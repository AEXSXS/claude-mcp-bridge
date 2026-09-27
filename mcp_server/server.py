"""claude-mcp-bridge MCP Server (Phase 3)

工具：
  hello        链路测试
  page_info    读取 claude.ai 页面状态（是否开了新聊天页、输入框是否就绪）
  send_prompt  向输入框填文本并点发送
  get_reply    抓取最后一条 Claude 回复文本

通信：本进程作为 ws 客户端连 bridge_ws.py 的内部端口 ws://127.0.0.1:8766，
发 page_cmd（带 id），等扩展经 background/content 执行后回传 page_result。
前置条件：bridge_ws.py 已启动、Firefox 已加载扩展并打开 claude.ai。
"""

import asyncio
import json
import os
import uuid

import websockets
from mcp.server.mcpserver import MCPServer

INTERNAL_WS = os.environ.get("BRIDGE_WS_URL", "ws://127.0.0.1:8766")
PAGE_TIMEOUT = 30.0

mcp = MCPServer("claude-mcp-bridge")


async def page_cmd(action: str, payload: dict | None = None, timeout: float = PAGE_TIMEOUT) -> str:
    """发 page_cmd 到桥接服务，等 page_result。返回可读的结果文本。"""
    cmd_id = uuid.uuid4().hex[:8]
    req = {"type": "page_cmd", "id": cmd_id, "action": action,
           "payload": payload or {}, "timeout": timeout}
    async with websockets.connect(INTERNAL_WS, max_size=2**22) as ws:
        await ws.send(json.dumps(req))
        deadline = asyncio.get_event_loop().time() + timeout
        while True:
            remain = deadline - asyncio.get_event_loop().time()
            if remain <= 0:
                return f"[{action}] 超时：{timeout:.0f}s 内未收到 page_result（服务/扩展/页面任一环节未就绪）"
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=remain)
            except (asyncio.TimeoutError, TimeoutError):
                return f"[{action}] 超时：{timeout:.0f}s 内未收到 page_result（服务/扩展/页面任一环节未就绪）"
            msg = json.loads(raw)
            if msg.get("type") == "page_result" and msg.get("id") == cmd_id:
                if msg.get("ok"):
                    return f"[{action}] OK: {json.dumps(msg.get('data'), ensure_ascii=False)}"
                return f"[{action}] FAILED: {msg.get('error')}"


@mcp.tool()
def hello(name: str = "world") -> str:
    """测试工具：返回问候语，用于验证 MCP Server 与客户端链路。"""
    return f"hello, {name}!"


@mcp.tool()
def page_info() -> str:
    """读取 claude.ai 页面状态：URL、标题、输入框/发送钮是否存在。"""
    try:
        return asyncio.run(page_cmd("page_info"))
    except OSError as e:
        return f"page_info FAILED: 连不上桥接服务 {INTERNAL_WS}（{e}），请先启动 bridge_ws.py"


@mcp.tool()
def send_prompt(text: str, wait: bool = True, timeout_s: int = 150) -> str:
    """向 claude.ai 输入框填入文本并点击发送。

    wait=True（默认）时等 Claude 回复生成完成并直接返回回复文本；
    wait=False 只确认发送成功。timeout_s 是等回复的秒数上限。
    """
    payload = {"text": text, "wait": wait, "timeout_ms": timeout_s * 1000}
    try:
        return asyncio.run(page_cmd("send_prompt", payload, timeout=max(PAGE_TIMEOUT, timeout_s + 30)))
    except OSError as e:
        return f"send_prompt FAILED: 连不上桥接服务 {INTERNAL_WS}（{e}），请先启动 bridge_ws.py"


@mcp.tool()
def get_reply() -> str:
    """抓取 claude.ai 页面上最后一条 Claude 回复文本（最多 4000 字符）。"""
    try:
        return asyncio.run(page_cmd("get_reply"))
    except OSError as e:
        return f"get_reply FAILED: 连不上桥接服务 {INTERNAL_WS}（{e}），请先启动 bridge_ws.py"


if __name__ == "__main__":
    mcp.run()  # stdio 传输，供本地 AI 客户端连接
