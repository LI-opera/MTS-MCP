"""Explicit CLI entry point; stdout is reserved for MCP when running."""
import argparse
import json
import sys
from typing import Annotated

from mcp.server import MCPServer
from mcp.types import CallToolResult, TextContent, ToolAnnotations
from pydantic import Field

from .config import load_config
from .service import MedicalService


def build_server(service):
    server = MCPServer(
        "medical-terminology", version="0.1.0", log_level="WARNING",
        instructions="医学缩写扩写与概念映射工具。保留后端的不确定状态，不补造概念代码，不将结果当作诊断或全病例实体标准化。失败后不要自动重试。",
    )

    @server.tool(annotations=ToolAnnotations(
        read_only_hint=False, destructive_hint=False,
        idempotent_hint=False, open_world_hint=True,
    ))
    async def standardize_medical_abbreviations(
        text: Annotated[str, Field(strict=True, min_length=1, max_length=service.config.max_chars)],
    ) -> CallToolResult:
        """通过本机医学后端扩写英文医学缩写并映射标准概念。可能调用付费模型；仅在用户要求分析时使用。每条文本独立处理，不支持文件、诊断或完整病例所有实体识别。"""
        payload = await service.analyze(text)
        return CallToolResult(
            content=[TextContent(type="text", text=json.dumps(payload, ensure_ascii=False))],
            structured_content=payload, is_error=payload["status"] != "COMPLETED",
        )

    return server


def main():
    parser = argparse.ArgumentParser(description="Medical Terminology MCP (local stdio)")
    parser.add_argument("mode", choices=["check", "run"])
    args = parser.parse_args()
    try:
        config = load_config()
    except (ValueError, OSError):
        print("MCP configuration invalid; check integrations/mcp/.env", file=sys.stderr)
        return 2
    if args.mode == "check":
        print(f"Configuration OK; backend={config.base_url}; timeout={config.timeout:g}s; max_chars={config.max_chars}")
        print("No backend request made. Codex starts the stdio server on demand.")
        return 0
    build_server(MedicalService(config)).run(transport="stdio")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
