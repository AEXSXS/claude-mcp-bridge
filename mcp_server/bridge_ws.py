"""claude-mcp-bridge WebSocket bridge (Phase 2)

常驻本地 WebSocket 服务：ws://127.0.0.1:8765
供浏览器扩展连接，协议（JSON text frame）：
  收 {"type": "ping"}                    -> 回 {"type": "pong"}
  收 {"type": "echo", "text": "..."}     -> 回 {"type": "echo_reply", "text": "..."}
  收其他/非法                            -> 回 {"type": "error", "error": "..."}

MCP stdio 入口见 server.py，两者为独立进程，互不阻塞。
启动：python bridge_ws.py
"""

import asyncio
import json

import websockets

HOST = "127.0.0.1"
PORT = 8765


async def handler(ws) -> None:
    peer = ws.remote_address
    print(f"[bridge-ws] client connected: {peer}", flush=True)
    try:
        async for raw in ws:
            print(f"[bridge-ws] recv: {raw}", flush=True)
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                reply = {"type": "error", "error": "invalid json"}
            else:
                t = msg.get("type") if isinstance(msg, dict) else None
                if t == "ping":
                    reply = {"type": "pong"}
                elif t == "echo":
                    reply = {"type": "echo_reply", "text": msg.get("text", "")}
                else:
                    reply = {"type": "error", "error": f"unknown type: {t}"}
            out = json.dumps(reply, ensure_ascii=False)
            print(f"[bridge-ws] send: {out}", flush=True)
            await ws.send(out)
    except websockets.ConnectionClosed as e:
        print(f"[bridge-ws] client closed: {peer} ({e})", flush=True)
    finally:
        print(f"[bridge-ws] client removed: {peer}", flush=True)


async def main() -> None:
    async with websockets.serve(handler, HOST, PORT):
        print(f"[bridge-ws] listening on ws://{HOST}:{PORT}", flush=True)
        await asyncio.Future()  # run forever


if __name__ == "__main__":
    asyncio.run(main())
