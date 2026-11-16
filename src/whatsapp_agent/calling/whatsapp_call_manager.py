"""
WhatsApp Business Calling API - Live Inbound WebRTC Call Handler.

Handles inbound VoIP calls initiated from WhatsApp using WebRTC (aiortc),
orchestrating STT (Whisper), LangGraph conversational agent (Anand Kumar),
and TTS (OpenAI/Piper) with real-time bidirectional Opus audio streaming.
"""

from __future__ import annotations

import asyncio
import collections
import fractions
import io
import json
import os
import time
import urllib.error
import urllib.request
import uuid
import wave
from typing import Any

import av
import numpy as np
import scipy.signal as signal
from aiortc import AudioStreamTrack, RTCPeerConnection, RTCSessionDescription
from aiortc.mediastreams import MediaStreamError

from whatsapp_agent.config.settings import get_settings
from whatsapp_agent.observability.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()

AUDIO_PTIME = 0.020  # 20ms per audio frame
SAMPLE_RATE = 48000  # WebRTC standard sample rate (Opus)
SAMPLES_PER_FRAME = int(SAMPLE_RATE * AUDIO_PTIME)  # 960 samples

# 2nd-order Butterworth voice bandpass filter (250Hz - 3400Hz @ 16kHz)
# Suppresses sub-250Hz low-frequency noise (AC, fan, desk rumble, mic pops)
# and frequencies above 3400Hz (hiss, static)
_VOICE_BANDPASS_SOS = signal.butter(2, [250, 3400], btype="bandpass", fs=16000, output="sos")

# Persistent OpenAI client for low-latency connection pooling
_openai_client: Any = None


def get_openai_client() -> Any:
    """Return persistent AsyncOpenAI client with active connection pool."""
    global _openai_client
    if _openai_client is None:
        openai_key = os.getenv("OPENAI_API_KEY") or settings.openai_api_key
        if openai_key:
            try:
                from openai import AsyncOpenAI
                _openai_client = AsyncOpenAI(api_key=openai_key)
            except Exception as e:
                logger.warning("failed_to_initialize_persistent_openai_client", error=str(e))
    return _openai_client


class AIAudioTrack(AudioStreamTrack):
    """
    Real-time audio track that streams Anand Kumar's voice to the WhatsApp caller.
    Paces output at exactly 20ms intervals (48kHz mono 16-bit PCM).
    """
    kind = "audio"

    def __init__(self, sample_rate: int = SAMPLE_RATE, frame_samples: int = SAMPLES_PER_FRAME) -> None:
        super().__init__()
        self.sample_rate = sample_rate
        self.frame_samples = frame_samples
        self.samples_sent = 0
        self.time_base = fractions.Fraction(1, self.sample_rate)
        self._queue: asyncio.Queue[np.ndarray] = asyncio.Queue()
        self._last_time = time.monotonic()
        self.is_playing = False

    def clear_queue(self) -> None:
        """Clear all pending audio frames to allow caller interruption."""
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except asyncio.QueueEmpty:
                break
        self.is_playing = False

    def queue_pcm_audio(self, pcm_bytes: bytes, in_sample_rate: int = 24000) -> None:
        """
        Convert complete PCM audio into 48kHz mono 20ms chunks using high-fidelity
        polyphase anti-aliasing resampling. Eliminates 100% of audio fluctuations and metallic buzz.
        """
        if not pcm_bytes:
            return

        try:
            audio_data = np.frombuffer(pcm_bytes, dtype=np.int16)
            if len(audio_data) == 0:
                return

            # High-fidelity polyphase anti-aliased resampling:
            if in_sample_rate == 24000:
                # 24kHz -> 48kHz: upsample by 2 with anti-aliasing half-band FIR filter
                audio_48k = signal.resample_poly(audio_data, 2, 1).astype(np.int16)
            elif in_sample_rate == 16000:
                # 16kHz -> 48kHz: upsample by 3
                audio_48k = signal.resample_poly(audio_data, 3, 1).astype(np.int16)
            elif in_sample_rate == self.sample_rate:
                audio_48k = audio_data
            else:
                num_target = int(len(audio_data) * self.sample_rate / in_sample_rate)
                audio_48k = np.interp(
                    np.linspace(0, len(audio_data), num_target, endpoint=False),
                    np.arange(len(audio_data)),
                    audio_data,
                ).astype(np.int16)

            # Chunk into exact 20ms frames (960 samples each)
            offset = 0
            chunks_added = 0
            while offset < len(audio_48k):
                chunk = audio_48k[offset : offset + self.frame_samples]
                if len(chunk) < self.frame_samples:
                    chunk = np.pad(chunk, (0, self.frame_samples - len(chunk)), mode="constant")
                self._queue.put_nowait(chunk)
                offset += self.frame_samples
                chunks_added += 1

            self.is_playing = True
            logger.info("queued_audio_frames_for_caller", total_chunks=chunks_added, duration_sec=round(chunks_added * 0.02, 2))
        except Exception as e:
            logger.error("error_queueing_pcm_audio", error=str(e))

    def flush_pcm(self) -> None:
        """No-op for batch sentence queuing."""
        pass

    async def recv(self) -> av.AudioFrame:
        """
        Produce the next 20ms audio frame with real-time pacing.
        """
        now = time.monotonic()
        elapsed = now - self._last_time
        sleep_time = (self.frame_samples / self.sample_rate) - elapsed
        if sleep_time > 0:
            await asyncio.sleep(sleep_time)
        self._last_time = time.monotonic()

        if not self._queue.empty():
            chunk = self._queue.get_nowait()
            self.is_playing = True
        else:
            chunk = np.zeros(self.frame_samples, dtype=np.int16)
            self.is_playing = False

        frame = av.AudioFrame.from_ndarray(chunk.reshape(1, -1), layout="mono", format="s16")
        frame.sample_rate = self.sample_rate
        frame.pts = self.samples_sent
        frame.time_base = self.time_base
        frame.duration = self.frame_samples

        self.samples_sent += self.frame_samples
        return frame
        frame.pts = self.samples_sent
        frame.time_base = self.time_base
        frame.duration = self.frame_samples

        self.samples_sent += self.frame_samples
        return frame


