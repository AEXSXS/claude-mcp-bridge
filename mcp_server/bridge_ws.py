"""claude-mcp-bridge WebSocket bridge (Phase 2, wss)

为什么是 wss：WebExtension 默认 CSP 含 upgrade-insecure-requests，Firefox/Chrome
会把扩展 background 页面里的 ws:// 强制升级为 wss://，明文 ws 永远收不到合法握手。
所以对外端口直接做 TLS 终结（自签证书，SAN: 127.0.0.1 / localhost）。

架构：
  扩展 --wss://127.0.0.1:8765--> [TLS 中继(窥探日志)] --ws--> 127.0.0.1:8766 [websockets]

首次使用需在 Firefox 给证书加例外：浏览器打开 https://127.0.0.1:8765
-> 高级 -> 接受风险并继续（例外入库后 wss 连接同样生效）。

协议（JSON text frame）：
  {"type": "ping"}                -> {"type": "pong"}
  {"type": "echo", "text": "..."} -> {"type": "echo_reply", "text": "..."}
  其他                            -> {"type": "error", "error": "..."}

MCP stdio 入口见 server.py，两者为独立进程。
启动：python bridge_ws.py [--port 8765] [--internal-port 8766]
"""

import argparse
import asyncio
import json
import logging
import ssl
from pathlib import Path

import websockets

SNIFF_TIMEOUT = 1.0   # 等第一段字节的秒数
SNIFF_SIZE = 512      # 抓取字节数上限
CERT_DIR = Path(__file__).parent / "certs"


def build_ssl_context() -> ssl.SSLContext:
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(CERT_DIR / "server.crt", CERT_DIR / "server.key")
    return ctx


async def relay(
    client_reader: asyncio.StreamReader,
    client_writer: asyncio.StreamWriter,
    internal_port: int,
) -> None:
    peer = client_writer.get_extra_info("peername")
    print(f"[diag] new TLS connection from {peer}", flush=True)

    try:
        head = await asyncio.wait_for(client_reader.read(SNIFF_SIZE), timeout=SNIFF_TIMEOUT)
    except asyncio.TimeoutError:
        head = b""
    except (ConnectionError, OSError, ssl.SSLError) as e:
        print(f"[diag] {peer} read failed before sniff: {e!r}", flush=True)
        client_writer.close()
        return
    if head:
        print(f"[diag] {peer} first {len(head)} byte(s): {head[:200]!r}", flush=True)
    else:
        print(f"[diag] {peer} sent 0 byte(s) within {SNIFF_TIMEOUT}s", flush=True)

    try:
        up_reader, up_writer = await asyncio.open_connection("127.0.0.1", internal_port)
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


async def main(port: int, internal_port: int) -> None:
    logging.basicConfig(level=logging.INFO, format="[ws-lib] %(name)s %(levelname)s %(message)s")
    ssl_ctx = build_ssl_context()

    async def serve_ws() -> None:
        async with websockets.serve(ws_handler, "127.0.0.1", internal_port):
            print(f"[bridge-ws] internal ws listening on 127.0.0.1:{internal_port}", flush=True)
            await asyncio.Future()

    async def serve_relay() -> None:
        server = await asyncio.start_server(
            lambda r, w: relay(r, w, internal_port), "127.0.0.1", port, ssl=ssl_ctx
        )
        print(f"[diag] public wss relay listening on wss://127.0.0.1:{port} (sniff {SNIFF_SIZE}B/{SNIFF_TIMEOUT}s)", flush=True)
        async with server:
            await asyncio.Future()

    await asyncio.gather(serve_ws(), serve_relay())


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--internal-port", type=int, default=8766)
    args = ap.parse_args()
    asyncio.run(main(args.port, args.internal_port))
