// Claude MCP Bridge - content script (https://claude.ai/*)
// Phase 3: DOM 交互层。接收 background 转发的 page_cmd，执行后返回结果。
// 动作：page_info / fill_prompt / click_send / send_prompt / get_reply

console.log("[claude-mcp-bridge] content script injected:", location.href);

(function showInjectBanner() {
  const banner = document.createElement("div");
  banner.textContent = "Claude MCP Bridge 已注入";
  banner.style.cssText = [
    "position:fixed",
    "top:8px",
    "right:8px",
    "z-index:2147483647",
    "padding:6px 12px",
    "background:rgba(200,30,30,0.75)",
    "color:#fff",
    "font-size:13px",
    "border-radius:4px",
    "pointer-events:none",
    "box-shadow:0 2px 6px rgba(0,0,0,0.3)",
  ].join(";");
  document.documentElement.appendChild(banner);
  setTimeout(() => banner.remove(), 3000);
})();

// Phase 2: 触发 background 经 WebSocket 发一次 ping，验证 content -> background -> Server 全链路
// DeadObject 兜底：background event page 刚被唤醒时 sendMessage 可能失败，重试最多 2 次
if (typeof browser !== "undefined" && browser.runtime && browser.runtime.sendMessage) {
  const pingBackground = (attempt = 0) => {
    browser.runtime
      .sendMessage({ type: "bridge-ping" })
      .then((res) => console.log("[claude-mcp-bridge] ping via background:", res))
      .catch((e) => {
        console.warn(`[claude-mcp-bridge] ping failed (attempt ${attempt + 1}/3):`, e);
        if (attempt < 2) setTimeout(() => pingBackground(attempt + 1), 600);
      });
  };
  pingBackground();
}

// ---------- Phase 3: DOM 动作 ----------

function chatInput() {
  return document.querySelector('[data-testid="chat-input"]');
}

function sendButton() {
  return document.querySelector('[data-testid="chat-input-send"]');
}

// ProseMirror contenteditable 填字：多方案逐级退回，每步带诊断
const norm = (s) => (s || "").replace(/\s+/g, " ").trim();

function fillPrompt(text) {
  const el = chatInput();
  if (!el) throw new Error("chat-input not found");
  const diag = { focused: el.contains(document.activeElement) || document.activeElement === el };
  const done = () => norm(el.textContent) === norm(text);

  el.focus();
  diag.focused = el.contains(document.activeElement) || document.activeElement === el;

  // 方案1：selectAll + insertText（走 beforeinput，React/PM 通常同步）
  document.execCommand("selectAll", false, null);
  let ok = document.execCommand("insertText", false, text);
  diag.s1_execCommand = { ok, content: (el.textContent || "").slice(0, 80) };
  if (ok && done()) { diag.hit = 1; return diag; }

  // 方案2：直接写 DOM + input 事件（ProseMirror MutationObserver 会接管变更）
  el.textContent = text;
  el.dispatchEvent(new InputEvent("input", {
    bubbles: true, cancelable: true, inputType: "insertText", data: text,
  }));
  diag.s2_directDOM = { content: (el.textContent || "").slice(0, 80) };
  if (done()) { diag.hit = 2; return diag; }

  // 方案3：合成 paste 事件
  try {
    const dt = new DataTransfer();
    dt.setData("text/plain", text);
    el.dispatchEvent(new ClipboardEvent("paste", {
      clipboardData: dt, bubbles: true, cancelable: true,
    }));
    diag.s3_paste = { content: (el.textContent || "").slice(0, 80) };
  } catch (e) {
    diag.s3_paste = { error: String(e) };
  }
  if (done()) { diag.hit = 3; return diag; }

  diag.final = (el.textContent || "").slice(0, 200);
  const err = new Error("fill failed: editor did not accept text");
  err.diag = JSON.stringify(diag);
  throw err;
}

function clickSend() {
  const btn = sendButton();
  if (!btn) throw new Error("send button not found");
  if (btn.disabled) throw new Error("send button is disabled (input empty or sending)");
  btn.click();
  return { clicked: true };
}

