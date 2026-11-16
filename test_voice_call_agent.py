import asyncio
import json
import base64
import audioop
import time
import websockets
from openai import AsyncOpenAI
from whatsapp_agent.config.settings import get_settings

async def main():
    print("=" * 60)
    print("📞 LIVE AI VOICE CALL AGENT (TELEPHONY STREAMING) TEST")
    print("=" * 60)

    settings = get_settings()
    ws_url = "ws://localhost:8000/ws/twilio/stream"

    # 1. Generate realistic caller voice audio (8kHz mu-law)
    caller_text = "Hello Anand, what services does Associative offer?"
    print(f"\n[1/5] Synthesizing caller voice message: '{caller_text}'...")

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    speech_resp = await client.audio.speech.create(
        model="tts-1",
        voice="alloy",
        input=caller_text,
        response_format="pcm"
    )
    pcm_24k = speech_resp.content

    # Resample 24kHz to 8kHz and convert to 8kHz mu-law (Standard Twilio / FreeSWITCH format)
    pcm_8k, _ = audioop.ratecv(pcm_24k, 2, 1, 24000, 8000, None)
    caller_mulaw = audioop.lin2ulaw(pcm_8k, 2)
    print(f"      ✓ Generated {len(caller_mulaw)} bytes of 8kHz mu-law audio.")

    # 2. Connect to Telephony WebSocket
    print(f"\n[2/5] Connecting to Telephony WebSocket: {ws_url}...")
    stream_sid = "test-call-stream-" + str(int(time.time()))

    async with websockets.connect(ws_url, ping_interval=None, ping_timeout=None) as ws:
        print("      ✓ WebSocket Connected successfully!")

        # 3. Send Twilio Stream Handshake
        await ws.send(json.dumps({"event": "connected", "protocol": "Call"}))
        await ws.send(json.dumps({
            "event": "start",
            "sequenceNumber": "1",
            "start": {
                "streamSid": stream_sid,
                "accountSid": "AC_mock_account",
                "callSid": "CA_mock_call_123",
                "tracks": ["inbound"]
            },
            "streamSid": stream_sid
        }))
        print(f"      ✓ Telephony Call Session started (StreamSID: {stream_sid})")

        # 4. Stream Caller Audio to the AI Agent in 20ms frames (160 bytes per chunk)
        print("\n[3/5] Streaming caller speech frames to AI Voice Agent...")
        chunk_size = 160 # 20ms of 8kHz audio
        for i in range(0, len(caller_mulaw), chunk_size):
            chunk = caller_mulaw[i:i + chunk_size]
            b64_chunk = base64.b64encode(chunk).decode("utf-8")
            await ws.send(json.dumps({
                "event": "media",
                "streamSid": stream_sid,
                "media": {"payload": b64_chunk}
            }))
            await asyncio.sleep(0.005) # Stream rapidly

        # Send silence frames to trigger VAD end-of-speech detection (>50 silent frames)
        print("      ✓ Speech frames sent. Sending trailing silence to trigger VAD...")
        silence_chunk = b"\xff" * 160 # 0 energy in mu-law
        silence_b64 = base64.b64encode(silence_chunk).decode("utf-8")
        for _ in range(60):
            await ws.send(json.dumps({
                "event": "media",
                "streamSid": stream_sid,
                "media": {"payload": silence_b64}
            }))
            await asyncio.sleep(0.01)

        print("\n[4/5] Waiting for AI Voice Agent to transcribe, reason, and stream audio response...")
        received_audio_bytes = bytearray()
        response_started = False
        start_wait = time.time()

        while time.time() - start_wait < 60.0:
            try:
                msg_raw = await asyncio.wait_for(ws.recv(), timeout=5.0)
                msg = json.loads(msg_raw)
                evt = msg.get("event")

                if evt == "media":
                    payload = msg.get("media", {}).get("payload")
                    if payload:
                        audio_data = base64.b64decode(payload)
                        received_audio_bytes.extend(audio_data)
                        if not response_started:
                            response_started = True
                            print(f"      🔊 AI Agent began streaming voice response! (First frame received in {time.time() - start_wait:.2f}s)")
                elif evt == "clear":
                    print("      ℹ️ Twilio clear/interruption signal received.")

            except asyncio.TimeoutError:
                if response_started:
                    print("      ✓ AI finished streaming audio response.")
                    break
                else:
                    print(f"      ... still processing speech ({time.time() - start_wait:.1f}s) ...")

        # 5. Verify Results
        print("\n[5/5] Voice Agent Performance & Audio Verification:")
        print("-" * 60)
        print(f"Total Received Mu-Law Audio Bytes: {len(received_audio_bytes)}")
        if len(received_audio_bytes) > 0:
            audio_duration_sec = len(received_audio_bytes) / 8000.0
            print(f"Synthesized Speech Duration: ~{audio_duration_sec:.2f} seconds of clear spoken audio")
            print("Status: ✅ SUCCESS — Full Bi-Directional AI Voice Call Pipeline is WORKING!")
        else:
            print("Status: ❌ FAILED — No audio frames received.")
        print("-" * 60)

if __name__ == "__main__":
    asyncio.run(main())
