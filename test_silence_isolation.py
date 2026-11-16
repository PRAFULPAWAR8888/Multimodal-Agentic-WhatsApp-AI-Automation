import asyncio
import websockets
import json
import time

async def main():
    print("Testing silence isolation on ws://localhost:8000/ws/twilio/stream...")
    async with websockets.connect("ws://localhost:8000/ws/twilio/stream") as ws:
        sid = f"silence-test-{int(time.time())}"
        await ws.send(json.dumps({"event": "connected", "protocol": "Call"}))
        await ws.send(json.dumps({
            "event": "start",
            "start": {"streamSid": sid, "accountSid": "AC_silence", "callSid": "CA_silence", "tracks": ["inbound"]},
            "streamSid": sid
        }))

        # Send 80 frames of pure silence (1.6 seconds)
        silence_b64 = "////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////"
        for _ in range(80):
            await ws.send(json.dumps({"event": "media", "streamSid": sid, "media": {"payload": silence_b64}}))
            await asyncio.sleep(0.01)

        # Wait 4 seconds to observe if the server falsely triggers
        falsely_spoke = False
        start_wait = time.time()
        while time.time() - start_wait < 4.0:
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=1.0)
                data = json.loads(msg)
                if data.get("event") == "media":
                    falsely_spoke = True
                    break
            except asyncio.TimeoutError:
                pass

        if falsely_spoke:
            print("❌ FAILURE: Server falsely generated AI speech during caller silence!")
            return False
        else:
            print("✅ SUCCESS: Server remained completely silent. Zero false triggers!")
            return True

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
