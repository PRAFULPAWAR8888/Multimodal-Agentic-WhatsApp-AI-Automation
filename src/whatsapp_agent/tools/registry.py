"""
Tool Execution Gatekeeper and Registry.

Provides a centralized registry for all agent tools (functions),
enforcing Risk Levels and Role-Based Access Control (RBAC) prior to execution.
"""

from __future__ import annotations

import inspect
from enum import Enum
from typing import Any, Callable, Coroutine, Dict

from whatsapp_agent.core.exceptions import ToolExecutionError
from whatsapp_agent.observability.logging import get_logger

logger = get_logger(__name__)


class RiskLevel(str, Enum):
    """
    Categorization of tool risk to enforce execution policy.
    LOW: Safe to run autonomously (e.g., read-only, search).
    MEDIUM: State-mutating but reversible or low-impact (e.g., draft email).
    HIGH: Irreversible or high financial/privacy impact (e.g., send money, delete data).
    """

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class ToolDefinition:
    """Metadata and execution pointer for a registered tool."""

    def __init__(
        self,
        name: str,
        description: str,
        func: Callable[..., Coroutine[Any, Any, Any]],
        schema: Dict[str, Any],
        risk_level: RiskLevel = RiskLevel.LOW,
        required_permissions: list[str] | None = None,
        required_consent_scopes: list[str] | None = None,
        owner_source: str = "native",
        is_mcp: bool = False,
        transport: str | None = None,
        version: str = "1.0",
        tool_id: str | None = None,
        enabled: bool = True,
    ) -> None:
        self.name = name
        self.description = description
        self.func = func
        self.schema = schema
        self.risk_level = risk_level
        self.required_permissions = required_permissions or []
        self.required_consent_scopes = required_consent_scopes or []
        self.owner_source = owner_source
        self.is_mcp = is_mcp
        self.transport = transport
        self.version = version
        self.tool_id = tool_id or name
        self.enabled = enabled


class ToolRegistry:
    """Central registry of all available agent tools."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def register(
        self,
        name: str,
        description: str,
        schema: Dict[str, Any],
        risk_level: RiskLevel = RiskLevel.LOW,
        required_permissions: list[str] | None = None,
        required_consent_scopes: list[str] | None = None,
        owner_source: str = "native",
        is_mcp: bool = False,
        transport: str | None = None,
        version: str = "1.0",
        tool_id: str | None = None,
        enabled: bool = True,
    ) -> Callable[[Callable[..., Coroutine[Any, Any, Any]]], Callable[..., Coroutine[Any, Any, Any]]]:
        """Decorator to register a tool function in the registry."""
        
        def decorator(func: Callable[..., Coroutine[Any, Any, Any]]) -> Callable[..., Coroutine[Any, Any, Any]]:
            if not inspect.iscoroutinefunction(func):
                raise ValueError(f"Tool function '{name}' must be a coroutine (async def).")

            self._tools[name] = ToolDefinition(
                name=name,
                description=description,
                func=func,
                schema=schema,
                risk_level=risk_level,
                required_permissions=required_permissions,
                required_consent_scopes=required_consent_scopes,
                owner_source=owner_source,
                is_mcp=is_mcp,
                transport=transport,
                version=version,
                tool_id=tool_id,
                enabled=enabled,
            )
            logger.info("tool_registered", tool_name=name, risk_level=risk_level.value, source=owner_source)
            return func

        return decorator

    def get_tool(self, name: str) -> ToolDefinition:
        """Retrieve a tool definition by name."""
        if name not in self._tools:
            raise ToolExecutionError(f"Tool '{name}' is not registered.", code="TOOL_NOT_FOUND")
        return self._tools[name]
    
    def list_tools(self) -> list[ToolDefinition]:
        """List all registered tools."""
        return list(self._tools.values())


class ToolRunner:
    """
    Executes tools while enforcing risk tier and permission checks.
    """

    def __init__(self, registry: ToolRegistry) -> None:
        self.registry = registry

    async def execute(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> Any:
        """
        Execute a tool by name with arguments.
        
        Args:
            tool_name: Name of the registered tool.
            arguments: kwargs to pass to the tool.
            context: Context dict containing 'permissions' list, 'workspace_id', etc.
        """
        import time
        
        ctx = context or {}
        
        # 1. Tool Registry Validation
        tool = self.registry.get_tool(tool_name)
        if not tool.enabled:
            raise ToolExecutionError(f"Tool '{tool_name}' is disabled.", code="TOOL_DISABLED")

        # 2. Authentication
        # Skip for internal system calls where is_authenticated is explicitly set
        if ctx.get("is_authenticated") is False:
            raise ToolExecutionError("Unauthenticated request", code="UNAUTHENTICATED")

        # 3. Identity / KYA
        user_id = ctx.get("user_id", "system")

        # 4. Authorization (Permissions)
        user_permissions = ctx.get("permissions", [])
        for req_perm in tool.required_permissions:
            if req_perm not in user_permissions:
                logger.warning(
                    "tool_execution_denied",
                    tool_name=tool_name,
                    missing_permission=req_perm,
                )
                raise ToolExecutionError(
                    f"Execution denied: Missing permission '{req_perm}' for tool '{tool_name}'",
                    code="PERMISSION_DENIED"
                )

        # 5. Consent / Scope Check
        user_scopes = ctx.get("consent_scopes", [])
        for scope in tool.required_consent_scopes:
            if scope not in user_scopes:
                logger.warning(
                    "tool_consent_denied",
                    tool_name=tool_name,
                    missing_scope=scope,
                )
                raise ToolExecutionError(
                    f"Execution denied: Missing consent scope '{scope}' for tool '{tool_name}'",
                    code="CONSENT_DENIED"
                )

        # 6. Risk Classification
        if tool.risk_level == RiskLevel.HIGH:
            logger.warning(
                "executing_high_risk_tool",
                tool_name=tool_name,
                arguments=arguments,
                user_id=user_id
            )

        # 7. Tool Execution
        logger.info("tool_executing", tool_name=tool_name, user_id=user_id)
        start_time = time.monotonic()
        try:
            result = await tool.func(**arguments)
        except Exception as exc:
            logger.error("tool_execution_failed", tool_name=tool_name, error=str(exc))
            raise ToolExecutionError(f"Tool '{tool_name}' execution failed: {exc}") from exc

        # 8. Audit Logging
        duration_ms = round((time.monotonic() - start_time) * 1000)
        logger.info(
            "tool_execution_audit", 
            tool_name=tool_name, 
            user_id=user_id, 
            duration_ms=duration_ms, 
            status="success",
            is_mcp=tool.is_mcp,
            owner=tool.owner_source
        )

        # 9. Response Validation
        if result is None:
            logger.warning("tool_returned_none", tool_name=tool_name)

        return result


# Global default registry
default_registry = ToolRegistry()
