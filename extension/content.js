// Claude MCP Bridge - content script (https://claude.ai/*)
// Phase 1: 注入可见性验证（提示条），DOM 交互后续阶段实现。

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
if (typeof browser !== "undefined" && browser.runtime && browser.runtime.sendMessage) {
  browser.runtime
    .sendMessage({ type: "bridge-ping" })
    .then((res) => console.log("[claude-mcp-bridge] ping via background:", res))
    .catch((e) => console.warn("[claude-mcp-bridge] ping failed:", e));
}
