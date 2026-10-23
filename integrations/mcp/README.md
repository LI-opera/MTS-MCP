# 医学术语 MCP 服务

本目录提供 standardize_medical_abbreviations 工具，复用医学平台 POST /expand/simple。

- [项目介绍与演示](../../README.md)
- [配置、安装、接入 Codex、启动与停止](../../docs/MCP_SETUP.md)
- [真实调用验证记录](LIVE_DEMO.md)
- [截图补充指南](../../docs/images/mcp/README.md)

代码：server.py 定义工具，config.py 加载配置，service.py 执行 HTTP 与去重控制，tests/ 包含离线测试和隔离子进程。check 不请求后端；run 使用 stdio，仅在工具被调用时发送医学请求。stdout 保留给 MCP 协议。

本地 .env、.venv/ 与 runtime/ 均不纳入 Git。requirements-lock.txt 为 Windows / Python 3.12 环境版本快照。
