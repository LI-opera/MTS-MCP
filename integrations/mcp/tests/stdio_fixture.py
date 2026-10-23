"""Offline child process used ONLY by protocol tests, never production config."""
import asyncio
import os
from pathlib import Path
from unittest.mock import patch

import httpx

from integrations.mcp.config import Config
from integrations.mcp.server import build_server
from integrations.mcp.service import MedicalService


def response(request):
    return httpx.Response(200, json={
        "success": False, "expansion_success": True,
        "standardization_success": False, "expanded_text": "synthetic expansion",
        "mappings": [], "mapping_states": [{"state": "WITHHELD"}],
    })


async def run():
    # asyncio's Windows wake-up socket has already been created at this point.
    with patch("socket.socket.connect", side_effect=AssertionError("network forbidden")), \
         patch("socket.getaddrinfo", side_effect=AssertionError("DNS forbidden")):
        service = MedicalService(Config(db_path=Path(os.environ["MCP_TEST_DB"])), httpx.MockTransport(response))
        await build_server(service).run_stdio_async()


if __name__ == "__main__":
    asyncio.run(run())
