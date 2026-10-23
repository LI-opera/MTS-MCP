# MCP 截图补充指南

三张图片在根 README 中横向并排。当前 SVG 均明确标注为占位示意，不是实拍界面。

| 文件名 | 拍摄内容 |
|---|---|
| 01-tool-setup.png | Codex 中医学 MCP 服务已连接，或工具已加载的明确证据 |
| 02-tool-call.png | 虚构英文输入和实际 standardize_medical_abbreviations 调用过程 |
| 03-analysis-result.png | 扩写后的完整文本、标准医学术语和结果状态 |

操作：

1. 将三张 PNG 放进本目录，按上表命名。
2. 打开仓库根 README.md，搜索 `MCP_SCREENSHOTS` 找到展示区域。
3. 将三个 `src` 中的 `-placeholder.svg` 改为 `.png`。
4. 删除表格中的【待补截图】文字、保存路径提示，以及“占位图”说明和 MCP_SCREENSHOTS 注释。
5. 保留三列表格，提交 README.md 与本目录的 PNG。占位 SVG 可在确认替换后删除。

可用 Git 命令（在这个独立仓库根目录执行）：

```powershell
git add README.md docs/images/mcp
git diff --cached --stat
git commit -m "docs: add real MCP demonstration screenshots"
git push origin main
```

只拍虚构病例。裁去 API Key、其他对话、账户信息和本机配置中不需要公开的内容。不要用手工排版的假界面代替真实工具调用截图。
