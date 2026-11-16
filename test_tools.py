import asyncio
from whatsapp_agent.tools.registry import default_registry, ToolRunner
from whatsapp_agent.tools.definitions.crm_tools import get_contact_info
from whatsapp_agent.tools.definitions.calendar_tools import book_meeting

async def test_tools():
    print("Testing Tool Registry...")
    tools = default_registry.list_tools()
    print(f"Registered Tools: {[t.name for t in tools]}")
    
    runner = ToolRunner(default_registry)
    
    print("\nTesting CRM Tool (get_contact_info)...")
    try:
        # We pass context with empty permissions/scopes if they are not strictly enforced in test, 
        # but let's just call the tool func directly since it's a unit test to bypass the gatekeeper if needed, 
        # or use runner.
        result = await get_contact_info(phone_number="+15551234567")
        print(f"CRM Tool Result: {result}")
    except Exception as e:
        print(f"CRM Tool Error: {e}")

    print("\nTesting Calendar Tool (book_meeting)...")
    try:
        result = await book_meeting(email="test@example.com", time_slot="2026-10-03T10:00:00")
        print(f"Calendar Tool Result: {result}")
    except Exception as e:
        print(f"Calendar Tool Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_tools())
