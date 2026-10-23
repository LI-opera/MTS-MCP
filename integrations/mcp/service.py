"""Bounded HTTP adapter. No clinical text or backend bodies are logged."""
import asyncio
import hashlib
import json
import re
import sqlite3
import time
import uuid
from contextlib import contextmanager

import httpx
from pydantic import BaseModel, ConfigDict, Field

from .config import Config


class BackendResult(BaseModel):
    model_config = ConfigDict(strict=True, extra="ignore")
    request_id: str | None = None
    success: bool
    expansion_success: bool
    standardization_success: bool
    success_breakdown: dict | None = None
    expanded_text: str
    mappings: list[dict]
    standardized_entities: list[dict] = Field(default_factory=list)
    mapping_states: list[dict] = Field(default_factory=list)


def failure(code, message):
    return {"status": code, "message": message, "retry_automatically": False}


class Store:
    """Persist hashes/status only, never input or result bodies.

    Successful duplicates are refused for ten minutes; ambiguous outcomes for
    24 hours. A global lease also bounds concurrent requests across processes.
    Expiry is a retry guard, not an exactly-once guarantee for the backend.
    """
    def __init__(self, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        with self.connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS requests (key TEXT PRIMARY KEY, state TEXT NOT NULL, expires REAL NOT NULL, active_until REAL NOT NULL)")

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=5)
        try:
            with db:
                yield db
        finally:
            db.close()

    def claim(self, key, timeout):
        now = time.time()
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("DELETE FROM requests WHERE expires <= ?", (now,))
            previous = db.execute("SELECT state FROM requests WHERE key=?", (key,)).fetchone()
            if previous:
                return "DUPLICATE" if previous[0] == "COMPLETED" else "OUTCOME_UNKNOWN"
            if db.execute("SELECT 1 FROM requests WHERE active_until > ?", (now,)).fetchone():
                return "BUSY"
            if db.execute("SELECT COUNT(*) FROM requests").fetchone()[0] >= 1000:
                return "CAPACITY"
            db.execute("INSERT INTO requests VALUES (?, 'RUNNING', ?, ?)", (key, now + 86400, now + timeout + 60))
        return None

    def finish(self, key, state):
        now = time.time()
        with self.connect() as db:
            # Unknown requests may still be executing on the backend. Preserve
            # their active lease; never claim cancellation stopped the backend.
            if state == "COMPLETED":
                db.execute("UPDATE requests SET state=?, expires=?, active_until=0 WHERE key=?", (state, now + 600, key))
            else:
                db.execute("UPDATE requests SET state=?, expires=? WHERE key=?", (state, now + 86400, key))


class MedicalService:
    def __init__(self, config: Config, transport=None):
        self.config = config
        self.store = Store(config.db_path)
        self.transport = transport  # Tests supply MockTransport, production None.

    async def analyze(self, text):
        if not isinstance(text, str):
            return failure("INVALID_INPUT", "请输入英文纯文本。")
        text = text.strip()
        if not text or len(text) > self.config.max_chars or not re.search(r"[A-Za-z]", text):
            return failure("INVALID_INPUT", f"请输入包含英文字母的文本，长度为 1～{self.config.max_chars} 字符。")
        key = hashlib.sha256((self.config.base_url + "\0" + text).encode()).hexdigest()
        try:
            blocked = self.store.claim(key, self.config.timeout)
        except sqlite3.Error:
            return failure("STORE_ERROR", "本地请求记录不可用，未提交分析。")
        if blocked:
            messages = {
                "DUPLICATE": "相同文本在最近十分钟已返回结果，请查看上一次工具结果。",
                "OUTCOME_UNKNOWN": "相同文本的上次请求结果未确认，24 小时内不重复提交；请先检查后端记录。",
                "BUSY": "已有请求正在处理或等待超时确认，请稍后再试。",
                "CAPACITY": "本地请求记录已达到上限，请等待过期记录释放。",
            }
            return failure(blocked, messages[blocked])
        try:
            async with asyncio.timeout(self.config.timeout):
                async with httpx.AsyncClient(
                    transport=self.transport, timeout=self.config.timeout,
                    follow_redirects=False, trust_env=False,
                    limits=httpx.Limits(max_connections=1),
                ) as client:
                    async with client.stream(
                        "POST", self.config.base_url.rstrip("/") + "/expand/simple",
                        json={"text": text}, headers={"X-Frontend-Request-Id": "mcp_" + uuid.uuid4().hex},
                    ) as response:
                        if response.status_code != 200:
                            raise ValueError("unexpected HTTP status")
                        chunks = bytearray()
                        async for chunk in response.aiter_bytes():
                            chunks.extend(chunk)
                            if len(chunks) > 2 * 1024 * 1024:
                                raise ValueError("response too large")
            data = json.loads(chunks, parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite JSON")))
            result = BackendResult.model_validate(data).model_dump()
            self.store.finish(key, "COMPLETED")
            return {"status": "COMPLETED", "scope": "medical_abbreviation_expansion_and_mapping", "result": result}
        except asyncio.CancelledError:
            self.store.finish(key, "OUTCOME_UNKNOWN")
            raise
        except Exception:
            # Never expose exception messages: HTTP errors may contain clinical data.
            try:
                self.store.finish(key, "OUTCOME_UNKNOWN")
            except sqlite3.Error:
                pass  # The persisted RUNNING row already prevents immediate retry.
            return failure("OUTCOME_UNKNOWN", "未取得可确认的分析结果。可能发生超时、后端不可用或响应异常；后端可能仍在处理，请勿自动重试。")
