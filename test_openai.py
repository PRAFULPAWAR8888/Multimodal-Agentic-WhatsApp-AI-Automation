import asyncio
from openai import AsyncOpenAI
import os
from dotenv import load_dotenv

load_dotenv()

async def test_openai():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("ERROR: OPENAI_API_KEY is still empty in .env!")
        return
        
    print(f"Found API Key starting with: {api_key[:10]}...")
    
    try:
        print("Testing connection to OpenAI...")
        client = AsyncOpenAI(api_key=api_key)
        
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "Say 'hello world' if you can hear me!"}],
            max_tokens=10
        )
        
        reply = response.choices[0].message.content
        print(f"SUCCESS! OpenAI replied: '{reply}'")
        
    except Exception as e:
        print(f"ERROR connecting to OpenAI: {e}")

if __name__ == "__main__":
    asyncio.run(test_openai())
