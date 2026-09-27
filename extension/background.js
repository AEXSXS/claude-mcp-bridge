// Claude MCP Bridge - background (Firefox MV3 event page)
// Phase 1: 仅生命周期日志，WS 连接后续阶段实现。

console.log("[claude-mcp-bridge] background loaded");

browser.runtime.onInstalled.addListener((details) => {
  console.log("[claude-mcp-bridge] installed:", details.reason);
});
