"""claude-mcp-bridge WebSocket bridge (Phase 2 + 诊断层)

对外监听 ws://127.0.0.1:8765（扩展连接此端口）。
对外端口前面加了一层"字节窥探中继"（诊断用）：
  - 打印每个新连接的 remote_address
  - 握手前抓取对端发来的第一段原始字节（含 0 字节情形）并打印 repr
  - 字节原样转发给内部 websockets 服务（127.0.0.1:8766），不影响正常握手
目的：排查 "opening handshake failed / did not receive a valid HTTP request"，
看清对端到底发来了什么（空字节 / TLS ClientHello / HTTP CONNECT / 乱码）。

协议（JSON text frame，由内部 websockets 服务处理）：
  {"type": "ping"}                -> {"type": "pong"}
  {"type": "echo", "text": "..."} -> {"type": "echo_reply", "text": "..."}
  其他                            -> {"type": "error", "error": "..."}

MCP stdio 入口见 server.py，两者为独立进程。
启动：python bridge_ws.py
"""

import asyncio
import json
import logging

import websockets

PUBLIC_HOST, PUBLIC_PORT = "127.0.0.1", 8765   # 对外：扩展连这里（诊断中继）
INTERNAL_HOST, INTERNAL_PORT = "127.0.0.1", 8766  # 对内：websockets 真正监听
SNIFF_TIMEOUT = 1.0   # 等第一段字节的秒数
SNIFF_SIZE = 512      # 抓取字节数上限


async def relay(client_reader: asyncio.StreamReader, client_writer: asyncio.StreamWriter) -> None:
    peer = client_writer.get_extra_info("peername")
    print(f"[diag] new connection from {peer}", flush=True)

    try:
        head = await asyncio.wait_for(client_reader.read(SNIFF_SIZE), timeout=SNIFF_TIMEOUT)
    except asyncio.TimeoutError:
        head = b""
    except ConnectionError as e:
        print(f"[diag] {peer} read failed before sniff: {e!r}", flush=True)
        client_writer.close()
        return
    print(f"[diag] {peer} first {len(head)} byte(s): {head[:200]!r}", flush=True)

    try:
        up_reader, up_writer = await asyncio.open_connection(INTERNAL_HOST, INTERNAL_PORT)
    except OSError as e:
        print(f"[diag] {peer} upstream connect failed: {e!r}", flush=True)
        client_writer.close()
        return
    if head:
        up_writer.write(head)
        await up_writer.drain()

    async def c2u() -> None:
        try:
            while True:
                data = await client_reader.read(4096)
                if not data:
                    break
                up_writer.write(data)
                await up_writer.drain()
        except (ConnectionError, OSError):
            pass
        finally:
            up_writer.close()

    async def u2c() -> None:
        try:
            while True:
                data = await up_reader.read(4096)
                if not data:
                    break
                client_writer.write(data)
                await client_writer.drain()
        except (ConnectionError, OSError):
            pass
        finally:
            client_writer.close()

    await asyncio.gather(c2u(), u2c())
    print(f"[diag] connection closed: {peer}", flush=True)


async def ws_handler(ws) -> None:
    peer = ws.remote_address
    print(f"[bridge-ws] handshake OK, client: {peer}", flush=True)
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
    logging.basicConfig(level=logging.INFO, format="[ws-lib] %(name)s %(levelname)s %(message)s")

    async def serve_ws() -> None:
        async with websockets.serve(ws_handler, INTERNAL_HOST, INTERNAL_PORT):
            print(f"[bridge-ws] internal ws listening on {INTERNAL_HOST}:{INTERNAL_PORT}", flush=True)
            await asyncio.Future()

    async def serve_relay() -> None:
        server = await asyncio.start_server(relay, PUBLIC_HOST, PUBLIC_PORT)
        print(f"[diag] public relay listening on {PUBLIC_HOST}:{PUBLIC_PORT} (sniff {SNIFF_SIZE}B/{SNIFF_TIMEOUT}s)", flush=True)
        async with server:
            await asyncio.Future()

    await asyncio.gather(serve_ws(), serve_relay())


if __name__ == "__main__":
    asyncio.run(main())
