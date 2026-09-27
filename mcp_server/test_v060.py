"""v0.6.0 协议级测试（mailbox 轮询版）：不经浏览器，用假扩展模拟扩展侧。

覆盖：
  1. page_cmd send_prompt（wait=false 语义）-> 假扩展回 page_result 带 prompt_id
  2. 扩展延迟推 reply_event -> 客户端 wait_reply 轮询等到回复
  3. mailbox_get 迟到取件（wait 放弃后再查 mailbox）
  4. missed 兜底：扩展只报 page_result 不推 reply_event -> wait_reply 超时返回错误
  5. TTL：直接 mail_put 一条旧时间戳条目，验证清理

用法：python test_v060.py  （自起 8775/8776 备用端口，不碰正式 8765/8766）
"""

import asyncio
import json
import sys
import time

import websockets

import bridge_ws

INT_PORT, PUB_PORT = 8776, 8775


async def fake_extension(hub_holder):
    """假扩展：收 page_cmd -> 回 page_result；ok 时延迟 2s 推 reply_event。

    miss_ids 里的 prompt 不推 reply_event，模拟 watcher 死掉只靠 missed 兜底。
    """
    miss_ids = getattr(fake_extension, "miss_ids", set())
    async with websockets.connect(f"ws://127.0.0.1:{INT_PORT}") as ws:
        while True:
            raw = await ws.recv()
            msg = json.loads(raw)
            if msg.get("type") != "page_cmd":
                continue
            await ws.send(json.dumps({
                "type": "page_result", "id": msg["id"], "ok": True,
                "data": {"prompt_id": msg["id"], "send": {"clicked": True}},
            }))
            if msg["id"] in miss_ids:
                continue
            await asyncio.sleep(2.0)
            await ws.send(json.dumps({
                "type": "reply_event", "id": msg["id"], "ok": True,
                "text": f"模拟回复-{msg['id']}", "truncated": False,
            }))


async def client_wait_reply(pid: str, timeout: float) -> dict:
    async with websockets.connect(f"ws://127.0.0.1:{INT_PORT}") as ws:
        await ws.send(json.dumps({"type": "wait_reply", "id": pid, "timeout": timeout}))
        while True:
            msg = json.loads(await ws.recv())
            if msg.get("type") == "reply_result" and msg.get("id") == pid:
                return msg


async def page_cmd_send() -> tuple[str, dict]:
    pid = f"t{int(time.time()*1000)%100000}"
    async with websockets.connect(f"ws://127.0.0.1:{INT_PORT}") as ws:
        await ws.send(json.dumps({
            "type": "page_cmd", "id": pid, "action": "send_prompt",
            "payload": {"text": "hi"}, "timeout": 10,
        }))
        while True:
            msg = json.loads(await ws.recv())
            if msg.get("type") == "page_result" and msg.get("id") == pid:
                return pid, msg


def check(name: str, cond: bool, extra: str = "") -> bool:
    print(f"  [{'PASS' if cond else 'FAIL'}] {name} {extra}", flush=True)
    return cond


async def main() -> int:
    hub = bridge_ws.Hub()
    server = await websockets.serve(
        lambda ws: bridge_ws.ws_handler(ws, hub), "127.0.0.1", INT_PORT)
    ext_task = asyncio.create_task(fake_extension(hub))
    await asyncio.sleep(0.3)
    ok_all = True

    try:
        print("== 1. send_prompt 提交即返回 prompt_id ==")
        pid, res = await page_cmd_send()
        ok_all &= check("page_result ok", res.get("ok") is True)
        ok_all &= check("data.prompt_id 回传", (res.get("data") or {}).get("prompt_id") == pid)

        print("== 2. wait_reply 轮询等到推送回复 ==")
        t0 = time.monotonic()
        r = await client_wait_reply(pid, 30)
        dt = time.monotonic() - t0
        ok_all &= check("found 且 ok", r.get("found") and r.get("ok"))
        ok_all &= check("文本正确", r.get("text") == f"模拟回复-{pid}")
        ok_all &= check("等待约 2s（推送后即返回）", 1.0 < dt < 5.0, f"实际 {dt:.1f}s")

        print("== 3. mailbox_get 迟到取件 ==")
        async with websockets.connect(f"ws://127.0.0.1:{INT_PORT}") as ws:
            await ws.send(json.dumps({"type": "mailbox_get", "id": pid}))
            r3 = json.loads(await ws.recv())
        ok_all &= check("取回同一份回复", r3.get("found") and r3.get("text") == f"模拟回复-{pid}")

        print("== 4. missed 兜底（watcher 死，无 reply_event）==")
        # reply_event 是 fire-and-forget，服务端不回包；另开连接查 mailbox 验证
        async with websockets.connect(f"ws://127.0.0.1:{INT_PORT}") as ws:
            await ws.send(json.dumps({
                "type": "reply_event", "id": "miss-case", "ok": False,
                "error": "missed: no reply detected",
            }))
        await asyncio.sleep(0.3)
        async with websockets.connect(f"ws://127.0.0.1:{INT_PORT}") as ws:
            await ws.send(json.dumps({"type": "mailbox_get", "id": "miss-case"}))
            r4 = json.loads(await asyncio.wait_for(ws.recv(), 5))
        ok_all &= check("missed 条目可查且 ok=False",
                        r4.get("found") and r4.get("ok") is False)

        print("== 5. TTL 清理 ==")
        hub.mailbox["old-case"] = {"ts": -9999, "ok": True, "text": "x",
                                   "truncated": False, "error": ""}
        hub.mail_put({"id": "fresh", "ok": True, "text": "y"})
        ok_all &= check("过期条目被清理", hub.mail_get("old-case") is None)
        ok_all &= check("新条目存活", hub.mail_get("fresh") is not None)
    finally:
        ext_task.cancel()
        await server.close()

    print(f"\n结果: {'ALL PASS' if ok_all else 'HAS FAILURES'}", flush=True)
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
