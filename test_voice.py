import os
import time
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
    recording = sd.rec(int(duration * fs), samplerate=fs, channels=1)
    sd.wait()  # Wait until recording is finished
    print("✅ Recording complete!")
    write(filename, fs, recording)  # Save as WAV file 
    return filename

def main():
    print("🎙️ Starting Local Voice-to-Text Microphone Test...\n")
    
    # 1. Record audio from microphone
    audio_file = record_audio(duration=5)
    
    # 2. Load the faster-whisper model
    print("\n[2/3] Loading faster-whisper model (this runs 100% locally on your CPU)...")
    start_time = time.time()
    model = WhisperModel("base", device="cpu", compute_type="int8")
    print(f"      ✓ Model loaded in {time.time() - start_time:.2f} seconds!")
    
    # 3. Transcribe the audio back to text
    print("\n[3/3] Transcribing your voice...")
    start_time = time.time()
    segments, info = model.transcribe(audio_file, beam_size=5)
    
    print(f"      ✓ Detected language: {info.language} (Probability: {info.language_probability:.2f})")
    
    print("\n📝 Transcription Result:")
    print("-" * 40)
    for segment in segments:
        print(f"[{segment.start:.2f}s -> {segment.end:.2f}s] {segment.text}")
    print("-" * 40)
    
    print(f"\n      ✓ Transcription completed in {time.time() - start_time:.2f} seconds!")
    
    # Cleanup
    if os.path.exists(audio_file):
        os.remove(audio_file)
    
    print("\n✅ TEST PASSED: Your local Speech-to-Text engine understood you perfectly!")

if __name__ == "__main__":
    main()