DEFAULT_GREETING = "Hello! Anand Kumar is speaking from Associative Technologies. How can I assist you with your project today?"

VOICE_SYSTEM_PROMPT = (
    "You are Anand Kumar representing Associative (a premier software development, web, mobile app, and AI automation company). "
    "You are on a live phone call with a customer who called our WhatsApp Business number. "
    "MANDATORY CONVERSATIONAL GUIDELINES: "
    "1. INSTANT SHORT OPENING: Start immediately with a short, punchy 2 to 4 word direct opening (e.g. 'Yes, certainly!', 'Yes, we do!', 'Our office is in Pune.', 'We build custom software!'). "
    "2. ANSWER DIRECTLY: Follow the opening with 1 concise, logical sentence answering their exact question. Total response must be 1 to 2 sentences (maximum 25 words). "
    "3. COMPANY BACKGROUND: Associative is based in Pune, Maharashtra, India. We build high-performance software for clients across India and globally. "
    "4. SERVICES: Custom software development, mobile apps (iOS & Android with Flutter or React Native), modern responsive websites, CRM/ERP platforms, and enterprise AI agent automation. "
    "5. PRICING & COST: We provide tailored pricing based on specific requirements, features, and timeline. Mention that we offer a free technical discovery consultation to discuss scope and provide an accurate quotation. "
    "6. OFFICE / LOCATION: Our headquarters are located in Pune, Maharashtra, India. We also work with clients remotely worldwide. "
    "7. HIRING / JOBS / INTERNSHIPS: If the caller asks for job or internship opportunities, politely thank them, confirm that their details are noted, and state that our recruitment team will reach out if their profile matches open openings. "
    "8. LANGUAGE: Seamlessly match the caller's language. If they speak in Hindi or Hinglish, respond in polite, natural conversational Hindi. If English, respond in natural English. "
    "9. PHONE CALL STYLE: Speak naturally like a real human on the phone. Never use asterisks, markdown, lists, bullet points, or robotic phrases. "
    "10. IGNORE INCIDENTAL BACKGROUND NOISE: If the transcribed message contains faint background chatter, room noise, or incidental words not addressed to you, focus strictly on the user's core question."
)


