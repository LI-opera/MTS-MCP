"""Configuration loaded only on explicit startup, never on import."""
import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

HERE = Path(__file__).resolve().parent


@dataclass(frozen=True)
class Config:
    base_url: str = "http://127.0.0.1:8001"
    timeout: float = 180
    max_chars: int = 4000
    db_path: Path = HERE / "runtime" / "requests.sqlite3"

    def __post_init__(self):
        url = urlsplit(self.base_url)
        if (url.scheme != "http" or url.hostname not in {"127.0.0.1", "::1"}
                or url.username or url.password or url.query or url.fragment
                or url.path not in {"", "/"}):
            raise ValueError("MEDICAL_API_BASE_URL must be a literal loopback HTTP origin")
        _ = url.port  # Validate the port before any request.
        if not 1 <= self.timeout <= 600 or not 1 <= self.max_chars <= 20000:
            raise ValueError("timeout must be 1..600 seconds; max text chars must be 1..20000")


def load_config(path: Path = HERE / ".env") -> Config:
    values = {}
    if path.exists():
        for raw in path.read_text(encoding="utf-8-sig").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            key, sep, value = line.partition("=")
            if not sep:
                raise ValueError("Invalid config line: expected KEY=value")
            values[key.strip()] = value.strip().strip("\"'")
    def get(key, default):
        return os.environ.get(key, values.get(key, default))
    return Config(
        base_url=get("MEDICAL_API_BASE_URL", "http://127.0.0.1:8001").rstrip("/"),
        timeout=float(get("MEDICAL_TIMEOUT_SECONDS", "180")),
        max_chars=int(get("MEDICAL_MAX_TEXT_CHARS", "4000")),
    )
