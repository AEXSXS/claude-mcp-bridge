"""临时测试：从内部端口 8766 发 page_cmd，验证 真实扩展 -> claude.ai 页面 全链路。"""
import asyncio
import json
import uuid

import websockets

INTERNAL_WS = "ws://127.0.0.1:8766"


async def page_cmd(action: str, payload: dict | None = None, timeout: float = 20.0):
    cmd_id = uuid.uuid4().hex[:8]
    req = {"type": "page_cmd", "id": cmd_id, "action": action,
           "payload": payload or {}, "timeout": timeout}
    async with websockets.connect(INTERNAL_WS, max_size=2**22) as ws:
        await ws.send(json.dumps(req))
        deadline = asyncio.get_event_loop().time() + timeout
        while True:
            remain = deadline - asyncio.get_event_loop().time()
            if remain <= 0:
                return f"[{action}] TIMEOUT {timeout}s"
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=remain)
            except (asyncio.TimeoutError, TimeoutError):
                return f"[{action}] TIMEOUT {timeout}s"
            msg = json.loads(raw)
            if msg.get("type") == "page_result" and msg.get("id") == cmd_id:
                return f"[{action}] " + ("OK: " + json.dumps(msg.get("data"), ensure_ascii=False)
                                         if msg.get("ok") else "FAILED: " + str(msg.get("error")))


async def main():
    print(await page_cmd("send_prompt", {
        "text": "这是一条链路测试消息。请只回复六个字：链路测试成功",
        "wait": True,
        "timeout_ms": 150000,
    }, timeout=180))


if __name__ == "__main__":
    asyncio.run(main())
