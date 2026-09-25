import asyncio
from typing import Any, Coroutine, Callable
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from whatsapp_agent.tools.registry import default_registry, RiskLevel
from whatsapp_agent.observability.logging import get_logger

logger = get_logger(__name__)


class MCPClientManager:
    """Manages connections to external MCP servers and registers their tools dynamically."""

    def __init__(self) -> None:
        self.active_sessions: dict[str, ClientSession] = {}
        # Keep references to the transport tasks so they don't get garbage collected
        self._exit_stacks = []

    async def connect_and_register(self, server_name: str, command: str, args: list[str], env: dict[str, str] | None = None) -> None:
        """
        Connect to a local MCP server over stdio and register its tools.
        """
        logger.info("mcp_connecting", server_name=server_name, command=command)
        
        server_params = StdioServerParameters(
            command=command,
            args=args,
            env=env
        )

        from contextlib import AsyncExitStack
        exit_stack = AsyncExitStack()
        self._exit_stacks.append(exit_stack)

        try:
            stdio_transport = await exit_stack.enter_async_context(stdio_client(server_params))
            read, write = stdio_transport
            session = await exit_stack.enter_async_context(ClientSession(read, write))
            
            await session.initialize()
            
            # List tools from the MCP server
            mcp_tools = await session.list_tools()
            
            for tool in mcp_tools.tools:
                # Wrap the MCP call in a local async function
                async def mcp_tool_wrapper(tool_name=tool.name, session=session, **kwargs) -> dict[str, Any]:
                    logger.debug("mcp_tool_executing", server_name=server_name, tool=tool_name)
                    result = await session.call_tool(tool_name, arguments=kwargs)
                    # Convert CallToolResult to a dict or string
                    if result.content and len(result.content) > 0:
                        if hasattr(result.content[0], "text"):
                            return result.content[0].text
                        return str(result.content)
                    return ""

                # Register it in the native ToolRegistry
                default_registry.register(
                    name=tool.name,
                    description=tool.description or "",
                    schema=tool.inputSchema,
                    risk_level=RiskLevel.MEDIUM, # Default MCP to medium risk
                    owner_source=server_name,
                    is_mcp=True,
                    transport="stdio",
                )(mcp_tool_wrapper)

                logger.info("mcp_tool_registered", server_name=server_name, tool=tool.name)

            self.active_sessions[server_name] = session
            logger.info("mcp_connected", server_name=server_name, tool_count=len(mcp_tools.tools))

        except Exception as e:
            logger.error("mcp_connection_failed", server_name=server_name, error=str(e))
            await exit_stack.aclose()
            raise


mcp_manager = MCPClientManager()
