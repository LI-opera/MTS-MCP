import asyncio
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

import httpx
from mcp import Client, StdioServerParameters

from integrations.mcp.config import Config
from integrations.mcp.server import build_server
from integrations.mcp.service import MedicalService

ROOT = Path(__file__).resolve().parents[3]


def valid():
    return {"success": False, "expansion_success": True, "standardization_success": False,
            "expanded_text": "synthetic expansion", "mappings": [],
            "mapping_states": [{"state": "WITHHELD", "reason": "ambiguous"}]}


class Tests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.config = Config(db_path=Path(self.temp.name) / "requests.db")
        # Guard after event loop creation: Windows socketpair is internal IPC.
        for target in ["socket.socket.connect", "socket.getaddrinfo"]:
            guard = patch(target, side_effect=AssertionError("network forbidden"))
            guard.start()
            self.addCleanup(guard.stop)
        self.calls = 0

    def service(self, handler=None, config=None):
        def respond(request):
            self.calls += 1
            self.assertEqual(request.url.path, "/expand/simple")
            self.assertEqual(request.method, "POST")
            return httpx.Response(200, json=valid())
        return MedicalService(config or self.config, httpx.MockTransport(handler or respond))

    async def test_result_and_restart_dedup(self):
        service = self.service()
        result = await service.analyze("The patient has SOB.")
        self.assertEqual(result["status"], "COMPLETED")
        self.assertFalse(result["result"]["success"])
        self.assertEqual(result["result"]["mapping_states"], valid()["mapping_states"])
        self.assertEqual((await self.service().analyze(" The patient has SOB. "))["status"], "DUPLICATE")
        self.assertEqual(self.calls, 1)
        self.assertNotIn(b"The patient", self.config.db_path.read_bytes())
        self.assertNotIn(b"synthetic expansion", self.config.db_path.read_bytes())

    async def test_validation_before_http(self):
        service = self.service()
        for text in [None, "", "   ", "中文", "a" * 4001]:
            self.assertEqual((await service.analyze(text))["status"], "INVALID_INPUT")
        self.assertEqual(self.calls, 0)
        for url in ["https://example.com", "http://localhost:8001", "http://127.0.0.1:8001/x", "http://user:pass@127.0.0.1"]:
            with self.assertRaises(ValueError):
                Config(base_url=url)

    async def test_errors_are_sanitized_no_retry(self):
        responses = [httpx.Response(302, headers={"location": "https://example.com"}),
                     httpx.Response(500, text="PRIVATE clinical text"),
                     httpx.Response(200, text="not JSON"),
                     httpx.Response(200, json={"success": "yes"}),
                     httpx.Response(200, content=b"a" * (2 * 1024 * 1024 + 1))]
        for i, response in enumerate(responses):
            with self.subTest(i=i):
                cfg = Config(db_path=Path(self.temp.name) / f"case{i}.db")
                calls = []
                def respond(request):
                    calls.append(request)
                    return response
                service = self.service(respond, cfg)
                result = await service.analyze("synthetic case")
                self.assertEqual(result["status"], "OUTCOME_UNKNOWN")
                self.assertNotIn("PRIVATE", json.dumps(result))
                self.assertEqual((await service.analyze("synthetic case"))["status"], "OUTCOME_UNKNOWN")
                self.assertEqual(len(calls), 1)

    async def test_busy_cancellation_and_timeout(self):
        started = asyncio.Event()
        async def slow(request):
            started.set()
            await asyncio.sleep(10)
            return httpx.Response(200, json=valid())
        service = self.service(slow)
        task = asyncio.create_task(service.analyze("first synthetic case"))
        await started.wait()
        self.assertEqual((await self.service().analyze("second synthetic case"))["status"], "BUSY")
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertEqual((await self.service().analyze("first synthetic case"))["status"], "OUTCOME_UNKNOWN")
        cfg = Config(timeout=1, db_path=Path(self.temp.name) / "timeout.db")
        self.assertEqual((await self.service(slow, cfg).analyze("timeout case"))["status"], "OUTCOME_UNKNOWN")

    async def test_expiry_and_capacity(self):
        service = self.service()
        await service.analyze("synthetic")
        with service.store.connect() as db:
            db.execute("UPDATE requests SET expires=0")
        self.assertEqual((await service.analyze("synthetic"))["status"], "COMPLETED")
        with service.store.connect() as db:
            db.executemany("INSERT INTO requests VALUES (?, 'COMPLETED', 99999999999, 0)", [(str(i),) for i in range(1000)])
        self.assertEqual((await service.analyze("new synthetic"))["status"], "CAPACITY")

    async def test_real_sdk_in_memory(self):
        for mode in ["auto", "legacy"]:
            cfg = Config(db_path=Path(self.temp.name) / f"{mode}.db")
            async with Client(build_server(self.service(config=cfg)), mode=mode) as client:
                listed = await client.list_tools()
                self.assertEqual(listed.tools[0].name, "standardize_medical_abbreviations")
                result = await client.call_tool("standardize_medical_abbreviations", {"text": "synthetic"})
                self.assertFalse(result.is_error)
                self.assertFalse(result.structured_content["result"]["standardization_success"])
                duplicate = await client.call_tool("standardize_medical_abbreviations", {"text": "synthetic"})
                self.assertTrue(duplicate.is_error)

    async def test_real_stdio_roundtrip(self):
        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "integrations.mcp.tests.stdio_fixture"],
            cwd=str(ROOT), env={**os.environ, "MCP_TEST_DB": str(Path(self.temp.name) / "child.db")},
        )
        async with Client(params, mode="legacy", read_timeout_seconds=15) as client:
            listed = await client.list_tools()
            self.assertEqual(len(listed.tools), 1)
            result = await client.call_tool("standardize_medical_abbreviations", {"text": "synthetic"})
            self.assertFalse(result.is_error)
            self.assertEqual(result.structured_content["result"]["mapping_states"], [{"state": "WITHHELD"}])


if __name__ == "__main__":
    unittest.main()
