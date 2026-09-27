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
---

### [2026-09-27 21:22] 🟢已完成：host_permissions 修复 + 注入提示条 + 重打包 v0.1.1
**目标**：按 21:18 指令修复 manifest 缺失的 host_permissions，增强注入可见性，重新打包。

**已做的事**：
- `extension/manifest.json`：version 升 **0.1.1**；新增（位于 `browser_specific_settings` 之后）：
  ```json
  "host_permissions": ["https://claude.ai/*"]
  ```
- `extension/content.js`：保留 console.log，新增页面右上角提示条——红色半透明（rgba(200,30,30,0.75)）小条，文字「Claude MCP Bridge 已注入」，3 秒后自动 remove()；z-index 2147483647、pointer-events:none，不干扰页面
- `extension/pack.py`：VERSION 同步 0.1.1
- 重新打包产出 `claude-mcp-bridge-0.1.1.xpi`（仓库根目录），随本 commit 入库

**结果/验证**：
- 从 .xpi 内部实测读回：entries 全部在根目录（flat）；`version: 0.1.1`；`host_permissions: ['https://claude.ai/*']` ✓
- 旧 `claude-mcp-bridge-0.1.0.xpi` 保留未删（协调者未要求删除；**当前有效版本为 0.1.1**）

**下一步打算**：
- 等用户真机验证：卸载旧临时扩展 → 加载 `claude-mcp-bridge-0.1.1.xpi` → 刷新 claude.ai → 看右上角提示条 + 控制台日志
- 验证通过后等协调者指示是否推进 WebSocket 阶段
---

### [2026-09-27 21:24] 【协调者验收 + 第二阶段指令】
- 针对：21:22 修复 + 用户确认「注入时页面右上角弹红色半透明提示条，成功了」
- 决策/指示：
  **验收结论：注入验证通过，第一阶段正式完成。**

  已核对：
  - manifest.json 含 host_permissions + version 0.1.1 ✓
  - content.js 含提示条逻辑 ✓
  - 用户真机确认提示条出现并 3 秒消失 ✓

  **进入第二阶段：WebSocket 双向桥接（最小可用）**

  目标（本次只做通信层，不做 DOM 发消息）：
  1. **MCP Server 侧**：
     - 在现有 stdio MCP 之外，额外启动一个本地 WebSocket 服务（端口 **8765**）。
     - 支持扩展连接后的简单协议：收到 `{ "type": "ping" }` 回 `{ "type": "pong" }`；收到 `{ "type": "echo", "text": "..." }` 回 `{ "type": "echo_reply", "text": "..." }`。
     - 保持原有 hello 工具可用。
  2. **扩展侧（background.js）**：
     - 启动后自动连接 `ws://127.0.0.1:8765`。
     - 连接成功/失败/断开时 console.log 明确状态。
     - 收到 pong / echo_reply 时也 log 出来。
     - 可选：页面加载后 content script 通过 runtime.sendMessage 让 background 发一次 ping，验证全链路。
  3. **不要**现在做 Claude 页面 DOM 操作（填框、点发送等），只打通扩展 ↔ Server 的 WebSocket。
  4. 完成后重新打包成 `claude-mcp-bridge-0.2.0.xpi`，并在日志贴出关键代码摘要 + 如何本地测试（先起 Server，再加载扩展，看两边日志）。

- 备注：
  - 端口固定 8765，协议先用简单 JSON。
  - requirements.txt 按需补充 websockets 或 aiohttp。
  - 颗粒度：只做通信通畅，不碰页面交互。
---

### [2026-09-27 21:30] 🟢已完成：第二阶段 —— WebSocket 双向桥接（最小可用）v0.2.0
**目标**：打通扩展 ↔ 本地 Server 的 WebSocket 通信层（ping/echo 协议），不碰 Claude 页面 DOM。

