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

// ProseMirror contenteditable 填字：execCommand insertText 走 React 同步；
// 失败则退回 paste 事件（DataTransfer），再校验
function fillPrompt(text) {
  const el = chatInput();
  if (!el) throw new Error("chat-input not found");
  el.focus();
  // 清空已有内容
  document.execCommand("selectAll", false, null);
  let ok = document.execCommand("insertText", false, text);
  if (!ok || (el.textContent || "").trim() !== text.trim()) {
    const dt = new DataTransfer();
    dt.setData("text/plain", text);
    el.dispatchEvent(new ClipboardEvent("paste", {
      clipboardData: dt, bubbles: true, cancelable: true,
    }));
    ok = (el.textContent || "").trim() === text.trim();
  }
  if (!ok) throw new Error("fill failed: editor did not accept text");
  return { filled: text.length, preview: text.slice(0, 60) };
}

function clickSend() {
  const btn = sendButton();
  if (!btn) throw new Error("send button not found");
  if (btn.disabled) throw new Error("send button is disabled (input empty or sending)");
  btn.click();
  return { clicked: true };
}

// 抓最后一条 Claude 回复。选择器按优先级尝试，DOM 变版时兜底 article
function getLastReply() {
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
      if (text) {
        return {
          selector: sel,
          count: nodes.length,
          text: text.slice(0, 4000),
          truncated: text.length > 4000,
        };
      }
    }
  }
  throw new Error("no reply text found (page may have no conversation yet)");
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
      data = fillPrompt(String(payload.text || ""));
      await new Promise((r) => setTimeout(r, 350)); // 等 React 状态刷新启用发送钮
      data.send = clickSend();
    } else if (action === "get_reply") {
      data = getLastReply();
    } else {
      throw new Error(`unknown action: ${action}`);
    }
    console.log("[claude-mcp-bridge] page action ok:", action);
    return { ok: true, data };
  } catch (e) {
    console.warn("[claude-mcp-bridge] page action failed:", action, e);
    return { ok: false, error: String((e && e.message) || e) };
  }
}

if (typeof browser !== "undefined" && browser.runtime && browser.runtime.onMessage) {
  browser.runtime.onMessage.addListener((msg) => {
    if (!msg || msg.type !== "bridge-page-cmd") return undefined;
    return Promise.resolve(handlePageAction(msg.action, msg.payload || {}));
  });
}
