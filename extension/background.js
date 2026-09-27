// Claude MCP Bridge - background (Firefox MV3 event page)
// Phase 2: WebSocket 连接 ws://127.0.0.1:8765，断线自动重连。

const WS_URL = "wss://127.0.0.1:8765";
const RECONNECT_MS = 3000;

let ws = null;
let retryTimer = null;

function scheduleReconnect(reason) {
  console.log(`[claude-mcp-bridge] WS closed (${reason}), retry in ${RECONNECT_MS}ms`);
  if (retryTimer) return;
  retryTimer = setTimeout(() => {
    retryTimer = null;
    connect();
  }, RECONNECT_MS);
}

const READY_STATE = ["CONNECTING", "OPEN", "CLOSING", "CLOSED"];

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
  ws.onopen = () => console.log("[claude-mcp-bridge] WS connected:", WS_URL);
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

function send(obj) {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify(obj));
    console.log("[claude-mcp-bridge] sent:", JSON.stringify(obj));
    return true;
  }
  console.warn("[claude-mcp-bridge] WS not open, drop:", JSON.stringify(obj));
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
