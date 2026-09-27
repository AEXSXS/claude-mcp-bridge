// Claude MCP Bridge - background (Firefox MV3 event page)
// Phase 2: WebSocket 连接 wss://127.0.0.1:8765，断线自动重连。
// 时序修复：WS 未就绪时消息入队，onopen 统一冲刷（原逻辑直接丢弃导致
// content 的 ping 在 CONNECTING 阶段被丢，握手成功后无任何收发）。

const WS_URL = "wss://127.0.0.1:8765";
const RECONNECT_MS = 3000;
const QUEUE_LIMIT = 50;

let ws = null;
let retryTimer = null;
let sendQueue = [];

const READY_STATE = ["CONNECTING", "OPEN", "CLOSING", "CLOSED"];

function scheduleReconnect(reason) {
  console.log(`[claude-mcp-bridge] WS closed (${reason}), retry in ${RECONNECT_MS}ms`);
  if (retryTimer) return;
  retryTimer = setTimeout(() => {
    retryTimer = null;
    connect();
  }, RECONNECT_MS);
}

function connect() {
  const existing = ws ? READY_STATE[ws.readyState] : "none";
  console.log(`[claude-mcp-bridge] connect() called, existing ws readyState: ${existing}`);
  if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
    console.warn("[claude-mcp-bridge] already have an active/connecting ws, skip duplicate connect");
    return;
  }
  try {
    ws = new WebSocket(WS_URL);
  } catch (e) {
    console.error("[claude-mcp-bridge] WS create failed:", e);
    scheduleReconnect("create failed");
    return;
  }
  ws.onopen = () => {
    console.log("[claude-mcp-bridge] WS connected:", WS_URL);
    // 冲刷积压消息（含重连场景），然后自发一次 ping 验证链路
    const pending = sendQueue.splice(0);
    for (const raw of pending) {
      ws.send(raw);
      console.log("[claude-mcp-bridge] flushed queued:", raw);
    }
    send({ type: "ping" });
  };
  ws.onerror = (e) => console.error("[claude-mcp-bridge] WS error:", e);
  ws.onclose = () => scheduleReconnect("closed");
  ws.onmessage = (ev) => {
    console.log("[claude-mcp-bridge] WS message:", ev.data);
    try {
      const msg = JSON.parse(ev.data);
      if (msg.type === "pong") console.log("[claude-mcp-bridge] pong received");
      if (msg.type === "echo_reply") console.log("[claude-mcp-bridge] echo_reply:", msg.text);
    } catch (e) {
      console.warn("[claude-mcp-bridge] non-JSON message:", ev.data);
    }
  };
}

// 返回 true 表示已发出或已入队（都不丢）
function send(obj) {
  const raw = JSON.stringify(obj);
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(raw);
    console.log("[claude-mcp-bridge] sent:", raw);
    return true;
  }
  if (sendQueue.length < QUEUE_LIMIT) {
    sendQueue.push(raw);
    console.log(`[claude-mcp-bridge] WS not open, queued (${sendQueue.length}/${QUEUE_LIMIT}):`, raw);
    return true;
  }
  console.warn("[claude-mcp-bridge] queue full, drop:", raw);
  return false;
}

browser.runtime.onMessage.addListener((msg) => {
  if (msg && msg.type === "bridge-ping") {
    return Promise.resolve({ sent: send({ type: "ping" }) });
  }
  if (msg && msg.type === "bridge-echo") {
    return Promise.resolve({ sent: send({ type: "echo", text: msg.text || "" }) });
  }
  return undefined;
});

connect();
