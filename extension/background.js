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
      if (msg.type === "page_cmd") handlePageCmd(msg);
    } catch (e) {
      console.warn("[claude-mcp-bridge] non-JSON message:", ev.data);
    }
  };
}

// v0.6.0: 单飞锁（同一 tab 有 send_prompt 在途时拒绝新请求）+ missed 计时器
// + reply_event 转发（content watcher 判定完成 / missed 兜底，二选一必达 mailbox）
const inFlight = new Map(); // tabId -> { id, timer }

function clearInFlight(tabId, id) {
  const cur = inFlight.get(tabId);
  if (cur && (!id || cur.id === id)) {
    if (cur.timer) clearTimeout(cur.timer);
    inFlight.delete(tabId);
  }
}

// Phase 3: page_cmd 路由 -> claude.ai 标签页 content script 执行 -> page_result 回传
async function handlePageCmd(msg) {
  const id = msg.id;
  let tab = null;
  let locked = false; // 本次调用是否已占位（只清理自己的锁，不动别人的）
  try {
    const tabs = await browser.tabs.query({ url: "https://claude.ai/*" });
    if (!tabs.length) throw new Error("no claude.ai tab open");
    tab = tabs.find((t) => t.active) || tabs[0];
    if (msg.action === "send_prompt") {
      if (inFlight.has(tab.id)) {
        const busyId = inFlight.get(tab.id).id;
        throw new Error(`busy: prompt ${busyId} still in flight on this tab (single-flight lock)`);
      }
      // 同步占位：消除"检查-上锁"之间隔整个 sendMessage（350ms+）的并发窗口
      inFlight.set(tab.id, { id, timer: null });
      locked = true;
    }
    const res = await browser.tabs.sendMessage(tab.id, {
      type: "bridge-page-cmd",
      id,
      action: msg.action,
      payload: msg.payload || {},
    });
    console.log("[claude-mcp-bridge] page_cmd result:", msg.action, res);
    if (msg.action === "send_prompt") {
      if (res?.ok) {
        // missed 兜底：content 死掉无法自报，background 独立计时，超时主动报 missed
        const timeoutMs = Number(msg.payload?.timeout_ms) || 150000;
        const timer = setTimeout(() => {
          const cur = inFlight.get(tab.id);
          if (cur && cur.id === id) {
            inFlight.delete(tab.id);
            send({
              type: "reply_event", id, ok: false,
              error: `missed: no reply detected within ${timeoutMs}ms (tab closed or watcher died)`,
            });
          }
        }, timeoutMs + 30000);
        inFlight.set(tab.id, { id, timer }); // 补挂计时器到已占位条目
      } else {
        clearInFlight(tab.id, id); // content 执行失败（如点击被拒），释放锁
      }
    }
    send({ type: "page_result", id, ok: !!res?.ok, data: res?.data, error: res?.error });
  } catch (e) {
    if (locked && tab) clearInFlight(tab.id, id);
    console.error("[claude-mcp-bridge] page_cmd routing failed:", e);
    send({ type: "page_result", id, ok: false, error: String((e && e.message) || e) });
  }
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

browser.runtime.onMessage.addListener((msg, sender) => {
  if (msg && msg.type === "bridge-ping") {
    return Promise.resolve({ sent: send({ type: "ping" }) });
  }
  if (msg && msg.type === "bridge-echo") {
    return Promise.resolve({ sent: send({ type: "echo", text: msg.text || "" }) });
  }
  if (msg && msg.type === "bridge-keepalive") {
    // content 每 20s 戳一次，重置 event page 空闲计时，防止 background 被回收
    return Promise.resolve({
      alive: true,
      ws: ws ? READY_STATE[ws.readyState] : "none",
    });
  }
  if (msg && msg.type === "bridge-reply-event") {
    // v0.6.0: content watcher 判定生成完成 -> 转发 reply_event 给 server mailbox
    const tabId = sender?.tab?.id;
    if (tabId !== undefined) clearInFlight(tabId, msg.id);
    send({
      type: "reply_event", id: msg.id, ok: !!msg.ok,
      text: msg.text, truncated: !!msg.truncated, error: msg.error,
    });
    return Promise.resolve({ forwarded: true });
  }
  return undefined;
});

connect();
