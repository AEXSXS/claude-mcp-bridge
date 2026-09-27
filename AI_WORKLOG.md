# AI_WORKLOG — claude-mcp-bridge

> 指导模式协作日志：执行方（AI）与协调者通过本日志沟通，日志随代码同步 push 到仓库。

---
### [2026-09-27 20:45] 🟡计划中：项目启动 —— MCP Server + 浏览器扩展桥接
**目标**：让本地 AI 通过 MCP Server + 浏览器扩展与 Claude.ai 网页界面互通消息，实现两个 AI 互发消息。

**已做的事**：
- clone 仓库到本地（Initial commit 1a003b2，仅 README.md）
- 创建本日志文件 AI_WORKLOG.md 并纳入 git 管理（本次 commit）

**结果/验证**：
- git clone / push 链路验证：本次提交即验证（若协调者能看到此记录，说明链路通）

**下一步打算**：
- 初步架构理解（待协调者确认后再动手）：
  - MCP Server（本地进程，供本地 AI 连接）↔ 本地通信服务（HTTP/WebSocket）↔ 浏览器扩展（注入 claude.ai 页面）↔ Claude.ai 网页聊天界面
  - 扩展负责：向 Claude.ai 发送消息、抓取回复文本
  - MCP Server 暴露工具（设想）：`send_to_claude`（发消息）、`get_claude_reply`（轮询/等待回复）
- 待确认的技术选型：
  1. MCP Server 语言：Node.js 还是 Python？
  2. 浏览器扩展目标：Chrome / Edge / 都要？
  3. MCP Server ↔ 扩展通信方式：WebSocket 长连接（推荐，扩展可主动收消息）还是 HTTP 轮询？
  4. 消息交互形态：单向发指令等回复，还是双向自由对话？

**风险/疑问**：
- 上面 4 个选型问题请协调者定夺，确认后即开始搭骨架
---

### [2026-09-27 20:48] 【协调者指令】
- 针对：上一记录中的 4 个技术选型问题 + 整体启动方向
- 决策/指示：
  1. **MCP Server 语言**：选用 **Python**（使用官方 mcp 库 + websockets / aiohttp）。生态成熟，后续扩展工具方便。
  2. **浏览器扩展目标**：优先 **Chrome Manifest V3**（同时兼容 Edge）。先做 Chrome，不额外维护 Firefox 等。
  3. **通信方式**：**WebSocket 长连接**（扩展作为客户端主动连接本地 MCP Server 暴露的 WS 端口，推荐 8765）。支持实时双向推送。
  4. **交互形态**：先实现**双向能力**的基础（`send_to_claude` + `get_claude_reply`），但第一阶段只要求能可靠发送消息并返回发送结果；回复抓取作为第二阶段。

  **第一阶段任务（本次只做这个）**：
  - 创建项目基础目录结构：
    ```
    claude-mcp-bridge/
    ├── mcp_server/          # Python MCP Server
    │   ├── server.py
    │   ├── requirements.txt
    │   └── ...
    ├── extension/           # Chrome 扩展
    │   ├── manifest.json
    │   ├── background.js
    │   ├── content.js
    │   └── ...
    ├── AI_WORKLOG.md
    └── README.md
    ```
  - 在 `mcp_server/` 下搭一个最小可运行的 MCP Server 骨架（能启动、暴露一个 hello 工具即可）。
  - 在 `extension/` 下创建最小 Manifest V3 扩展骨架（能加载、content script 能注入 claude.ai）。
  - **不要**现在就实现真正的发送逻辑或 WebSocket 连接。先把目录和空骨架建好并提交。

- 备注：
  - 任务颗粒度控制：本次只建骨架，验证能 push 成功即可。
  - 完成后在本日志追加 🟢 记录，并贴出目录树 + 关键文件内容摘要。
  - 不要修改已有 README 以外的文件，除非是新建目录/文件。
  - 本地项目路径请在下一轮日志中确认写明。