**已做的事**：
- 新增 `mcp_server/bridge_ws.py`：常驻 WS 服务（`ws://127.0.0.1:8765`，websockets 17.1）。协议（JSON text）：
  - `{"type":"ping"}` → `{"type":"pong"}`
  - `{"type":"echo","text":"..."}` → `{"type":"echo_reply","text":"..."}`
  - 未知 type / 非法 JSON → `{"type":"error","error":"..."}`
  - 与 `server.py`（MCP stdio）为**独立进程、独立入口**：MCP run() 是阻塞的，同进程并跑需动 MCP 库内部 session，独立进程更稳且满足本阶段目标；后续工具需与 WS 互通时再设计跨进程通道（已列入待设计点）
- 重写 `extension/background.js`：自动连 `ws://127.0.0.1:8765`，3 秒自动重连；onopen/onerror/onclose/onmessage 全部明确 log；pong / echo_reply 专门 log；runtime.onMessage 支持 `bridge-ping` / `bridge-echo` 两消息
- `extension/content.js`：注入后自动 `runtime.sendMessage({type:"bridge-ping"})` 触发 background 发 ping（验证 content→background→Server 全链路）；提示条保留
- `manifest.json` version → **0.2.0**；`requirements.txt` 补 `websockets>=12.0`；`pack.py` VERSION 同步
- 重新打包 `claude-mcp-bridge-0.2.0.xpi`（仓库根目录，随本 commit 入库）

**结果/验证**（服务端与客户端双端实测）：
- WS 服务后台运行，Python 客户端连入后依次发 ping / echo / unknown / 非法 JSON，回包逐条正确：
  `pong` / `{"type":"echo_reply","text":"hello bridge"}` / `{"type":"error","error":"unknown type: whatever"}` / `{"type":"error","error":"invalid json"}`
- 服务端日志完整记录 connected / recv / send / removed
- MCP 侧回归：hello 工具实测仍可用（`hello, phase2!`）
- 扩展↔Server 的真机验证（加载 0.2.0 → 看 background 控制台 "WS connected" + pong 日志）需用户/协调者侧操作，本环境无浏览器 GUI

**本地测试方法**：
1. 起 Server：`python mcp_server/bridge_ws.py`（看到 listening on ws://127.0.0.1:8765）
2. 加载 `claude-mcp-bridge-0.2.0.xpi`
3. 打开 claude.ai，看页面控制台有 injected + ping via background
4. 在 about:debugging → 扩展 → Inspect 看 background 控制台是否有 "WS connected" 和 "pong received"

**下一步打算**：等用户真机验证 WebSocket 连通性后，再推进 DOM 发消息阶段。
---

### [2026-09-27 21:34] 【协调者诊断】
- 针对：用户加载 v0.2.0 后控制台截图（`ping via background: { sent: false }`）
- 决策/指示：
  **诊断结论**：content → background 消息通路正常，但 **WebSocket 未连接成功**（`sent: false` 表示 `ws.readyState !== OPEN`）。

  最可能原因：**本地 WebSocket 服务没有启动**。

  请用户按以下步骤验证：
  1. 打开终端，进入项目目录，运行：
     ```
     python mcp_server/bridge_ws.py
     ```
     确认看到类似 `listening on ws://127.0.0.1:8765` 的输出。
  2. 保持该终端运行，然后在 Firefox：
     - 刷新 claude.ai 页面，或重新临时加载扩展。
  3. 查看两处日志：
     - **页面控制台**（F12）：应看到 `ping via background: { sent: true }`
     - **扩展 background 控制台**（about:debugging → 此 Firefox → 找到 Claude MCP Bridge → Inspect）：应看到 `WS connected` 和 `pong received`

  如果 Server 已启动仍出现 `sent: false`，请把 background 控制台的完整日志贴出来，再进一步排查。

- 备注：当前不需要执行者改代码，先确认 Server 是否在跑。
---

### [2026-09-27 21:40] 【协调者诊断 + 排查指令】
- 针对：用户反馈——Server 已启动（`python bridge_ws.py`，非之前提到的 venv，而是
  `C:\Users\hp\AppData\Local\Programs\Python\Python310\python.exe`），日志显示
  `listening on ws://127.0.0.1:8765`，随后持续反复报错：
  ```
  opening handshake failed
  ...
  EOFError: line without CRLF
  ...
  websockets.exceptions.InvalidMessage: did not receive a valid HTTP request
  ```
  （同一组 traceback 连续重复出现多次）
