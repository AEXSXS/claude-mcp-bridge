"""claude-mcp-bridge MCP Server (v0.6.0, 推送式)

工具：
  hello        链路测试
  page_info    读取 claude.ai 页面状态（是否开了新聊天页、输入框是否就绪）
  send_prompt  向输入框填文本并点发送；默认立即返回 prompt_id（不阻塞等生成）
  wait_reply   按 prompt_id 轮询等回复生成完成（扩展 watcher 检测，mailbox 送达）
  get_reply    取回复：带 prompt_id 走 mailbox（迟到取件），不带则现场抓页面最后一条

v0.6.0 架构（评审定稿：mailbox 轮询版，无 Future）：
  send_prompt 提交即返回 -> 扩展侧 content watcher 检测生成完成 ->
  background 推 reply_event -> bridge_ws 存 mailbox（TTL 10min）->
  wait_reply 轮询取件 / get_reply(id) 迟到取件。
  客户端超时放弃后，回复仍留在 mailbox，事后可用 get_reply 捞回。

通信：本进程作为 ws 客户端连 bridge_ws.py 的内部端口 ws://127.0.0.1:8766。
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
WAIT_CAP = 600.0  # wait_reply 最长等 10 分钟

mcp = MCPServer("claude-mcp-bridge")


async def ws_request(req: dict, recv_timeout: float,
                     want_type: str | None = None,
                     want_id: str | None = None) -> dict:
    """连内部端口发一条请求，等匹配的响应，返回原始 dict。

    page_cmd 会被 bridge_ws 广播给所有连接（含发送者自己），所以必须按
    type/id 过滤，否则会把自己的广播回声当成响应（旧版实现有此过滤）。
    """
    async with websockets.connect(INTERNAL_WS, max_size=2**22) as ws:
        await ws.send(json.dumps(req))
        deadline = asyncio.get_event_loop().time() + recv_timeout
        while True:
            remain = deadline - asyncio.get_event_loop().time()
            if remain <= 0:
                raise TimeoutError(f"{recv_timeout:.0f}s 内未收到 {req.get('type')} 的响应")
            raw = await asyncio.wait_for(ws.recv(), timeout=remain)
            msg = json.loads(raw)
            if msg.get("type") == "error":
                raise RuntimeError(msg.get("error"))
            if want_type and msg.get("type") != want_type:
                continue
            if want_id and msg.get("id") != want_id:
                continue
            return msg


async def page_cmd_raw(action: str, payload: dict | None = None,
                       timeout: float = PAGE_TIMEOUT) -> dict:
    """发 page_cmd，等 page_result，返回完整 dict（含 ok/data/error）。"""
    cmd_id = uuid.uuid4().hex[:8]
    req = {"type": "page_cmd", "id": cmd_id, "action": action,
           "payload": payload or {}, "timeout": timeout}
    msg = await ws_request(req, recv_timeout=max(timeout + 10, 40),
                           want_type="page_result", want_id=cmd_id)
    return msg


def fmt_result(action: str, msg: dict) -> str:
    if msg.get("ok"):
        return f"[{action}] OK: {json.dumps(msg.get('data'), ensure_ascii=False)}"
    return f"[{action}] FAILED: {msg.get('error')}"


async def page_cmd(action: str, payload: dict | None = None,
                   timeout: float = PAGE_TIMEOUT) -> str:
    try:
        return fmt_result(action, await page_cmd_raw(action, payload, timeout))
    except OSError as e:
        return f"{action} FAILED: 连不上桥接服务 {INTERNAL_WS}（{e}），请先启动 bridge_ws.py"


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


async def _send_prompt(text: str, wait: bool, timeout_s: int) -> str:
    # 提交阶段：快速返回，扩展侧只做填字+点发送（不挂长连接）
    msg = await page_cmd_raw("send_prompt", {"text": text}, timeout=PAGE_TIMEOUT)
    if not msg.get("ok"):
        return f"[send_prompt] FAILED: {msg.get('error')}"
    prompt_id = (msg.get("data") or {}).get("prompt_id", "")
    if not wait:
        return (f"[send_prompt] OK 已发送，prompt_id={prompt_id}。"
                f"回复生成后用 wait_reply(prompt_id) 等取，"
                f"或稍后 get_reply(prompt_id) 迟到取件。")
    # 等待阶段：bridge_ws 内部轮询 mailbox（扩展 watcher 负责检测完成）
    reply = await ws_request(
        {"type": "wait_reply", "id": prompt_id, "timeout": timeout_s},
        recv_timeout=min(float(timeout_s), WAIT_CAP) + 30,
        want_type="reply_result", want_id=prompt_id)
    if reply.get("found") and reply.get("ok"):
        return f"[send_prompt] 回复已到: {reply.get('text', '')}"
    return f"[wait_reply] FAILED: {reply.get('error')}"


@mcp.tool()
def send_prompt(text: str, wait: bool = False, timeout_s: int = 300) -> str:
    """向 claude.ai 输入框填入文本并点击发送。

    默认（wait=False）立即返回 prompt_id，不阻塞；
    之后用 wait_reply(prompt_id, timeout_s) 等回复，或 get_reply(prompt_id) 取件。
    wait=True 则本次调用内等完生成再返回（兼容旧用法，不推荐）。
    timeout_s 是等回复的秒数上限。
    """
    try:
        return asyncio.run(_send_prompt(text, wait, timeout_s))
    except OSError as e:
        return f"send_prompt FAILED: 连不上桥接服务 {INTERNAL_WS}（{e}），请先启动 bridge_ws.py"
    except TimeoutError as e:
        return f"send_prompt FAILED: {e}"


async def _wait_reply(prompt_id: str, timeout_s: int) -> str:
    reply = await ws_request(
        {"type": "wait_reply", "id": prompt_id, "timeout": timeout_s},
        recv_timeout=min(float(timeout_s), WAIT_CAP) + 30,
        want_type="reply_result", want_id=prompt_id)
    if reply.get("found"):
        if reply.get("ok"):
            return f"[wait_reply] 回复已到: {reply.get('text', '')}"
        return f"[wait_reply] FAILED: {reply.get('error')}"
    return f"[wait_reply] FAILED: {reply.get('error')}"


@mcp.tool()
def wait_reply(prompt_id: str, timeout_s: int = 300) -> str:
    """按 prompt_id 等待 Claude 回复生成完成并返回文本。

    bridge_ws 内部每秒轮询 mailbox；扩展 watcher 检测到生成完成即送达。
    若该 prompt 此前已有回复落在 mailbox（迟到取件），立即返回。
    客户端超时放弃后回复仍在 mailbox，可稍后再调本工具或 get_reply 捞回。
    """
    try:
        return asyncio.run(_wait_reply(prompt_id, timeout_s))
    except OSError as e:
        return f"wait_reply FAILED: 连不上桥接服务 {INTERNAL_WS}（{e}），请先启动 bridge_ws.py"
    except TimeoutError as e:
        return f"wait_reply FAILED: {e}"


async def _get_reply(prompt_id: str) -> str:
    if prompt_id:
        reply = await ws_request({"type": "mailbox_get", "id": prompt_id}, recv_timeout=40,
                                 want_type="reply_result", want_id=prompt_id)
        if reply.get("found"):
            tag = "回复已到" if reply.get("ok") else "该 prompt 失败"
            body = reply.get("text", "") or reply.get("error", "")
            return f"[get_reply] {tag}: {body}"
        return f"[get_reply] mailbox 中无此 prompt（从未送达或已被 TTL 清理）"
    # 无 id：退回旧行为，现场抓页面最后一条回复
    return await page_cmd("get_reply")


@mcp.tool()
def get_reply(prompt_id: str = "") -> str:
    """取 Claude 回复文本。

    带 prompt_id：查 mailbox 迟到取件（即使之前 wait 超时放弃过也能捞回）。
    不带：抓取 claude.ai 页面上最后一条 Claude 回复（最多 4000 字符）。
    """
    try:
        return asyncio.run(_get_reply(prompt_id))
    except OSError as e:
        return f"get_reply FAILED: 连不上桥接服务 {INTERNAL_WS}（{e}），请先启动 bridge_ws.py"


if __name__ == "__main__":
    mcp.run()  # stdio 传输，供本地 AI 客户端连接