class WhatsAppCallManager:
    """
    Manages active WhatsApp Business Calling API WebRTC peer connections.
    """

    def __init__(self) -> None:
        self.active_calls: dict[str, RTCPeerConnection] = {}
        self.call_tracks: dict[str, AIAudioTrack] = {}
        self.call_history: dict[str, list[dict[str, str]]] = {}
        self.call_turn_tasks: dict[str, asyncio.Task[None]] = {}
        self._cached_greeting_pcm: bytes | None = None
        self._cached_greeting_rate: int = 24000

    async def get_or_create_greeting_audio(self) -> tuple[bytes | None, int]:
        """
        Get or synthesize Anand Kumar's initial greeting audio.
        Cached in memory so incoming calls can be answered with zero latency.
        """
        if self._cached_greeting_pcm is not None:
            return self._cached_greeting_pcm, self._cached_greeting_rate

        pcm_bytes, rate = await self._generate_pcm_speech(DEFAULT_GREETING)
        if pcm_bytes:
            self._cached_greeting_pcm = pcm_bytes
            self._cached_greeting_rate = rate
        return self._cached_greeting_pcm, self._cached_greeting_rate

    async def _generate_pcm_speech(self, text: str) -> tuple[bytes | None, int]:
        """
        Synthesize text into raw linear PCM bytes and sample rate.
        """
        # Priority 1: OpenAI TTS (24kHz linear PCM) using persistent client
        client = get_openai_client()
        if client:
            try:
                resp = await client.audio.speech.create(
                    model="tts-1",
                    voice="alloy",
                    input=text,
                    response_format="pcm",  # 24,000 Hz, 16-bit linear PCM
                )
                pcm_bytes = resp.content
                if pcm_bytes:
                    return pcm_bytes, 24000
            except Exception as e:
                logger.warning("openai_tts_generation_error", error=str(e))

        # Priority 2: Piper TTS / Twilio Mulaw fallback
        try:
            from whatsapp_agent.voice.tts.piper_tts import get_tts_provider
            tts = get_tts_provider()
            mulaw_bytes = await tts.generate_twilio_audio(text)
            if mulaw_bytes:
                import audioop
                pcm_8k = audioop.ulaw2lin(mulaw_bytes, 2)
                return pcm_8k, 8000
        except Exception as e:
            logger.warning("piper_tts_generation_error", error=str(e))

        return None, 16000

    async def handle_inbound_call(
        self,
        call_event: dict[str, Any],
        phone_number_id: str | None,
    ) -> None:
        """
        Process an inbound call event received from Meta's 'calls' webhook.
        """
        call_id = call_event.get("id")
        event = call_event.get("event")
        caller = call_event.get("from")
        session = call_event.get("session", {})

        logger.info(
            "call_manager_received_event",
            call_id=call_id,
            call_action=event,
            caller=caller,
            phone_number_id=phone_number_id,
        )

        if not call_id:
            logger.warning("call_event_missing_id", call_event=call_event)
            return

        if event in ("terminate", "rejected", "timed_out", "hungup", "ended"):
            logger.info("call_terminated_remotely", call_id=call_id, reason=event)
            await self._cleanup_call(call_id)
            return

        # Extract SDP offer from all possible payload locations
        sdp_offer = None
        if isinstance(session, dict) and session.get("sdp"):
            sdp_offer = session.get("sdp")
        elif isinstance(call_event.get("sdp"), dict) and call_event.get("sdp", {}).get("sdp"):
            sdp_offer = call_event["sdp"]["sdp"]
        elif isinstance(call_event.get("sdp"), str):
            sdp_offer = call_event["sdp"]
        elif isinstance(call_event.get("connection"), dict):
            webrtc = call_event["connection"].get("webrtc", {})
            sdp_offer = webrtc.get("sdp") if isinstance(webrtc, dict) else None

        event_str = (event or "").lower()
        logger.info(
            "evaluating_call_event",
            call_id=call_id,
            call_action=event_str,
            has_sdp=(sdp_offer is not None),
        )

        if event_str in ("connect", "offer", "ringing", "incoming") or sdp_offer:
            if not sdp_offer:
                logger.warning(
                    "call_incoming_missing_sdp_offer",
                    call_id=call_id,
                    available_keys=list(call_event.keys()),
                )
                return

            await self._answer_call(call_id, sdp_offer, caller or "Unknown", phone_number_id)

    async def _answer_call(
        self,
        call_id: str,
        sdp_offer: str,
        caller: str,
        phone_number_id: str | None,
    ) -> None:
        """
        Accept an inbound call: establish WebRTC peer connection, generate SDP answer,
        send 'accept' to Meta Graph API, and start speaking.
        """
        logger.info("answering_whatsapp_call", call_id=call_id, caller=caller)

        # 1. Create RTCPeerConnection
        pc = RTCPeerConnection()
        self.active_calls[call_id] = pc

        # 2. Add AI Audio Track for agent responses
        ai_track = AIAudioTrack()
        self.call_tracks[call_id] = ai_track
        pc.addTrack(ai_track)

        # 3. Setup incoming audio processing (Caller -> Whisper -> Agent)
        @pc.on("track")
        def on_track(track: AudioStreamTrack) -> None:
            if track.kind == "audio":
                logger.info("incoming_caller_audio_track_started", call_id=call_id)
                asyncio.create_task(self._process_caller_audio(call_id, track, caller, ai_track))

        @pc.on("connectionstatechange")
        async def on_state_change() -> None:
            logger.info("call_connection_state_changed", call_id=call_id, state=pc.connectionState)
            if pc.connectionState in ("failed", "closed"):
                await self._cleanup_call(call_id)

        try:
            # 4. Set Remote SDP Offer
            offer = RTCSessionDescription(sdp=sdp_offer, type="offer")
            await pc.setRemoteDescription(offer)

            # 5. Create and Set Local SDP Answer
            answer = await pc.createAnswer()
            await pc.setLocalDescription(answer)

            # 6. Initialize conversation history with Anand Kumar greeting
            self.call_history[call_id] = [
                {"role": "assistant", "content": DEFAULT_GREETING}
            ]

            # 7. CRITICAL: Prepare and queue Anand Kumar's greeting audio BEFORE sending accept!
            # The call is answered only when the voice audio is loaded in RAM and ready to play!
            logger.info("preparing_ai_greeting_before_pickup", call_id=call_id)
            pcm_bytes, rate = await self.get_or_create_greeting_audio()
            if pcm_bytes:
                ai_track.queue_pcm_audio(pcm_bytes, in_sample_rate=rate)
                logger.info("ai_greeting_queued_and_ready", call_id=call_id)
            else:
                await self._synthesize_and_speak(ai_track, DEFAULT_GREETING)

            # 8. NOW that the backend is 100% primed and ready to talk, send 'accept' to Meta Graph API!
            token = os.getenv("WHATSAPP_ACCESS_TOKEN") or settings.whatsapp_access_token
            p_id = phone_number_id or os.getenv("WHATSAPP_PHONE_NUMBER_ID") or settings.whatsapp_phone_number_id
            version = os.getenv("WHATSAPP_API_VERSION", "v25.0")

            if not token or not p_id:
                logger.error("missing_credentials_for_call_accept")
                return

            accept_payload = {
                "messaging_product": "whatsapp",
                "call_id": call_id,
                "action": "accept",
                "session": {
                    "sdp_type": "answer",
                    "sdp": pc.localDescription.sdp,
                },
            }

            url = f"https://graph.facebook.com/{version}/{p_id}/calls"
            logger.info("sending_meta_call_accept", url=url, call_id=call_id)
            req = urllib.request.Request(
                url,
                data=json.dumps(accept_payload).encode("utf-8"),
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )

            # Call Meta Graph API
            loop = asyncio.get_running_loop()
            res_body = await loop.run_in_executor(None, self._send_meta_request, req)
            logger.info("meta_call_accepted_successfully", call_id=call_id, response=res_body)

        except Exception as e:
            logger.error("failed_to_answer_whatsapp_call", call_id=call_id, error=str(e))
            await self._cleanup_call(call_id)

    def _send_meta_request(self, req: urllib.request.Request) -> str:
        """Helper to send HTTP request to Meta Graph API."""
        try:
            with urllib.request.urlopen(req) as resp:
                data: str = resp.read().decode("utf-8")
                logger.info("meta_call_accept_response", status_code=resp.status, body=data)
                return str(data)
        except urllib.error.HTTPError as e:
            err: str = e.read().decode("utf-8")
            logger.error("meta_call_accept_api_error", code=e.code, body=err)
            return str(err)
        except Exception as e:
            logger.error("meta_call_accept_general_error", error=str(e))
            return str(e)

    def _frame_to_16k_pcm(self, frame: Any) -> Any:
        """
        Convert PyAV AudioFrame (aiortc Opus packed stereo, planar stereo, or mono)
        into a clean 1D mono 16kHz int16 PCM NumPy array.
        """
        try:
            arr = frame.to_ndarray()
            layout_name = getattr(getattr(frame, "layout", None), "name", "")
            samples = getattr(frame, "samples", 960)
            rate = getattr(frame, "sample_rate", 48000) or 48000

            # 1. Normalize bit depth to int16
            if np.issubdtype(arr.dtype, np.floating):
                int16_arr = (np.clip(arr, -1.0, 1.0) * 32767.0).astype(np.int16)
            elif arr.dtype == np.int32:
                int16_arr = (arr / 65536.0).astype(np.int16)
            else:
                int16_arr = arr.astype(np.int16)

            # 2. Downmix multi-channel (aiortc Opus produces packed s16 stereo [L0, R0, L1, R1...])
            if "stereo" in layout_name or (int16_arr.ndim == 1 and len(int16_arr) == samples * 2) or (int16_arr.ndim == 2 and int16_arr.shape[0] == 1 and int16_arr.shape[1] == samples * 2):
                flat = int16_arr.reshape(-1)
                left = flat[0::2]
                right = flat[1::2]
                mono = ((left.astype(np.int32) + right.astype(np.int32)) // 2).astype(np.int16)
            elif int16_arr.ndim == 2 and int16_arr.shape[0] == 2:
                mono = ((int16_arr[0].astype(np.int32) + int16_arr[1].astype(np.int32)) // 2).astype(np.int16)
            else:
                mono = int16_arr.reshape(-1)

            # 3. Resample down to 16kHz (Opus 48kHz mono is exact 3:1 decimation)
            if rate == 48000:
                return mono[::3]
            elif rate == 16000:
                return mono
            elif rate > 0 and len(mono) > 0:
                target_len = int(len(mono) * 16000 / rate)
                if target_len == 0:
                    return np.empty(0, dtype=np.int16)
                return np.interp(
                    np.linspace(0, len(mono), target_len, endpoint=False),
                    np.arange(len(mono)),
                    mono,
                ).astype(np.int16)
            return mono
        except Exception as e:
            logger.warning("frame_to_16k_pcm_error", error=str(e))
            return np.empty(0, dtype=np.int16)

    async def _process_caller_audio(
        self,
        call_id: str,
        track: AudioStreamTrack,
        caller: str,
        ai_track: AIAudioTrack,
    ) -> None:
        """
        Continuously read audio frames from the caller, filter out low-frequency noise (AC, fan, desk rumble)
        and high-frequency hiss, track adaptive background noise floor, detect speech using voice-band VAD,
        and transcribe via Whisper.
        """
        logger.info("caller_audio_processing_loop_started", call_id=call_id)

        audio_buffer = bytearray()
        pre_roll = collections.deque(maxlen=10)  # ~200ms audio buffer to preserve opening syllables
        silence_frames = 0
        speech_frames = 0
        interrupt_frames = 0
        is_speaking = False

        # Real-time streaming voice bandpass filter state (250Hz - 3400Hz)
        filter_zi = signal.sosfilt_zi(_VOICE_BANDPASS_SOS) * 0.0
        noise_floor = 120.0

        from whatsapp_agent.voice.stt.faster_whisper import get_stt_provider
        stt = get_stt_provider()

        while True:
            try:
                frame = await track.recv()
            except MediaStreamError:
                break
            except Exception:
                break

            # 1. Convert frame to guaranteed 16kHz mono int16 PCM
            pcm_16k = self._frame_to_16k_pcm(frame)
            if len(pcm_16k) == 0:
                continue

            # 2. Real-Time Noise Cancellation Filter (Telephone Voice Band 250Hz - 3400Hz):
            # Suppresses sub-250Hz low-frequency noise (AC, fan rumble, desk vibrations, mic breath pops)
            # and frequencies above 3400Hz (hiss, static)
            filtered_float, filter_zi = signal.sosfilt(_VOICE_BANDPASS_SOS, pcm_16k.astype(np.float32), zi=filter_zi)
            clean_pcm = np.clip(filtered_float, -32768.0, 32767.0).astype(np.int16)

            # 3. Compute Voice-Band RMS (measures ONLY human vocal cord energy, ignoring ambient rumble)
            rms = float(np.sqrt(np.mean(clean_pcm.astype(np.float32) ** 2)))

            raw_bytes = clean_pcm.tobytes()
            pre_roll.append(raw_bytes)

            # 4. Adaptive Background Noise Floor tracking during silence
            if not is_speaking and not ai_track.is_playing:
                if rms < 450.0:
                    noise_floor = 0.96 * noise_floor + 0.04 * rms

            # Adaptive Speech Threshold: must be significantly above ambient noise floor
            # Minimum 550.0 (strictly filters out faint murmurs, distant chatter, and quiet background noise)
            VAD_THRESHOLD = max(550.0, noise_floor * 2.8)

            # 5. Caller Barge-In / Interruption handling while AI is speaking
            if ai_track.is_playing:
                if rms > 900.0:
                    interrupt_frames += 1
                    if interrupt_frames >= 3:  # ~60ms of distinct direct speech
                        logger.info("caller_interrupted_ai_playback", rms=rms)
                        ai_track.clear_queue()
                        # Cancel any ongoing speech task
                        prev_task = self.call_turn_tasks.get(call_id)
                        if prev_task and not prev_task.done():
                            prev_task.cancel()

                        # Switch immediately to recording caller's speech without losing audio
                        is_speaking = True
                        speech_frames = 3
                        silence_frames = 0
                        interrupt_frames = 0
                        audio_buffer.clear()
                        for chunk in pre_roll:
                            audio_buffer.extend(chunk)
                        continue
                else:
                    interrupt_frames = 0
                # Echo suppression while AI speaks
                continue
            else:
                interrupt_frames = 0

            # 6. Standard Voice Activity Detection when AI is listening
            if rms > VAD_THRESHOLD:
                speech_frames += 1
                silence_frames = 0
                if not is_speaking and speech_frames >= 3:  # Require 60ms of continuous human voice
                    is_speaking = True
                    audio_buffer.clear()
                    # Prepend pre-roll frames so opening syllables are preserved
                    for pr_chunk in pre_roll:
                        audio_buffer.extend(pr_chunk)
                    logger.info("caller_started_speaking", rms=rms, threshold=round(VAD_THRESHOLD, 1))
            else:
                if is_speaking:
                    silence_frames += 1
                    # Natural conversational pause threshold:
                    # 28 frames * 20ms = 560ms of silence ensures caller is completely done talking and not cut off mid-thought
                    pause_threshold = 28

                    if silence_frames >= pause_threshold:
                        is_speaking = False
                        speech_frames = 0
                        silence_frames = 0
                        duration_sec = round(len(audio_buffer) / (16000 * 2), 2)
                        logger.info("caller_finished_speaking", buffer_size=len(audio_buffer), duration_sec=duration_sec)

                        segment_bytes = bytes(audio_buffer)
                        audio_buffer.clear()

                        # Minimum audio duration: 500ms (rejects brief clicks, mic taps, throat clears)
                        if len(segment_bytes) >= 16000 * 2 * 0.5:
                            prev_task = self.call_turn_tasks.get(call_id)
                            if prev_task and not prev_task.done():
                                prev_task.cancel()

                            task = asyncio.create_task(
                                self._handle_user_turn(call_id, segment_bytes, caller, ai_track, stt)
                            )
                            self.call_turn_tasks[call_id] = task

            if is_speaking:
                audio_buffer.extend(raw_bytes)

        logger.info("caller_audio_processing_loop_ended", call_id=call_id)

    async def _handle_user_turn(
        self,
        call_id: str,
        pcm_16k_bytes: bytes,
        caller: str,
        ai_track: AIAudioTrack,
        stt: Any,
    ) -> None:
        """
        Transcribe user speech, query Anand Kumar agent with full conversation history,
        and synthesize speech with low latency.
        """
        try:
            # 1. Prepare 16kHz Mono WAV container
            wav_io = io.BytesIO()
            with wave.open(wav_io, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(16000)
                wf.writeframes(pcm_16k_bytes)
            wav_bytes = wav_io.getvalue()

            # Save debug WAV for inspection
            try:
                with open("call_debug_user_last.wav", "wb") as f:
                    f.write(wav_bytes)
            except Exception:
                pass

            user_text = ""
            client = get_openai_client()

            # Priority 1: OpenAI Whisper (understands English, Indian accents, Hindi, Hinglish)
            if client:
                try:
                    resp = await client.audio.transcriptions.create(
                        model="whisper-1",
                        file=("audio.wav", wav_bytes, "audio/wav"),
                        prompt=(
                            "Anand Kumar, Associative Technologies Pune. Custom software, mobile apps, Flutter, React, websites, AI, pricing, jobs. English, Hindi."
                        ),
                        temperature=0.0,
                    )
                    user_text = resp.text.strip()
                    logger.info("whisper_transcription_result", call_id=call_id, recognized_text=user_text)
                except Exception as e:
                    logger.warning("openai_whisper_error_trying_fallback", error=str(e))

            # Priority 2: Local Faster-Whisper fallback
            if not user_text:
                try:
                    transcription = await stt.transcribe(wav_bytes)
                    user_text = transcription.text.strip() if transcription else ""
                    logger.info("local_whisper_transcription_result", call_id=call_id, recognized_text=user_text)
                except Exception as e:
                    logger.warning("local_whisper_error", error=str(e))

            if not user_text or len(user_text.strip()) < 2:
                logger.debug("call_stt_silence_or_empty_ignored")
                return

            cleaned = user_text.lower().strip(" .,!?:;\n\t\"'")
            logger.info("whatsapp_call_caller_spoke", call_id=call_id, text=user_text)

            # Filter pure noise hallucinations & non-speech transcripts
            NOISE_PHRASES = {
                "", "thank you for watching", "thanks for watching", "subtitles by",
                "amara.org", "[silence]", "[applause]", "you", "bye", "thank you.",
                "so", "the end", "transcription by", "music", "[music]", "[laughter]",
                "laughter", "cough", "throat clearing", "applause", "hmm", "um", "uh", "ah"
            }
            if cleaned in NOISE_PHRASES:
                logger.debug("call_noise_ignored", text=user_text)
                return

            # Check-in greetings
            if cleaned in ("hello", "hello?", "hi", "hey", "are you there", "are you there?", "sun rahe ho", "kya aap sun rahe ho"):
                quick_reply = "Yes, I am listening! Please tell me, how can I assist you with your project today?"
                if call_id in self.call_history:
                    self.call_history[call_id].append({"role": "user", "content": user_text})
                    self.call_history[call_id].append({"role": "assistant", "content": quick_reply})
                await self._synthesize_and_speak(ai_track, quick_reply)
                return

            # 2. Record caller question into conversation history
            if call_id not in self.call_history:
                self.call_history[call_id] = [
                    {"role": "assistant", "content": DEFAULT_GREETING}
                ]
            self.call_history[call_id].append({"role": "user", "content": user_text})

            # 3. Stream Response with Full Context and Real-Time Sentence TTS
            if client:
                await self._stream_response_and_speak(user_text, ai_track, call_id, client)
            else:
                from whatsapp_agent.agents.llm_provider import get_llm_provider
                llm = get_llm_provider()
                ai_resp = await llm.complete(
                    system_prompt=VOICE_SYSTEM_PROMPT,
                    user_message=user_text,
                    temperature=0.3,
                    max_tokens=60,
                )
                ai_text = ai_resp.content.strip()
                self.call_history[call_id].append({"role": "assistant", "content": ai_text})
                await self._synthesize_and_speak(ai_track, ai_text)

        except asyncio.CancelledError:
            logger.info("user_turn_cancelled_due_to_interruption", call_id=call_id)
        except Exception as e:
            logger.error("error_handling_user_turn", call_id=call_id, error=str(e))

    async def _stream_response_and_speak(
        self,
        user_text: str,
        ai_track: AIAudioTrack,
        call_id: str,
        client: Any,
    ) -> None:
        """
        Stream tokens from LLM using full conversation history and synthesize
        each complete sentence immediately with high-fidelity anti-aliasing.
        """
        # Retrieve recent history (sliding window of last 8 turns = 4 full exchanges)
        history = self.call_history.get(call_id, [])
        recent_history = history[-8:] if len(history) > 8 else list(history)

        messages = [{"role": "system", "content": VOICE_SYSTEM_PROMPT}] + recent_history

        try:
            stream = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                temperature=0.3,
                max_tokens=80,
                stream=True,
            )

            current_sentence = ""
            delimiters = (".", "!", "?", "\n")
            full_reply = []

            async for chunk in stream:
                delta = chunk.choices[0].delta.content or ""
                if not delta:
                    continue
                current_sentence += delta
                full_reply.append(delta)

                # Synthesize on complete grammatical sentence
                if any(d in current_sentence for d in delimiters) and len(current_sentence.strip()) >= 15:
                    sentence_to_play = current_sentence.strip()
                    current_sentence = ""
                    await self._synthesize_and_speak(ai_track, sentence_to_play)

            # Synthesize any trailing text
            if current_sentence.strip():
                await self._synthesize_and_speak(ai_track, current_sentence.strip())

            complete_ai_text = "".join(full_reply).strip()
            if complete_ai_text:
                if call_id in self.call_history:
                    self.call_history[call_id].append({"role": "assistant", "content": complete_ai_text})
                logger.info("streamed_voice_turn_completed", call_id=call_id, ai_reply=complete_ai_text)
            else:
                fallback_text = "I hear you. Could you please share more details about what you need?"
                if call_id in self.call_history:
                    self.call_history[call_id].append({"role": "assistant", "content": fallback_text})
                await self._synthesize_and_speak(ai_track, fallback_text)

        except asyncio.CancelledError:
            logger.info("streaming_turn_cancelled", call_id=call_id)
            raise
        except Exception as e:
            logger.error("error_in_streaming_turn", call_id=call_id, error=str(e))
            fallback_text = "Associative provides custom software, mobile apps, and AI solutions. How can we help with your project?"
            if call_id in self.call_history:
                self.call_history[call_id].append({"role": "assistant", "content": fallback_text})
            await self._synthesize_and_speak(ai_track, fallback_text)

    async def _synthesize_and_speak(self, ai_track: AIAudioTrack, text: str) -> None:
        """
        Synthesize text into speech and queue to the caller's audio track.
        """
        clean_text = text.strip()
        if not clean_text:
            return

        logger.info("synthesizing_speech_for_call", text=clean_text[:80])
        pcm_bytes, rate = await self._generate_pcm_speech(clean_text)
        if pcm_bytes:
            ai_track.queue_pcm_audio(pcm_bytes, in_sample_rate=rate)
            logger.info("speech_streamed_to_call", bytes_len=len(pcm_bytes))
            return

        # Fallback audible pleasant chime so caller knows line is live
        try:
            import math
            samples = bytearray()
            for i in range(16000):  # 1-second chime
                freq = 523.25 if i < 8000 else 659.25  # C5 then E5
                val = int(4000 * math.sin(2 * math.pi * freq * i / 16000))
                samples.extend(val.to_bytes(2, byteorder="little", signed=True))
            ai_track.queue_pcm_audio(bytes(samples), in_sample_rate=16000)
            logger.info("chime_streamed_to_call")
        except Exception as e:
            logger.error("all_tts_fallbacks_failed", error=str(e))

    async def _cleanup_call(self, call_id: str) -> None:
        """
        Close RTCPeerConnection and release call resources.
        """
        task = self.call_turn_tasks.pop(call_id, None)
        if task and not task.done():
            task.cancel()

        pc = self.active_calls.pop(call_id, None)
        self.call_tracks.pop(call_id, None)
        self.call_history.pop(call_id, None)
        if pc:
            try:
                await pc.close()
            except Exception:
                pass
        logger.info("whatsapp_call_closed_and_cleaned", call_id=call_id)


# Global singleton instance
_call_manager: WhatsAppCallManager | None = None


def get_call_manager() -> WhatsAppCallManager:
    global _call_manager
    if _call_manager is None:
        _call_manager = WhatsAppCallManager()
    return _call_manager
