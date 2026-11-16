import asyncio
import os
from dotenv import load_dotenv
from whatsapp_agent.whatsapp.providers.factory import get_whatsapp_provider

load_dotenv()

async def test_outbound():
    provider = get_whatsapp_provider()
    
    # We will send a simple text message to the user's verified number
    to_phone = "919322295706"
    
    print(f"Testing OUTBOUND message to: {to_phone}")
    try:
        from whatsapp_agent.whatsapp.providers.base import SendTextRequest
        response = await provider.send_text_message(
            SendTextRequest(
                to=to_phone,
                body="Hello from your AI Assistant! 🤖 We've just restarted the backend and worker servers, and everything is looking great. Did you find the 'messages' checkbox in the Meta Dashboard?"
            )
        )
        print("SUCCESS! Message sent to WhatsApp!")
        print(f"Response from Meta: {response}")
    except Exception as e:
        print(f"ERROR sending message: {e}")

if __name__ == "__main__":
    asyncio.run(test_outbound())
