import asyncio
import time
import os
from faster_whisper import WhisperModel

try:
    import sounddevice as sd
    from scipy.io.wavfile import write
except ImportError:
    print("Missing required packages for microphone recording!")
    print("Please run this command first:")
    print("pip install sounddevice scipy")
    exit(1)

def record_audio(filename="test_mic.wav", duration=5, fs=44100):
    print(f"\n🎤 RECORDING FOR {duration} SECONDS... SPEAK NOW! 🎤")
    print("(Try saying something like: 'Hello, what is your name?')")
    recording = sd.rec(int(duration * fs), samplerate=fs, channels=1)
    sd.wait()
    print("✅ Recording complete!")
    write(filename, fs, recording)
    return filename

async def main():
    print("🎙️ Starting End-to-End Voice Agent Test...\n")
    
    # 1. Record audio
    audio_file = record_audio(duration=5)
    
    # 2. Transcribe
    print("\n[2/4] Loading faster-whisper model...")
    model = WhisperModel("base", device="cpu", compute_type="int8")
    
    print("\n[3/4] Transcribing your voice...")
    segments, _ = model.transcribe(audio_file, beam_size=5)
    transcript = " ".join([s.text for s in segments]).strip()
    
    print("\n📝 You said:")
    print("-" * 40)
    print(transcript)
    print("-" * 40)
    
    # Cleanup audio file
    if os.path.exists(audio_file):
        os.remove(audio_file)

    if not transcript:
        print("Could not hear anything. Exiting.")
        return

    # 3. Process through LangGraph Agent Workflow
    print("\n[4/4] Sending transcription to the AI Agent Workflow...")
    
    # Import workflow and database session
    from whatsapp_agent.workflows.main_workflow import get_workflow
    from whatsapp_agent.whatsapp.providers.factory import get_whatsapp_provider
    
    workflow = get_workflow()
    
    # Build the mock state
    state = {
        "raw_text": transcript,
        "input_modality": "voice",
        "contact_wa_id": "test_user_123",
        "conversation_history": [],
        "workspace_id": "00000000-0000-0000-0000-000000000000" # Dummy UUID
    }
    
    print("Running workflow (this will invoke the LLM)...")
    result_state = await workflow.ainvoke(state)
    
    # 4. Show the response
    print("\n🤖 Agent Response:")
    print("=" * 40)
    print(result_state.get("response_text"))
    print("=" * 40)
    
    print(f"\nIntent Detected: {result_state.get('intent')}")
    print(f"Modality flag (voice response requested?): {result_state.get('response_voice')}")
    
    # Check if the Mock provider sent the message
    provider = get_whatsapp_provider()
    if provider.is_mock:
        sent = provider.get_sent_messages()
        print(f"\nMessages sent via WhatsApp Provider: {len(sent)}")
        
    print("\n✅ E2E VOICE TEST COMPLETED!")

if __name__ == "__main__":
    asyncio.run(main())