- 决策/指示：
  **诊断方向**：这类报错的含义是——有客户端建立了 TCP 连接，但没有发送合法的 HTTP
  升级请求就断开了（可能是空字节，也可能是非 HTTP 流量）。需要先分清来源：
  1. 是不是就是 Firefox 扩展在连（`background.js` 有 3 秒自动重连逻辑，若一直连不上
     会持续重试，时间上有可能对得上）；
  2. 还是本机其他进程/安全软件在扫描 8765 端口（这种情况下即使不开 Firefox 报错也会
     持续出现）。

  **本次任务（只做诊断，不改协议/不碰 DOM 逻辑）**：
  1. 修改 `mcp_server/bridge_ws.py`：加上连接来源日志。至少要能在每次 handshake
     成功或失败时打印 `websocket.remote_address`（IP:端口）。如果 websockets 库支持，
     打开其内置 logger（`logging.basicConfig(level=logging.DEBUG)` 并对
     `"websockets"` logger 设置 DEBUG），确认失败的连接来自本机哪个端口范围/是否
     每次端口号都变化（变化说明是新连接不断建立，符合扫描或重连特征）。
  2. 请用户配合做一次对照实验，并把结果原文（不只是描述，要贴日志文本）反馈：
     - **步骤 A**：完全关闭 Firefox（不加载扩展），只保留 `bridge_ws.py` 单独运行，
       观察 5-10 秒——这段时间内 "opening handshake failed" 是否还会自己反复出现？
       - 如果 **还在报错**：说明来源不是扩展，是本机别的东西在扫 8765 端口（比如杀毒
         软件/安全防护），需要考虑换个端口或者加白名单排查。
       - 如果 **不再报错**：说明确实是扩展在连但连不上，进入下一步。
     - **步骤 B**（仅在步骤A显示"不报错"时做）：重新加载 Firefox 扩展 v0.2.0，打开
       claude.ai，同时观察三处：
       - Server 终端：新的 handshake 日志（含来源信息，看是否还失败）
       - 页面控制台（F12）：`ping via background: { sent: ? }`
       - 扩展 background 控制台（about:debugging → Inspect）：完整日志文本
  3. 把 A/B 两步的**原始日志文本**（尤其是新加的来源信息）整理进下一条 🟢/🔴 记录，
     不要只用"好了/还是不行"这种结论性描述。

- 备注：
  - 分支已确认为 `main`（仓库只有这一个分支，本地远程一致）。
  - 这一步只加日志排查代码，**不要**改动 ping/echo 协议、不要动 background.js/
    content.js 的业务逻辑，避免排查过程中引入新变量。
  - 如果步骤 A 证实是本机安全软件在扫描端口，下一轮我会再决定是换端口还是加白名单，
    现在先不要自行改端口号。
---

### [2026-09-27 21:46] 【协调者指令】
- 针对：用户反馈——**确认是浏览器扩展这边的问题**，报错是在刷新 claude.ai 页面后
  才出现的（未完整走 21:40 指令里的步骤 A/B，是基于"刷新页面 → 报错出现"这个时间
  相关性做的判断，先按此推进，若后续证据有出入再回头验证）
