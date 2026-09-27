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
---

### [2026-09-27 20:51] 【协调者指令】
- 针对：用户明确要求「要火狐浏览器的扩展」——修正浏览器目标
- 决策/指示：
  1. **浏览器扩展目标改为优先 Firefox**。
     - 使用 **Firefox 兼容的 Manifest V3**（Firefox 109+ 已支持 MV3）。
     - 目录仍叫 `extension/`，但 manifest.json、background、content script 按 Firefox 要求编写。
     - 如有必要可后续再加 Chrome 兼容层，当前阶段只保证 Firefox 能加载并注入 `claude.ai`。
  2. 其他决策保持不变（Python MCP Server、WebSocket、双向基础）。
  3. **第一阶段任务更新**：
     - 目录结构保持不变（`mcp_server/` + `extension/`）。
     - `extension/` 下创建**最小 Firefox Manifest V3 扩展骨架**：
       - manifest.json（browser_specific_settings 等 Firefox 字段按需加）
       - background.js（或 service worker）
       - content.js（匹配 `https://claude.ai/*`）
     - 能在 Firefox 的 about:debugging 中临时加载，content script 能成功注入 claude.ai 页面即可。
     - 仍然**不要**实现真正的发送逻辑或 WebSocket 连接。

- 备注：
  - 如果执行者已经按之前的 Chrome 指令开始动手，请停止并按本指令改为 Firefox 目标。
  - 完成后同样追加 🟢 记录，附目录树 + 关键文件摘要（尤其是 manifest.json 内容）。
  - 本地项目路径请一并确认写明。
---

### [2026-09-27 21:00] 🟢已完成：第一阶段 —— 骨架搭建（Firefox 版）
**目标**：按协调者两条指令（20:48 + 20:51 修正为 Firefox）搭建 MCP Server 与浏览器扩展最小骨架，不实现真实业务逻辑。

**本地项目路径确认**：`D:\\kk三部曲\\155.claude-mcp-bridge`

**已做的事**：
- 新建 `mcp_server/`：
  - `server.py`：Python MCP Server 骨架，基于官方 `mcp` 库（**v2.2.0**，注意 2.x 已把 FastMCP 更名为 `MCPServer`，本骨架直接用 2.x API），暴露一个 `hello` 测试工具，stdio 传输
  - `requirements.txt`：`mcp>=2.0.0`
- 新建 `extension/`（Firefox MV3）：
  - `manifest.json`：manifest_version 3 + `browser_specific_settings.gecko`（id: claude-mcp-bridge@aexsxs.dev, strict_min_version 109.0）；background 用 `scripts`（Firefox event page，非 service_worker）；content script 匹配 `https://claude.ai/*`
  - `background.js`：仅生命周期日志
  - `content.js`：仅注入标记日志
- 未动 README，未实现 WebSocket / 发送逻辑（遵守指令）

**结果/验证**：
- MCP Server **实测通过**：用 mcp 客户端走 stdio 完成 initialize + call_tool('hello')，返回 `hello, bridge!`（全链路实测，非静态检查）
- `manifest.json` JSON 语法校验通过
- Firefox 实际加载（about:debugging）未验证——本机执行环境无法操作浏览器 GUI，需协调者或用户手动加载验证 content script 注入
- 环境备注：venv 位于 `C:\\Users\\hp\\.workbuddy\\binaries\\python\\envs\\bridge`（跑 server 用它）；pip 装 tuna 镜像异常（from versions: none），换 aliyun 镜像成功，供后续排障参考

**下一步打算**（等协调者指示）：
- 第二阶段候选：扩展 ↔ Server 的 WebSocket 连接（8765）；Claude.ai 页面 DOM 交互（发送消息）；回复抓取
- 扩展骨架待真机 Firefox 加载验证后，方可进入下一阶段

**风险/疑问**：
- Firefox MV3 的 background 暂用 `scripts`（event page）；若后续要 Chrome 兼容需加 `service_worker` 字段，结构上已预留
- 本 commit：见 git log（骨架文件 + 本日志同 commit 提交）
---

### [2026-09-27 21:06] 【协调者验收】
- 针对：第一阶段骨架（21:00 🟢记录）
- 决策/指示：
  **验收结论：通过（带备注）**

  已用工具实际核对仓库内容：
  - 目录结构正确：`mcp_server/` + `extension/` 齐全
  - `mcp_server/server.py`：仅 hello 工具 + stdio，无真实业务逻辑 ✓
  - `mcp_server/requirements.txt`：`mcp>=2.0.0` ✓
  - `extension/manifest.json`：MV3 + gecko id + strict_min_version 109.0 + background.scripts + content_scripts 匹配 claude.ai ✓
  - `background.js` / `content.js`：仅 console.log，无发送/WS 逻辑 ✓
  - 本地路径已记录：`D:\\kk三部曲\\155.claude-mcp-bridge`

  **备注 / 风险提示**：
  1. `from mcp.server.mcpserver import MCPServer` 这条导入路径依赖执行者声称的 mcp 2.x 更名。后续若官方包仍使用 FastMCP 或其他路径，需修正。当前阶段可接受。
  2. Firefox 真机加载（about:debugging）尚未由执行者验证——请用户或协调者侧有条件时手动确认 content script 是否成功注入。
  3. 无越权改动，遵守了「不实现真实发送/WS」的边界。

  **当前不立即下发第二阶段任务**。请执行者先确认：
  - 是否方便在本机 Firefox 临时加载扩展并验证 content script 注入（看控制台是否有 `[claude-mcp-bridge] content script injected`）？
  - 若已验证，请补充 🟢 记录；若暂时无法验证，也可直接说明，协调者再决定是否推进 WebSocket 连接阶段。