// 抓最后一条 Claude 回复。选择器按优先级尝试，DOM 变版时兜底 article
function readLastReply() {
  const sels = [
    '[data-testid="assistant-message"]',
    "article .font-claude-message",
    ".font-claude-message",
    "main article",
  ];
  for (const sel of sels) {
    const nodes = document.querySelectorAll(sel);
    if (nodes.length) {
      const last = nodes[nodes.length - 1];
      const text = (last.innerText || "").trim();
      if (text) return { selector: sel, count: nodes.length, text };
    }
  }
  return null;
}

function getLastReply() {
  const r = readLastReply();
  if (!r) throw new Error("no reply text found (page may have no conversation yet)");
  return {
    selector: r.selector,
    count: r.count,
    text: r.text.slice(0, 4000),
    truncated: r.text.length > 4000,
  };
}

// 等 Claude 生成完：轮询最后一条回复文本，连续 3 次采样不变且与发送前基线
// 不同（说明出现了新回复）即认为完成。不依赖 Stop 按钮等易变 UI 特征。
async function waitForReply(prevText, timeoutMs = 150000) {
  const start = Date.now();
  let last = "";
  let stable = 0;
  while (Date.now() - start < timeoutMs) {
    await new Promise((r) => setTimeout(r, 1200));
    let cur = "";
    try {
      cur = readLastReply()?.text || "";
    } catch (_) {
      cur = "";
    }
    if (cur && cur === last) {
      stable++;
      if (stable >= 3 && cur !== prevText) return cur;
    } else {
      stable = 0;
    }
    last = cur;
  }
  throw new Error(`timeout waiting for reply (${timeoutMs}ms)`);
}

async function handlePageAction(action, payload) {
  console.log("[claude-mcp-bridge] page action:", action, payload);
  try {
    let data;
    if (action === "page_info") {
      data = {
        url: location.href,
        title: document.title,
        readyState: document.readyState,
        hasChatInput: !!chatInput(),
        hasSendButton: !!sendButton(),
      };
    } else if (action === "fill_prompt") {
      data = fillPrompt(String(payload.text || ""));
    } else if (action === "click_send") {
      data = clickSend();
    } else if (action === "send_prompt") {
      const prevText = readLastReply()?.text || ""; // 基线：发送前的最后一条回复
      data = fillPrompt(String(payload.text || ""));
      await new Promise((r) => setTimeout(r, 350)); // 等 React 状态刷新启用发送钮
      data.send = clickSend();
      if (payload.wait) {
        const reply = await waitForReply(prevText, Number(payload.timeout_ms) || 150000);
        data.reply = { text: reply.slice(0, 4000), truncated: reply.length > 4000 };
      }
    } else if (action === "get_reply") {
      data = getLastReply();
    } else {
      throw new Error(`unknown action: ${action}`);
    }
    console.log("[claude-mcp-bridge] page action ok:", action);
    return { ok: true, data };
  } catch (e) {
    console.warn("[claude-mcp-bridge] page action failed:", action, e);
    const extra = e && e.diag ? " | diag=" + e.diag : "";
    return { ok: false, error: String((e && e.message) || e) + extra };
  }
}

if (typeof browser !== "undefined" && browser.runtime && browser.runtime.onMessage) {
  browser.runtime.onMessage.addListener((msg) => {
    if (!msg || msg.type !== "bridge-page-cmd") return undefined;
    return Promise.resolve(handlePageAction(msg.action, msg.payload || {}));
  });
}

// 心跳保活：event page 空闲会被 Firefox 回收（WS 随之断开，服务端广播无人收）。
// 页面开着时每 20s 发一次 keepalive 重置空闲计时；background 若被重建，
// sendMessage 失败后下一轮自然恢复。
if (typeof browser !== "undefined" && browser.runtime && browser.runtime.sendMessage) {
  setInterval(() => {
    browser.runtime
      .sendMessage({ type: "bridge-keepalive" })
      .then((res) => {
        if (res?.ws !== "OPEN") {
          console.log("[claude-mcp-bridge] keepalive: background ws =", res?.ws);
        }
      })
      .catch((e) => console.warn("[claude-mcp-bridge] keepalive failed:", e.message || e));
  }, 20000);
}
