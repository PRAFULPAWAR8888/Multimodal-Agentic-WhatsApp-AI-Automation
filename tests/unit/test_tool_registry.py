import pytest

from whatsapp_agent.tools.registry import ToolRegistry, ToolRunner, ToolExecutionError, RiskLevel

@pytest.fixture
def registry():
    return ToolRegistry()

@pytest.fixture
def runner(registry):
    return ToolRunner(registry)

@pytest.mark.asyncio
async def test_tool_registration(registry, runner):
    @registry.register(
        name="test_tool",
        description="A simple test tool",
        schema={"type": "object", "properties": {}},
        risk_level=RiskLevel.LOW,
        required_permissions=["use_test_tool"]
    )
    async def dummy_tool(x: int) -> int:
        return x * 2

    assert "test_tool" in registry._tools
    
    tool = registry.get_tool("test_tool")
    assert tool.name == "test_tool"
    assert tool.risk_level == RiskLevel.LOW
    
    # Execution should succeed with correct permissions
    result = await runner.execute("test_tool", {"x": 5}, context={"permissions": ["use_test_tool"]})
    assert result == 10

@pytest.mark.asyncio
async def test_tool_permission_denial(registry, runner):
    @registry.register(
        name="secure_tool",
        description="A tool requiring high permissions",
        schema={"type": "object", "properties": {}},
        risk_level=RiskLevel.HIGH,
        required_permissions=["admin_only"]
    )
    async def secure_tool() -> str:
        return "Secret data"

    # Execution should fail with missing permissions
    with pytest.raises(ToolExecutionError, match="Execution denied") as exc:
        await runner.execute("secure_tool", {}, context={"permissions": ["user"]})
    
    assert "Missing permission 'admin_only'" in str(exc.value)

@pytest.mark.asyncio
async def test_tool_not_found(runner):
    with pytest.raises(ToolExecutionError, match="not registered"):
        await runner.execute("non_existent_tool", {}, context={})
