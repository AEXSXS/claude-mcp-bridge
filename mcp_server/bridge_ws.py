"""claude-mcp-bridge WebSocket bridge (Phase 3, wss)

为什么是 wss：WebExtension 默认 CSP 含 upgrade-insecure-requests，Firefox/Chrome
会把扩展 background 页面里的 ws:// 强制升级为 wss://，明文 ws 永远收不到合法握手。
所以对外端口直接做 TLS 终结（自签证书，SAN: 127.0.0.1 / localhost）。

架构：
  扩展 --wss://127.0.0.1:8765--> [TLS 中继(窥探日志)] --ws--> 127.0.0.1:8766 [websockets]
  MCP server.py / 其他客户端 --ws--> 127.0.0.1:8766（同一内部端口）

首次使用需在 Firefox 给证书加例外：浏览器打开 https://127.0.0.1:8765
-> 高级 -> 接受风险并继续（例外入库后 wss 连接同样生效）。

协议（JSON text frame）：
  {"type": "ping"}                -> {"type": "pong"}
  {"type": "echo", "text": "..."} -> {"type": "echo_reply", "text": "..."}
  {"type": "page_cmd", "id": "...", "action": "...", "payload": {...}}
      -> 广播给所有连接（扩展收到后转发 claude.ai 标签页执行）
  {"type": "page_result", "id": "...", "ok": true, "data": {...}}
      -> 匹配 pending 的 page_cmd，完成一次请求-响应往返
  其他                            -> {"type": "error", "error": "..."}

启动：python bridge_ws.py [--port 8765] [--internal-port 8766]
"""

import argparse
import asyncio
import json
import logging
import ssl
import uuid
from pathlib import Path

import websockets

SNIFF_TIMEOUT = 1.0   # 等第一段字节的秒数
SNIFF_SIZE = 512      # 抓取字节数上限
CERT_DIR = Path(__file__).parent / "certs"


def build_ssl_context() -> ssl.SSLContext:
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(CERT_DIR / "server.crt", CERT_DIR / "server.key")
    return ctx


class Hub:
    """连接注册表 + page_cmd 请求-响应匹配。"""

    def __init__(self) -> None:
        self.clients: set = set()
        self.pending: dict = {}  # id -> asyncio.Future

    async def broadcast(self, text: str) -> None:
        for c in list(self.clients):
            try:
                await c.send(text)
            except websockets.ConnectionClosed:
                pass


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


async def ws_handler(ws, hub: Hub) -> None:
    peer = ws.remote_address
    hub.clients.add(ws)
    print(f"[bridge-ws] handshake OK, client: {peer} (total {len(hub.clients)})", flush=True)
    try:
        async for raw in ws:
            print(f"[bridge-ws] recv: {raw}", flush=True)
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                reply = {"type": "error", "error": "invalid json"}
                print(f"[bridge-ws] send: {json.dumps(reply)}", flush=True)
                await ws.send(json.dumps(reply))
                continue

            t = msg.get("type") if isinstance(msg, dict) else None
            if t == "ping":
                await ws.send(json.dumps({"type": "pong"}))
            elif t == "echo":
                await ws.send(json.dumps({"type": "echo_reply", "text": msg.get("text", "")}))
            elif t == "page_cmd":
                cmd_id = msg.get("id") or uuid.uuid4().hex[:8]
                req_timeout = min(float(msg.get("timeout", 30)), 300)  # 等生成最长 5 分钟
                fut = asyncio.get_running_loop().create_future()
                hub.pending[cmd_id] = fut
                await hub.broadcast(json.dumps(
                    {"type": "page_cmd", "id": cmd_id,
                     "action": msg.get("action"), "payload": msg.get("payload", {})},
                    ensure_ascii=False))
                try:
                    result = await asyncio.wait_for(fut, timeout=req_timeout)
                except asyncio.TimeoutError:
                    result = {"type": "page_result", "id": cmd_id,
                              "ok": False, "error": f"timeout ({req_timeout:.0f}s), no page_result"}
                finally:
                    hub.pending.pop(cmd_id, None)
                out = json.dumps(result, ensure_ascii=False)
                print(f"[bridge-ws] send: {out}", flush=True)
                await ws.send(out)
            elif t == "page_result":
                fut = hub.pending.get(msg.get("id"))
                if fut and not fut.done():
                    fut.set_result(msg)
                    print(f"[bridge-ws] page_result matched: {msg.get('id')}", flush=True)
            else:
                reply = {"type": "error", "error": f"unknown type: {t}"}
                print(f"[bridge-ws] send: {json.dumps(reply)}", flush=True)
                await ws.send(json.dumps(reply))
    except websockets.ConnectionClosed as e:
        print(f"[bridge-ws] client closed: {peer} ({e})", flush=True)
    finally:
        hub.clients.discard(ws)
        print(f"[bridge-ws] client removed: {peer} (total {len(hub.clients)})", flush=True)


async def main(port: int, internal_port: int) -> None:
    logging.basicConfig(level=logging.INFO, format="[ws-lib] %(name)s %(levelname)s %(message)s")
    ssl_ctx = build_ssl_context()
    hub = Hub()

    async def serve_ws() -> None:
        async with websockets.serve(lambda ws: ws_handler(ws, hub), "127.0.0.1", internal_port):
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
