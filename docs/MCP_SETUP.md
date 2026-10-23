# MCP 接入与运行指南

本文面向新克隆的独立项目。所有相对路径均从仓库根目录开始；请把示例绝对路径换成自己的路径。MCP 服务与医学 API 是两个独立进程。

## 准备医学后端

已有平台：复用原来的 API 地址和 Milvus 数据即可。不要再次执行建库脚本。

新环境（Docker Desktop 与 Python 3.12）：

```powershell
Copy-Item backend/.env.example backend/.env
notepad backend/.env
```

填写自己的 DEEPSEEK_API_KEY。仅当目标端口和容器名称无冲突时启动这个新环境：

```powershell
docker compose up -d --build
docker compose ps
```

默认 API 地址为 `http://127.0.0.1:8000`，网页为 `/app`。医学 API 的 `/health` 只验证进程在线。

只有在确认是可重建的新演示数据库时，才运行下面命令。**这个脚本会删除同名 concepts_only_name 集合后重建，不能对已有术语库直接执行。**

```powershell
docker compose exec api python tools/milvus/create_milvus_db.py
```

仓库的 SNOMED_5000.csv 是小型演示数据，不能替代完整术语库，且不包含完整 RxNorm；这里的真实演示是在原有配置环境完成，新建小库输出可能不同。首次模型下载需要网络。

如原来采用本机 Python 环境，在已准备好 `.venv`、后端依赖和 Milvus 的情况下，可单独启动 API：

```powershell
Set-Location backend
..\.venv\Scripts\python.exe -m uvicorn api.main:app --host 127.0.0.1 --port 8001
```

此窗口需保持运行。若尚未安装本机后端依赖，在根目录用 `py -3.12 -m venv .venv` 创建环境，再用 `.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt` 安装。模型缓存位置按个人环境配置，仓库不分发权重。

## 安装 MCP

回到仓库根目录：

```powershell
py -3.12 -m venv integrations/mcp/.venv
.\integrations\mcp\.venv\Scripts\python.exe -m pip install -r integrations/mcp/requirements-lock.txt
Copy-Item integrations/mcp/.env.example integrations/mcp/.env
notepad integrations/mcp/.env
```

若已有 `.env` 则直接编辑，勿覆盖已有设置。将 MEDICAL_API_BASE_URL 改为实际端口：Compose 通常 8000，本机示例 8001。只允许回环 IP HTTP，不填 `/app`。不需要飞书 ID 或 MCP API Key。

```powershell
.\integrations\mcp\.venv\Scripts\python.exe -m integrations.mcp.server check
.\integrations\mcp\.venv\Scripts\python.exe -m unittest integrations.mcp.tests.test_mcp -v
```

以上检查不请求真实医学后端；应看到 Configuration OK 和测试 OK。

## 配置 Codex

1. 打开 `integrations/mcp/codex-config.example.toml`。
2. 替换 `command` 和 `cwd` 为这个仓库的绝对路径；Windows TOML 示例使用单引号，反斜杠不需要转义。
3. 备份并编辑你实际使用的 Codex 配置，默认 `~/.codex/config.toml`。
4. 合并模板中的两个表，保留其他内容。如果同名表已存在则修改该表，不要重复添加。
5. 保存并重启 Codex，先要求检查 `standardize_medical_abbreviations` 是否加载。
6. 确认医学 API 在线后，再发送虚构文本，并确认工具调用。

模板设置为工具调用前询问，因为医学后端可能调用付费模型。MCP 默认超时 180 秒；Codex 工具超时 240 秒。如果改变前者，保持后者更长。

Codex 自动管理 stdio MCP 子进程。不要手动运行第二个同名服务。MCP 没有单独的网页 URL，也不会为你启动医学 API。

## 验证实际调用

可发送：

> 请调用 standardize_medical_abbreviations，分析这段虚构文本：The patient has HTN. 保留工具返回的状态，失败不要自动重试。

检查有实际工具调用，而不只是模型直接回答。后端有效响应下，COMPLETED 表示工具收到结果；医学是否扩写、编码成功仍看结果中各标志及 mapping_states。

## 排障与停止

| 现象 | 检查方式 |
|---|---|
| 工具未加载 | 确认绝对路径、配置表名、依赖安装，重启客户端 |
| OUTCOME_UNKNOWN | 先检查 API 进程、端口和请求日志，不要反复提交或删除状态库 |
| BUSY | 等待活动请求或保护租期结束；可能仍有后端请求在运行 |
| DUPLICATE | 同文本十分钟内已有结果，回看原工具响应 |
| API 在线但映射失败 | 检查 Milvus 集合、模型配置与实际 mapping_states；health 不检查这些依赖 |

状态库为 `integrations/mcp/runtime/requests.sqlite3`，只存摘要、状态与时间。未确认的同文本保护 24 小时，保护记录不能证明后端已终止。只有核查请求确未送达后，才考虑人工处理，不应通过改字绕过保护。

禁用 MCP：将对应 Codex 配置表的 enabled 改为 false，再重启。停止手动 API：在 API 终端按 Ctrl+C。停止本仓库 Compose：`docker compose stop`。不要使用删除数据卷的命令来停止服务。

## 工作原理与运行边界

一个工具，一次文本，一次 HTTP 请求。后端网络/响应异常不自动重试；同一状态库内控制并发，不限制其他网页或飞书服务对同一个 API 的调用。SQLite 摘要去重不等于多用户授权或公网安全方案。

当前发布源码包含本机 stdio 服务，不是公网 Streamable HTTP 服务。没有配置 OAuth 或远程服务权限控制。原医学处理范围是缩写扩写与概念映射，不是全病例诊断。

参考：[官方 MCP SDK](https://py.sdk.modelcontextprotocol.io/) 与 [Codex MCP 配置](https://developers.openai.com/codex/mcp/)。
