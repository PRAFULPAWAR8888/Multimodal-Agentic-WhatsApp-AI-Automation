import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
import redis.asyncio as redis
import os
from dotenv import load_dotenv

load_dotenv()

async def test_pgvector():
    db_url = os.getenv("DATABASE_URL")
    print(f"Testing pgvector in Postgres at: {db_url}")
    engine = create_async_engine(db_url)
    try:
        async with engine.connect() as conn:
            # Check if pgvector is installed
            result = await conn.execute(text("SELECT extname FROM pg_extension WHERE extname = 'vector'"))
            ext = result.scalar()
            if ext == 'vector':
                print("[OK] pgvector extension is installed and enabled.")
            else:
                print("[FAIL] pgvector extension is NOT installed. You may need to run 'CREATE EXTENSION vector;'")
    except Exception as e:
        print("[FAIL] Postgres connection failed:", e)
    finally:
        await engine.dispose()

async def test_redis():
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    print(f"\nTesting Redis at: {redis_url}")
    try:
        client = redis.from_url(redis_url)
        ping_result = await client.ping()
        if ping_result:
            print("[OK] Redis connection successful! (PING -> PONG)")
        else:
            print("[FAIL] Redis connection failed or returned unexpected result.")
    except Exception as e:
        print("[FAIL] Redis connection failed:", e)
    finally:
        if 'client' in locals():
            await client.close()

async def main():
    await test_pgvector()
    await test_redis()

if __name__ == "__main__":
    asyncio.run(main())
