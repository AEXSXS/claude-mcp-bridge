"""claude-mcp-bridge MCP Server (Phase 1 skeleton)

最小可运行骨架：仅暴露一个 hello 测试工具。
WebSocket 桥接与真实发送逻辑属后续阶段，暂不实现。
"""

from mcp.server.mcpserver import MCPServer

mcp = MCPServer("claude-mcp-bridge")


@mcp.tool()
def hello(name: str = "world") -> str:
    """测试工具：返回问候语，用于验证 MCP Server 与客户端链路。"""
    return f"hello, {name}!"


if __name__ == "__main__":
    mcp.run()  # stdio 传输，供本地 AI 客户端连接