- 备注：等待执行者对 Firefox 加载验证的反馈后再开下一阶段。
---

### [2026-09-27 21:10] 【协调者指令】
- 针对：用户提供了可被 Firefox 直接接受的 .xpi 示例包，要求后续打包成这种格式
- 决策/指示：
  1. **打包规范**（参考用户提供的示例 `claude-skills-sync-fixed-v1.9.1.xpi`）：
     - .xpi 本质是 **ZIP 压缩包**，文件必须放在 **ZIP 根目录**（flat structure，不能有 extension/ 子文件夹）。
     - 示例结构（根目录直接包含）：
       ```
       manifest.json
       background.js
       content-script.js   （或 content.js）
       （可选其他文件如 panel.html / panel.js）
       ```
     - manifest.json 风格与示例一致：MV3 + `browser_specific_settings.gecko` + `background.scripts` + `content_scripts` + `host_permissions`。
  2. **当前阶段要求**：
     - 在 `extension/` 目录下增加一个简单打包脚本或说明（例如 `pack.ps1` 或 `pack.sh`），能把当前 extension 里的文件打成 `claude-mcp-bridge-0.1.0.xpi`。
     - 打包命令示例（PowerShell）：
       ```powershell
       Compress-Archive -Path manifest.json, background.js, content.js -DestinationPath ..\claude-mcp-bridge-0.1.0.xpi -Force
       ```
       或使用 zip 工具，确保文件在 ZIP 根目录。
     - 把生成的 .xpi 也提交到仓库根目录（或 extension/ 下），方便用户直接拖到 Firefox 安装/临时加载。
  3. **不要**现在实现业务逻辑，只加打包能力 + 产出一个可用的 .xpi 骨架包。

- 备注：
  - 完成后在日志追加 🟢 记录，说明打包脚本位置、生成的 .xpi 文件名，以及如何验证（用户可用 about:debugging → 临时加载附加组件 → 选择该 .xpi）。
  - 本地路径已确认，无需再重复。
---

### [2026-09-27 21:15] 🟢已完成：.xpi 打包能力 + 骨架包产出（含 Firefox 验证问题反馈）
**目标**：按 21:10 指令增加打包脚本并产出 flat 结构 .xpi；同时反馈 21:06 验收中关于 Firefox 真机验证的问题。

**已做的事**：
- 新增 `extension/pack.ps1`：按指令示例编写的 PowerShell 打包脚本（Compress-Archive，列文件保 flat）
- 新增 `extension/pack.py`：Python zipfile 打包脚本（本机执行环境 PowerShell 子进程受限，Compress-Archive 静默失败，故补 Python 版保证可复现；arcname 用裸文件名确保 ZIP 根目录）
- 产出 `claude-mcp-bridge-0.1.0.xpi`（仓库根目录，约 1 KB），**随本 commit 提交入库**

**结果/验证**：
- ZIP 条目实测：`['manifest.json', 'background.js', 'content.js']` —— 全部在根目录，flat 结构符合示例规范
- `pack.py` 连跑两次（含删除重建）验证可复现
- **关于 Firefox 真机验证的反馈**：我的执行环境无浏览器 GUI 操作能力，无法自行完成 about:debugging 临时加载验证。现用户已拿到 .xpi，可直接验证：`about:debugging` → 此 Firefox → 临时加载附加组件 → 选择 `claude-mcp-bridge-0.1.0.xpi` → 打开 claude.ai 页面看控制台是否有 `[claude-mcp-bridge] content script injected`。请协调者决定：等用户验证反馈，还是直接推进 WebSocket 连接阶段。

**下一步打算**：
- 等协调者指示：推进 WS 连接阶段，或等待真机验证结果

**风险/疑问**：
- PowerShell 环境备注：本机沙箱对 PowerShell 子进程（powershell.exe 嵌套、Add-Type、Compress-Archive）有限制，pack.ps1 逻辑正确但在本环境不可执行，需在正常终端跑；Python 版无此限制
---

### [2026-09-27 21:18] 【协调者指令】
- 针对：用户反馈「打包文件已经加载，但是在目标网页不能使用」（截图显示扩展已出现在网站权限列表，但实际无效果）
- 决策/指示：
  **问题诊断**：当前 `manifest.json` **缺少 `host_permissions`**。示例 .xpi 有明确的：
  ```json
  "host_permissions": ["https://claude.ai/*"]
  ```
  我们的骨架只有 `content_scripts.matches`，在 Firefox MV3 临时加载场景下经常导致 content script 无法真正注入或权限不足。

  **立即修复（本次只做这个）**：
  1. 修改 `extension/manifest.json`，增加：
     ```json
     "host_permissions": [
       "https://claude.ai/*"
     ]
     ```
     （位置建议放在 `browser_specific_settings` 之后、`background` 之前，与示例风格一致）
  2. 同时增强 `content.js` 的可见性（方便用户验证）：
     - 保留原来的 console.log
     - 额外在页面右上角临时插入一个明显的提示条（例如红色半透明小条，写「Claude MCP Bridge 已注入」），3 秒后自动消失。这样用户不需要开控制台也能立刻看到是否注入成功。
  3. 重新运行打包脚本，生成新的 `claude-mcp-bridge-0.1.0.xpi`（或版本升到 0.1.1）并提交到仓库根目录。
  4. **仍然不要**实现 WebSocket 或发送逻辑。

- 备注：
  - 用户需要：卸载旧临时扩展 → 重新加载新的 .xpi → 刷新 claude.ai 页面 → 看是否出现右上角提示条 + 控制台日志。
  - 完成后追加 🟢 记录，贴出修改后的 manifest.json 关键部分 + content.js 关键代码。
