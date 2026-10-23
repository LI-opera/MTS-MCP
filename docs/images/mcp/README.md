# MCP 演示截图

三张真实截图已在根 README 中横向并排展示，点击可查看原图。

| 文件 | 内容 |
|---|---|
| [01-tool-setup.png](01-tool-setup.png) | Codex 检查工具已加载，展示名称与用途 |
| [02-tool-call.png](02-tool-call.png) | 虚构 HTN 文本触发工具调用，返回 COMPLETED 和成功标志 |
| [03-analysis-result.png](03-analysis-result.png) | hypertension 扩写文本、Hypertensive disorder 标准术语及 CODED 状态 |

后续更新时用同名 PNG 替换文件即可，无需修改根 README 的图片路径。保留虚构病例，裁去密钥、账户信息与无关对话。

在独立仓库根目录提交更新：

```powershell
git add README.md docs/images/mcp integrations/mcp/LIVE_DEMO.md
git diff --cached --stat
git commit -m "docs: update MCP demonstration screenshots"
git push origin main
```
