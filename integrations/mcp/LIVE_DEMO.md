# 真实调用验证记录

验证日期：2026-10-23。以下输入均为虚构文本；结果来自开发环境的实际调用，不是模拟输出。

## Codex 桌面原生 MCP 工具

输入：`The patient has HTN.`

工具：`standardize_medical_abbreviations`。

实际扩写：`The patient has hypertension.`

标准术语：`Hypertensive disorder`，状态 CODED。后端 success、expansion_success、standardization_success 均为 true。

验证链路：当前 Codex 对话 → 已加载的 MCP 工具 → 生产 stdio 服务 → POST /expand/simple → 实际模型和术语检索 → 结构化结果。

首次调用遇到医学 API 已退出、端口拒绝连接。核对后端未接收该请求后恢复 API，仅人工解除对应未送达请求的保护；随后一次原生工具调用成功。此经历说明 MCP 进程不能替代医学 API 的运行管理。

## 本机 SDK 客户端

输入：`The patient has RA with joint pain and morning stiffness.`

实际扩写：`The patient has Rheumatoid Arthritis with joint pain and morning stiffness.`

标准术语：`Rheumatoid arthritis`，状态 CODED。扩写与标准化标志均为 true。

此例经过本机官方 SDK 客户端、生产 MCP 服务及真实医学后端；不是 Codex 原生界面截图。

## 离线与发布检查

7 个 unittest 方法覆盖输入校验、结果保真、跨实例去重、并发保护、取消/超时、异常响应、容量/到期和协议调用。测试使用 MockTransport 与临时状态库并拦截网络连接；与上述真实分析区分。

截图仍待使用者补充，README 中展示的是明确标记的占位图。源码与测试通过不代表每个部署环境都能立即复现：实际输出取决于模型、术语库与配置。未将单例成功用作医学准确率、全病例实体标准化、多用户、公网或自动保活验收。
