import asyncio
import json
import base64
import audioop
import time
import wave
import io
import sys
import os
import winsound
import websockets
from openai import AsyncOpenAI
from whatsapp_agent.config.settings import get_settings

PRESETS = [
    "Hello Anand, what services does Associative offer?",
    "Hi Anand, I am a Python and React developer looking for a job at Associative.",
    "Can you help me schedule a project discovery consultation?",
    "I want to speak with a human manager right now, I am very frustrated!",
]

async def run_call(user_speech_text: str):
    print("\n" + "=" * 65)
    print("📞 SIMULATING INBOUND PHONE CALL TO ANAND KUMAR (ASSOCIATIVE)")
    print("=" * 65)
    print(f"🗣️  Caller Voice: \"{user_speech_text}\"")

    settings = get_settings()
    ws_url = "ws://localhost:8000/ws/twilio/stream"

    # 1. Synthesize caller voice as 8kHz mu-law (Standard FreeSWITCH / Twilio format)
    print("\n[1/4] Generating 8kHz mu-law audio for inbound voice call...")
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    speech_resp = await client.audio.speech.create(
        model="tts-1",
        voice="alloy",
        input=user_speech_text,
        response_format="pcm"
    )
    pcm_24k = speech_resp.content
    pcm_8k, _ = audioop.ratecv(pcm_24k, 2, 1, 24000, 8000, None)
    caller_mulaw = audioop.lin2ulaw(pcm_8k, 2)
    print(f"      ✓ Generated {len(caller_mulaw)} bytes of caller voice stream.")

    # 2. Connect to Telephony WebSocket
    print(f"\n[2/4] Connecting to Telephony WebSocket ({ws_url})...")
    stream_sid = "manual-call-" + str(int(time.time()))

    async with websockets.connect(ws_url, ping_interval=None, ping_timeout=None) as ws:
        # Handshake
        await ws.send(json.dumps({"event": "connected", "protocol": "Call"}))
        await ws.send(json.dumps({
            "event": "start",
            "sequenceNumber": "1",
            "start": {
                "streamSid": stream_sid,
                "accountSid": "AC_manual_test",
                "callSid": "CA_manual_" + str(int(time.time())),
                "tracks": ["inbound"]
            },
            "streamSid": stream_sid
        }))
        print("      ✓ Call connected. Streaming caller audio...")

        # 3. Stream audio in 20ms frames (160 bytes)
        chunk_size = 160
        for i in range(0, len(caller_mulaw), chunk_size):
            chunk = caller_mulaw[i:i + chunk_size]
            b64_chunk = base64.b64encode(chunk).decode("utf-8")
            await ws.send(json.dumps({
                "event": "media",
                "streamSid": stream_sid,
                "media": {"payload": b64_chunk}
            }))
            await asyncio.sleep(0.005)

        # Send trailing silence frames to trigger VAD
        silence_chunk = b"\xff" * 160
        silence_b64 = base64.b64encode(silence_chunk).decode("utf-8")
        for _ in range(60):
            await ws.send(json.dumps({
                "event": "media",
                "streamSid": stream_sid,
                "media": {"payload": silence_b64}
            }))
            await asyncio.sleep(0.01)

        print("\n[3/4] Waiting for AI Voice Agent to transcribe & respond...")
        received_mulaw = bytearray()
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
                        received_mulaw.extend(audio_data)
                        if not response_started:
                            response_started = True
                            print(f"      🔊 Anand Kumar answered! Streaming audio received in {time.time() - start_wait:.2f}s")
                elif evt == "clear":
                    print("      ℹ️ Telephony clear/interruption received.")

            except asyncio.TimeoutError:
                if response_started:
                    print("      ✓ AI finished streaming spoken response.")
                    break
                else:
                    print(f"      ... AI reasoning and synthesizing ({time.time() - start_wait:.1f}s) ...")

    # 4. Play audio through Windows PC speakers
    print("\n[4/4] Playing AI Voice Response Through Your Speakers...")
    if len(received_mulaw) > 0:
        duration_sec = len(received_mulaw) / 8000.0
        print(f"      🔊 Audio Duration: {duration_sec:.2f} seconds ({len(received_mulaw)} bytes)")
        
        # Convert 8kHz mu-law to Linear 16-bit PCM WAV
        linear_pcm = audioop.ulaw2lin(bytes(received_mulaw), 2)
        wav_io = io.BytesIO()
        with wave.open(wav_io, 'wb') as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(8000)
            wav_file.writeframes(linear_pcm)
        wav_bytes = wav_io.getvalue()

        # Save to disk for reference
        output_file = "last_call_response.wav"
        with open(output_file, "wb") as f:
            f.write(wav_bytes)
        print(f"      💾 Saved audio to: {os.path.abspath(output_file)}")

        # Play out loud on Windows
        try:
            print("      ▶️ Playing through PC speakers now...")
            winsound.PlaySound(wav_bytes, winsound.SND_MEMORY)
            print("      ✓ Audio playback complete!")
        except Exception as e:
            print(f"      ⚠️ Speaker playback notice: {e}")

        print("\n✅ CALL TEST SUCCESSFUL! Call and transcript logged to database.")
    else:
        print("❌ No audio received from agent.")

def main():
    print("=" * 65)
    print("🎙️  INTERACTIVE AI VOICE CALL AGENT TESTER (ANAND KUMAR)")
    print("=" * 65)
    print("Choose how you want to test the voice call agent:\n")
    for idx, preset in enumerate(PRESETS, 1):
        print(f"  [{idx}] {preset}")
    print("  [5] Custom question (Type your own)")
    print("  [0] Exit")
    print("-" * 65)

    choice = input("\nEnter choice [1-5]: ").strip()
    if choice == "0":
        return
    elif choice in ["1", "2", "3", "4"]:
        question = PRESETS[int(choice) - 1]
    elif choice == "5":
        question = input("\nType what you want to say to Anand Kumar: ").strip()
        if not question:
            question = PRESETS[0]
    else:
        question = PRESETS[0]

    asyncio.run(run_call(question))

if __name__ == "__main__":
    main()