- 决策/指示：
  **锁定排查范围为扩展 ↔ Server 的握手过程**，本次任务只加诊断能力，不改协议：

  1. **`mcp_server/bridge_ws.py` 加原始字节 + 来源日志**：
     - 用 `websockets` 提供的 `process_request`（或等效的底层 hook）在正式握手校验之前，
       把收到的原始请求行/首部文本、以及 `remote_address`（IP:端口）打印出来，即使
       解析失败也要能看到"到底收到了什么"，而不是只看到异常堆栈。
     - 目的：分清是收到了**完全空的字节**（连接建立后立刻断开，一个字节没发）还是
       收到了**非 HTTP 的乱码/被截断的数据**（说明中间有东西改写了流量，比如代理/
       安全软件在拦截本地回环流量）。
  2. **`extension/background.js` 加连接生命周期去重日志**：
     - 在每次准备 `new WebSocket(...)` 之前，打印当前是否已存在一个未关闭的连接
       （现有 ws 对象的 readyState），避免"页面刷新触发 content script 唤醒 background
       → background 重复建立多个 WebSocket 对象"这种情况被误判为"服务端拒绝"。
     - 保留原有 onopen/onerror/onclose 日志不变。
  3. **提一个澄清问题给用户**（不用写代码，日志里问一下即可）：用户本机是否开着任何
     **VPN / 代理 / 杀毒软件的网络防护（比如 360、火绒的"流量防护"类功能）**？这类
     软件有时会拦截/重写 `127.0.0.1` 的回环流量，是「握手数据被截断成非 HTTP」的
     常见来源之一。

  **不要**在这一步改端口、改协议、实现 DOM 发送逻辑。

- 备注：
  - 完成后追加 🟢/🔴 记录，贴：(a) Server 端新日志的原始文本（尤其是有没有抓到
    "空字节"还是"乱码字节"）、(b) background.js 新日志、(c) 用户对 VPN/安全软件
    问题的回答。三者凑齐了大概率就能定位根因。
---

### [2026-09-27 21:50] 【协调者指令】
- 针对：用户回复——**360 已关闭，但本机确实开着代理**
- 决策/指示：
  **高度怀疑根因就是代理**。原理：`ws://127.0.0.1:8765` 本该走本地回环、不经过任何
  代理，但如果代理软件（比如 Clash / V2ray / 类似工具）没有把 `127.0.0.1` /
  `localhost` 加入"直连/绕过"名单，或者 Firefox 自身的网络设置把"所有协议都使用
  该代理服务器"勾选了，就会导致 WebSocket 握手请求被发去代理那里绕一圈，代理再转发
  回本地服务端时数据被重新包装/截断，正好对应我们看到的"收到的不是合法 HTTP 请求"。

  **本次不需要执行者改代码，先让用户直接排查两处代理设置**：
  1. **Firefox 自身的网络代理设置**（独立于系统代理，容易被忽略）：
     `about:preferences` → 搜索"网络设置/Network Settings" → "设置"按钮 → 看当前是
     "使用系统代理设置" 还是 "手动配置代理"：
     - 如果是手动配置：检查"不使用代理"/"无代理"的例外列表里有没有
       `127.0.0.1` 和 `localhost`，没有就加上。
     - 如果是"使用系统代理设置"：去检查系统代理（或代理软件自己的设置面板）的
       "绕过代理的地址/直连列表"里是否包含 `127.0.0.1`、`localhost`、
       `<local>`，通常代理软件（Clash 等）默认会绕过局域网地址，但如果开了
       "增强模式/TUN 模式"之类的全局接管，可能会连本地回环也一起接管。
  2. **最快的验证方法（不用改配置也能先确认是不是它）**：暂时把代理软件整个**退出/
     关闭**（不是切换到"直连"模式，是彻底退出进程，因为有些代理即使切直连也还在
     拦截系统层流量），然后：
     - 保持 `bridge_ws.py` 继续跑
     - 刷新 claude.ai 页面
     - 看 Server 终端还报不报 "opening handshake failed"
     - 如果不报了 → 确认是代理的问题，回头再去加 `127.0.0.1`/`localhost` 的绕过规则，
       不用一直关代理
     - 如果还报错 → 代理不是唯一原因，回到 21:46 指令里加的诊断日志继续排查

- 备注：
  - 这一步是用户侧的配置排查，不涉及仓库代码改动，执行者暂不需要动手。
  - 等用户反馈"关代理后是否还报错"，协调者再决定：是指导配置绕过规则收尾，还是继续走
    21:46 的代码诊断路线。
---