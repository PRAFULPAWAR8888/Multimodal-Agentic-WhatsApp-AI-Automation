import json
import base64
import audioop
import wave
import io
import asyncio
import uuid
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Body
from fastapi.responses import HTMLResponse, JSONResponse
from loguru import logger

from whatsapp_agent.voice.stt.faster_whisper import get_stt_provider
from whatsapp_agent.voice.tts.piper_tts import get_tts_provider
from whatsapp_agent.workflows.main_workflow import get_workflow

router = APIRouter()

# Energy threshold for Voice Activity Detection (8kHz linear PCM RMS)
VAD_ENERGY_THRESHOLD = 900
INTERRUPT_ENERGY_THRESHOLD = 2600  # High energy required to interrupt while AI is speaking
SILENCE_FRAMES_THRESHOLD = 25      # ~500ms of quiet before considering speech turn completed
MIN_SPEECH_FRAMES = 12             # At least ~240ms of actual speech frames above threshold

@router.websocket("/ws/twilio/stream")
async def twilio_media_stream(websocket: WebSocket):
    """
    WebSocket endpoint for Twilio Media Streams (Live AI Phone Agents).
    Handles bi-directional audio streaming with VAD and Interruptibility.
    Twilio sends 8kHz mulaw base64 encoded audio payloads.
    """
    await websocket.accept()
    logger.info("twilio_websocket_connected")
    
    stream_sid = None
    
    # VAD State
    audio_buffer = bytearray()
    silence_frames = 0
    speech_frames = 0
    interrupt_frames = 0
    is_user_speaking = False
    
    # Interruption State
    ai_speaking = False
    current_response_task = None
    
    # Providers
    stt = get_stt_provider()
    tts = get_tts_provider()
    workflow = get_workflow()
    
    workspace_id = "00000000-0000-0000-0000-000000000001"
    try:
        from whatsapp_agent.database.session import _get_session_factory
        from whatsapp_agent.database.models import Workspace
        from sqlalchemy import select
        factory = _get_session_factory()
        async with factory() as db:
            ws = (await db.execute(select(Workspace).limit(1))).scalar_one_or_none()
            if ws:
                workspace_id = str(ws.id)
    except Exception:
        pass
    contact_id = "phone-caller-" + str(uuid.uuid4())[:8]

    async def process_speech_and_respond(mulaw_bytes: bytes, sid: str):
        """Background task to run STT -> LLM -> TTS -> Twilio"""
        nonlocal ai_speaking
        try:
            # 1. Convert accumulated 8kHz mulaw to 8kHz linear PCM
            linear_pcm = audioop.ulaw2lin(mulaw_bytes, 2)
            
            # 2. Package as a standard WAV file in memory
            wav_io = io.BytesIO()
            with wave.open(wav_io, 'wb') as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(8000)
                wav_file.writeframes(linear_pcm)
            wav_bytes = wav_io.getvalue()
            
            # 3. Transcribe with Whisper (High-Accuracy OpenAI Whisper with local Faster-Whisper fallback)
            logger.info("twilio_stt_started", stream_sid=sid)
            user_text = ""
            from whatsapp_agent.config.settings import get_settings
            settings = get_settings()

            if settings.openai_api_key:
                try:
                    from openai import AsyncOpenAI
                    client = AsyncOpenAI(api_key=settings.openai_api_key)
                    wav_bio = io.BytesIO(wav_bytes)
                    wav_bio.name = "caller.wav"
                    tr_resp = await asyncio.wait_for(
                        client.audio.transcriptions.create(
                            model="whisper-1",
                            file=wav_bio,
                            language="en",
                            prompt="Live customer phone call with Anand Kumar at Associative discussing software, web apps, job applications, or project discovery."
                        ),
                        timeout=3.0
                    )
                    user_text = tr_resp.text.strip()
                except Exception as cloud_stt_err:
                    logger.warning(f"cloud_stt_fallback_to_local: {cloud_stt_err}")

            if not user_text:
                stt_result = await stt.transcribe_bytes(wav_bytes, audio_format="wav")
                user_text = stt_result.text.strip()
            
            # Discard empty, silence, or noise hallucinations
            if not user_text or len(user_text.strip()) < 2:
                logger.debug("twilio_stt_silence_ignored", stream_sid=sid)
                return

            cleaned = user_text.lower().strip(" .,!?:;\n\t\"'")
            WHISPER_NOISE_PHRASES = {
                "", "you", "thank you", "thank you.", "thanks", "thanks for watching",
                "thank you for watching", "thank you for watching.", "subtitles by",
                "bye", "bye.", "okay", "okay.", "um", "uh", "so", "hello?", "yes", "yeah",
                "all right", "alright", "silence", "[silence]", "[applause]", "[music]"
            }
            if cleaned in WHISPER_NOISE_PHRASES:
                logger.debug("twilio_stt_whisper_noise_ignored", text=user_text, stream_sid=sid)
                return
                
            logger.info("twilio_user_said", text=user_text, stream_sid=sid)
            try:
                await websocket.send_text(json.dumps({"event": "transcript", "role": "user", "text": user_text}))
            except Exception:
                pass
            
            # Fast keyword check for escalation / frustration (zero latency overhead)
            FRUSTRATION_KEYWORDS = {"angry", "manager", "human", "agent", "supervisor", "escalate", "frustrated", "cheat", "scam", "lawyer", "sue", "cancel"}
            text_lower = user_text.lower()
            if any(kw in text_lower for kw in FRUSTRATION_KEYWORDS):
                logger.warning("twilio_live_sentiment_escalation", stream_sid=sid, text=user_text)
                handoff_msg = "I understand this is frustrating. I am transferring your call to a human representative right now. Please hold the line."
                ai_speaking = True
                handoff_audio = await tts.generate_twilio_audio(handoff_msg)
                await websocket.send_text(json.dumps({"event": "clear", "streamSid": sid}))
                for i in range(0, len(handoff_audio), 4000):
                    if not ai_speaking:
                        break
                    chunk = handoff_audio[i:i+4000]
                    payload_base64 = base64.b64encode(chunk).decode('utf-8')
                    await websocket.send_text(json.dumps({
                        "event": "media",
                        "streamSid": sid,
                        "media": {"payload": payload_base64}
                    }))
                    await asyncio.sleep(0.05)
                ai_speaking = False
                try:
                    await websocket.send_text(json.dumps({"event": "ai_finished", "streamSid": sid}))
                except Exception:
                    pass
                return

            # 4. Instant Conversational Phone Agent Turn (Anand Kumar)
            # Ultra-low latency single-shot generation tailored for live phone calls
            from whatsapp_agent.agents.llm_provider import get_llm_provider
            llm = get_llm_provider()

            voice_system_prompt = (
                "You are Anand Kumar representing Associative (a software, web, mobile app, and AI development company). "
                "You are on a LIVE PHONE CALL with a customer. "
                "CRITICAL RULES: "
                "1. Keep response strictly to 1 or 2 concise, conversational sentences (maximum 25 words). "
                "2. Speak naturally in clear, professional English without any markdown, bullets, or asterisks. "
                "3. If they ask about services: state Associative provides custom software, websites, mobile apps, and AI solutions, and offer a discovery call. "
                "4. If they are a job seeker: warmly acknowledge their application, confirm their details are saved, and inform them that if selected for the role, our HR team will contact them for an interview schedule. "
                "5. Contact: website associative.in, phone +91 97669 82828."
            )

            try:
                logger.info("twilio_agent_running", stream_sid=sid)
                ai_resp = await asyncio.wait_for(
                    llm.complete(
                        system_prompt=voice_system_prompt,
                        user_message=user_text,
                        temperature=0.3,
                        max_tokens=65
                    ),
                    timeout=2.5
                )
                ai_text = ai_resp.content.strip()
            except Exception as e:
                logger.warning(f"fast_voice_llm_fallback: {e}")
                ai_text = "Hello! Associative provides custom software, web, and AI solutions. How can I assist you with your project today?"

            logger.info("twilio_ai_replied", text=ai_text, stream_sid=sid)
            try:
                await websocket.send_text(json.dumps({"event": "transcript", "role": "ai", "text": ai_text}))
            except Exception:
                pass

            # 4.5 Persist call transcript to customer history
            try:
                from whatsapp_agent.database.session import _get_session_factory
                from whatsapp_agent.database.models.whatsapp import (
                    WhatsAppAccount, WhatsAppContact, WhatsAppConversation,
                    WhatsAppMessage, MessageDirection, MessageType, MessageStatus, Modality
                )
                from sqlalchemy import select
                from datetime import datetime

                factory = _get_session_factory()
                async with factory() as db:
                    ws_id_uuid = uuid.UUID(workspace_id)
                    acct = (await db.execute(select(WhatsAppAccount).where(WhatsAppAccount.workspace_id == ws_id_uuid).limit(1))).scalar_one_or_none()
                    if acct:
                        contact = (await db.execute(select(WhatsAppContact).where(
                            WhatsAppContact.workspace_id == ws_id_uuid,
                            WhatsAppContact.wa_id == contact_id
                        ).limit(1))).scalar_one_or_none()
                        if not contact:
                            contact = WhatsAppContact(
                                workspace_id=ws_id_uuid,
                                wa_id=contact_id,
                                phone_number=contact_id,
                                display_name="Voice Caller"
                            )
                            db.add(contact)
                            await db.flush()

                        conv = (await db.execute(select(WhatsAppConversation).where(
                            WhatsAppConversation.workspace_id == ws_id_uuid,
                            WhatsAppConversation.contact_id == contact.id
                        ).limit(1))).scalar_one_or_none()
                        if not conv:
                            conv = WhatsAppConversation(
                                workspace_id=ws_id_uuid,
                                account_id=acct.id,
                                contact_id=contact.id
                            )
                            db.add(conv)
                            await db.flush()

                        in_msg = WhatsAppMessage(
                            workspace_id=ws_id_uuid,
                            conversation_id=conv.id,
                            account_id=acct.id,
                            contact_id=contact.id,
                            wamid=f"call-in-{uuid.uuid4()}",
                            direction=MessageDirection.INBOUND,
                            message_type=MessageType.AUDIO,
                            modality=Modality.VOICE,
                            body=user_text,
                            transcription=user_text,
                            is_voice_note=True,
                            status=MessageStatus.RECEIVED,
                            timestamp=datetime.now()
                        )
                        out_msg = WhatsAppMessage(
                            workspace_id=ws_id_uuid,
                            conversation_id=conv.id,
                            account_id=acct.id,
                            contact_id=contact.id,
                            wamid=f"call-out-{uuid.uuid4()}",
                            direction=MessageDirection.OUTBOUND,
                            message_type=MessageType.AUDIO,
                            modality=Modality.VOICE,
                            body=ai_text,
                            transcription=ai_text,
                            is_voice_note=True,
                            status=MessageStatus.SENT,
                            timestamp=datetime.now()
                        )
                        conv.message_count += 2
                        conv.ai_message_count += 1
                        conv.last_message_at = out_msg.timestamp
                        db.add(in_msg)
                        db.add(out_msg)
                        await db.commit()
                        logger.info("twilio_call_logged_to_history", stream_sid=sid, conversation_id=str(conv.id))
            except Exception as db_err:
                logger.error(f"twilio_call_logging_failed: {db_err}")
            
            # 5. Generate TTS via Piper / Cloud
            ai_speaking = True
            logger.info("twilio_tts_started", stream_sid=sid)
            ai_mulaw_bytes = await tts.generate_twilio_audio(ai_text)
            
            # 6. Stream back to Twilio / Web Phone
            CHUNK_SIZE = 4000
            for i in range(0, len(ai_mulaw_bytes), CHUNK_SIZE):
                if not ai_speaking:
                    logger.info("twilio_playback_interrupted", stream_sid=sid)
                    break
                    
                chunk = ai_mulaw_bytes[i:i+CHUNK_SIZE]
                payload_base64 = base64.b64encode(chunk).decode('utf-8')
                
                await websocket.send_text(json.dumps({
                    "event": "media",
                    "streamSid": sid,
                    "media": {
                        "payload": payload_base64
                    }
                }))
                await asyncio.sleep(0.08)

            try:
                await websocket.send_text(json.dumps({"event": "ai_finished", "streamSid": sid}))
            except Exception:
                pass

        except asyncio.CancelledError:
            logger.info("twilio_process_cancelled_by_interruption", stream_sid=sid)
        except Exception as e:
            logger.error(f"twilio_process_failed: {e}", exc_info=True, stream_sid=sid)
        finally:
            ai_speaking = False


    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            event = message.get("event")
            
            if event == "connected":
                logger.info("twilio_stream_connected")
                
            elif event == "start":
                stream_sid = message["start"]["streamSid"]
                logger.info("twilio_stream_started", stream_sid=stream_sid)

            elif event == "interrupt":
                logger.info("twilio_manual_interrupt_requested", stream_sid=stream_sid)
                ai_speaking = False
                if current_response_task and not current_response_task.done():
                    current_response_task.cancel()
                await websocket.send_text(json.dumps({
                    "event": "clear",
                    "streamSid": stream_sid
                }))
                audio_buffer.clear()
                is_user_speaking = False
                speech_frames = 0
                silence_frames = 0
                interrupt_frames = 0
                
            elif event == "media":
                if not stream_sid:
                    continue
                    
                payload = message["media"]["payload"]
                audio_chunk = base64.b64decode(payload)
                
                # VAD using audioop RMS (Root Mean Square energy)
                linear_chunk = audioop.ulaw2lin(audio_chunk, 2)
                energy = audioop.rms(linear_chunk, 2)
                
                # If AI is currently speaking:
                if ai_speaking:
                    # Echo prevention: discard normal audio so speakers don't loop back
                    if energy > INTERRUPT_ENERGY_THRESHOLD:
                        interrupt_frames += 1
                        if interrupt_frames >= 6: # ~120ms of firm loud user interruption
                            logger.info("twilio_interrupted_by_caller_voice", stream_sid=stream_sid, energy=energy)
                            ai_speaking = False
                            if current_response_task and not current_response_task.done():
                                current_response_task.cancel()
                            await websocket.send_text(json.dumps({
                                "event": "clear",
                                "streamSid": stream_sid
                            }))
                            audio_buffer.clear()
                            is_user_speaking = True
                            speech_frames = interrupt_frames
                            silence_frames = 0
                    else:
                        interrupt_frames = 0
                    continue

                # If AI is NOT speaking:
                interrupt_frames = 0
                if energy > VAD_ENERGY_THRESHOLD:
                    silence_frames = 0
                    speech_frames += 1
                    if not is_user_speaking:
                        is_user_speaking = True
                        logger.debug("twilio_vad_speech_started")
                    audio_buffer.extend(audio_chunk)
                else:
                    if is_user_speaking:
                        silence_frames += 1
                        audio_buffer.extend(audio_chunk)
                        
                        # Turn complete when silence threshold is reached
                        if silence_frames > SILENCE_FRAMES_THRESHOLD:
                            is_user_speaking = False
                            logger.debug("twilio_vad_speech_ended", speech_frames=speech_frames)
                            
                            speech_bytes = bytes(audio_buffer)
                            audio_buffer.clear()
                            
                            # Discard transient blips, breaths, clicks
                            if speech_frames >= MIN_SPEECH_FRAMES and len(speech_bytes) >= 9600:
                                current_response_task = asyncio.create_task(
                                    process_speech_and_respond(speech_bytes, stream_sid)
                                )
                            else:
                                logger.debug("twilio_vad_dropped_short_noise", speech_frames=speech_frames, total_bytes=len(speech_bytes))
                            
                            speech_frames = 0
                            silence_frames = 0
                                
            elif event == "stop":
                logger.info("twilio_stream_stopped", stream_sid=stream_sid)
                break
                
    except WebSocketDisconnect:
        logger.info("twilio_websocket_disconnected", stream_sid=stream_sid)
    except Exception as e:
        logger.error("twilio_websocket_error", error=str(e), stream_sid=stream_sid)
    finally:
        if current_response_task and not current_response_task.done():
            current_response_task.cancel()


@router.post("/api/voice/synthesize-mulaw")
async def synthesize_caller_mulaw(data: dict = Body(...)):
    """Synthesizes caller speech as 8kHz mu-law audio for realistic telephony simulation."""
    text = data.get("text", "").strip()
    if not text:
        return JSONResponse(status_code=400, content={"error": "Text is required"})
    try:
        from whatsapp_agent.config.settings import get_settings
        from openai import AsyncOpenAI
        import audioop
        settings = get_settings()
        client = AsyncOpenAI(api_key=settings.openai_api_key)
        speech_resp = await client.audio.speech.create(
            model="tts-1",
            voice="alloy",
            input=text[:500],
            response_format="pcm"
        )
        pcm_24k = speech_resp.content
        pcm_8k, _ = audioop.ratecv(pcm_24k, 2, 1, 24000, 8000, None)
        mulaw_bytes = audioop.lin2ulaw(pcm_8k, 2)
        b64 = base64.b64encode(mulaw_bytes).decode("utf-8")
        return {"mulaw_b64": b64, "length_bytes": len(mulaw_bytes)}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.get("/voice-call-test", response_class=HTMLResponse)
async def voice_call_tester_page():
    """Interactive Web Phone Simulator with Push-to-Talk, Echo Cancellation, and Live VU Meter."""
    html_content = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Associative AI Voice Call Tester — Anand Kumar</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Plus Jakarta Sans', sans-serif; }
    body {
      background: radial-gradient(circle at top, #1e293b, #0f172a 75%);
      color: #f8fafc;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      padding: 20px 16px;
    }
    .phone-container {
      width: 100%;
      max-width: 460px;
      background: #111827;
      border: 1px solid rgba(255,255,255,0.12);
      border-radius: 36px;
      padding: 28px 22px;
      box-shadow: 0 25px 60px -15px rgba(0,0,0,0.7), 0 0 40px rgba(37,211,102,0.12);
      display: flex;
      flex-direction: column;
      align-items: center;
      position: relative;
    }
    .badge-row {
      display: flex;
      gap: 8px;
      margin-bottom: 16px;
    }
    .badge {
      font-size: 11px;
      font-weight: 700;
      letter-spacing: 0.06em;
      text-transform: uppercase;
      background: rgba(37, 211, 102, 0.15);
      color: #25d366;
      border: 1px solid rgba(37, 211, 102, 0.3);
      padding: 4px 10px;
      border-radius: 999px;
    }
    .badge.echo {
      background: rgba(56, 189, 248, 0.15);
      color: #38bdf8;
      border-color: rgba(56, 189, 248, 0.3);
    }
    .avatar-wrapper {
      position: relative;
      width: 100px;
      height: 100px;
      margin-bottom: 12px;
    }
    .avatar-pulse {
      position: absolute;
      inset: -8px;
      border-radius: 50%;
      background: rgba(37, 211, 102, 0.25);
      animation: pulse 2s infinite ease-out;
      opacity: 0;
    }
    .avatar-pulse.speaking {
      background: rgba(56, 189, 248, 0.4);
      opacity: 1;
      animation: speakingPulse 1.1s infinite ease-in-out;
    }
    @keyframes pulse {
      0% { transform: scale(0.9); opacity: 0.8; }
      100% { transform: scale(1.4); opacity: 0; }
    }
    @keyframes speakingPulse {
      0%, 100% { transform: scale(1.0); }
      50% { transform: scale(1.22); }
    }
    .avatar {
      width: 100%;
      height: 100%;
      border-radius: 50%;
      background: linear-gradient(135deg, #059669, #0d9488);
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 40px;
      border: 3px solid rgba(255,255,255,0.2);
      box-shadow: 0 10px 25px rgba(0,0,0,0.4);
    }
    .agent-name {
      font-size: 21px;
      font-weight: 800;
      letter-spacing: -0.02em;
      margin-bottom: 3px;
    }
    .agent-role {
      font-size: 12px;
      color: #94a3b8;
      margin-bottom: 10px;
    }
    .call-status {
      font-size: 13px;
      font-weight: 600;
      color: #38bdf8;
      display: flex;
      align-items: center;
      gap: 6px;
      margin-bottom: 14px;
      min-height: 20px;
    }
    .status-dot {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: #38bdf8;
    }
    .status-dot.active { background: #22c55e; animation: blink 1.5s infinite; }
    @keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }

    /* Mode Selector Pill Bar */
    .mode-bar {
      display: flex;
      background: rgba(255,255,255,0.06);
      padding: 4px;
      border-radius: 12px;
      gap: 4px;
      margin-bottom: 14px;
      width: 100%;
    }
    .mode-btn {
      flex: 1;
      padding: 7px 10px;
      border-radius: 8px;
      border: none;
      font-size: 12px;
      font-weight: 600;
      background: transparent;
      color: #94a3b8;
      cursor: pointer;
      transition: all 0.15s ease;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 5px;
    }
    .mode-btn.active {
      background: #0f172a;
      color: #38bdf8;
      box-shadow: 0 2px 8px rgba(0,0,0,0.4);
      border: 1px solid rgba(56, 189, 248, 0.3);
    }

    /* Live VU Meter */
    .vu-meter-container {
      width: 100%;
      margin-bottom: 14px;
      display: flex;
      flex-direction: column;
      gap: 4px;
    }
    .vu-label {
      display: flex;
      justify-content: space-between;
      font-size: 11px;
      color: #64748b;
      font-weight: 600;
    }
    .vu-track {
      width: 100%;
      height: 6px;
      background: rgba(255,255,255,0.08);
      border-radius: 99px;
      overflow: hidden;
      position: relative;
    }
    .vu-level {
      width: 0%;
      height: 100%;
      background: linear-gradient(90deg, #22c55e, #eab308, #ef4444);
      transition: width 0.08s ease;
      border-radius: 99px;
    }

    /* Main Action Row */
    .actions-row {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 12px;
      margin-bottom: 16px;
      width: 100%;
    }
    .call-action-btn {
      width: 68px;
      height: 68px;
      border-radius: 50%;
      border: none;
      display: flex;
      align-items: center;
      justify-content: center;
      cursor: pointer;
      font-size: 28px;
      transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
      box-shadow: 0 10px 25px rgba(0,0,0,0.5);
    }
    .call-action-btn:hover { transform: scale(1.08); }
    .call-action-btn:active { transform: scale(0.95); }
    .btn-start { background: linear-gradient(135deg, #22c55e, #16a34a); color: white; }
    .btn-end { background: linear-gradient(135deg, #ef4444, #dc2626); color: white; display: none; }

    /* Push-to-Talk Big Button */
    .ptt-btn {
      flex: 1;
      height: 52px;
      background: rgba(37, 211, 102, 0.15);
      border: 1px solid rgba(37, 211, 102, 0.4);
      color: #25d366;
      border-radius: 14px;
      font-size: 13px;
      font-weight: 700;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      user-select: none;
      touch-action: none;
      transition: all 0.15s ease;
    }
    .ptt-btn:hover { background: rgba(37, 211, 102, 0.22); }
    .ptt-btn.active {
      background: #25d366 !important;
      color: #000 !important;
      box-shadow: 0 0 25px rgba(37, 211, 102, 0.6);
      transform: scale(0.98);
    }

    .aux-btn {
      padding: 0 14px;
      height: 52px;
      background: rgba(255,255,255,0.06);
      border: 1px solid rgba(255,255,255,0.1);
      color: #cbd5e1;
      border-radius: 14px;
      font-size: 12px;
      font-weight: 600;
      cursor: pointer;
      display: flex;
      align-items: center;
      gap: 6px;
      transition: all 0.15s ease;
    }
    .aux-btn:hover { background: rgba(255,255,255,0.12); color: white; }
    .aux-btn.muted {
      background: rgba(239, 68, 68, 0.18);
      border-color: rgba(239, 68, 68, 0.4);
      color: #f87171;
    }
    .btn-interrupt {
      display: none;
      background: rgba(234, 179, 8, 0.18);
      border-color: rgba(234, 179, 8, 0.4);
      color: #facc15;
    }
    .btn-interrupt:hover {
      background: rgba(234, 179, 8, 0.3);
      color: #fef08a;
    }

    .transcript-box {
      width: 100%;
      background: rgba(15, 23, 42, 0.85);
      border: 1px solid rgba(255,255,255,0.08);
      border-radius: 16px;
      padding: 12px;
      margin-top: 10px;
      min-height: 110px;
      max-height: 170px;
      overflow-y: auto;
      font-size: 13px;
      display: flex;
      flex-direction: column;
      gap: 8px;
    }
    .msg-user {
      align-self: flex-end;
      background: #065f46;
      color: #ecfdf5;
      padding: 8px 12px;
      border-radius: 12px 12px 2px 12px;
      max-width: 85%;
      line-height: 1.4;
    }
    .msg-ai {
      align-self: flex-start;
      background: #1e293b;
      color: #f1f5f9;
      padding: 8px 12px;
      border-radius: 12px 12px 12px 2px;
      max-width: 85%;
      border-left: 3px solid #25d366;
      line-height: 1.4;
    }

    .presets-container {
      width: 100%;
      margin-top: 14px;
      display: flex;
      flex-direction: column;
      gap: 6px;
    }
    .presets-title {
      font-size: 11px;
      color: #64748b;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      margin-bottom: 2px;
    }
    .preset-btn {
      background: rgba(255,255,255,0.04);
      border: 1px solid rgba(255,255,255,0.08);
      color: #cbd5e1;
      padding: 7px 11px;
      border-radius: 9px;
      font-size: 12px;
      text-align: left;
      cursor: pointer;
      transition: all 0.15s;
    }
    .preset-btn:hover {
      background: rgba(255,255,255,0.09);
      color: white;
      border-color: rgba(37,211,102,0.4);
    }
    .custom-input-row {
      display: flex;
      gap: 6px;
      width: 100%;
      margin-top: 8px;
    }
    .custom-input {
      flex: 1;
      background: rgba(255,255,255,0.06);
      border: 1px solid rgba(255,255,255,0.1);
      padding: 8px 12px;
      border-radius: 8px;
      color: white;
      font-size: 12px;
      outline: none;
    }
    .custom-input:focus { border-color: #25d366; }
    .custom-send-btn {
      background: #25d366;
      border: none;
      color: black;
      font-weight: 700;
      padding: 0 14px;
      border-radius: 8px;
      font-size: 12px;
      cursor: pointer;
    }
  </style>
</head>
<body>

  <div class="phone-container">
    <div class="badge-row">
      <div class="badge">Live 8kHz &mu;-Law</div>
      <div class="badge echo">Echo Suppression Active</div>
    </div>
    
    <div class="avatar-wrapper">
      <div id="avatarPulse" class="avatar-pulse"></div>
      <div class="avatar">👨‍💼</div>
    </div>

    <div class="agent-name">Anand Kumar</div>
    <div class="agent-role">Associative Technologies</div>

    <div class="call-status">
      <span id="statusDot" class="status-dot"></span>
      <span id="statusText">Ready to start call</span>
    </div>

    <!-- Mode Selector -->
    <div class="mode-bar">
      <button id="modePtt" class="mode-btn active" onclick="setMode('ptt')">
        🎙️ Push-to-Talk (Hold Space)
      </button>
      <button id="modeHandsFree" class="mode-btn" onclick="setMode('hands-free')">
        🔊 Hands-Free (Auto)
      </button>
    </div>

    <!-- Live Microphone Audio VU Meter -->
    <div class="vu-meter-container">
      <div class="vu-label">
        <span id="vuStatusLabel">Microphone Input Level</span>
        <span id="vuValueLabel">0%</span>
      </div>
      <div class="vu-track">
        <div id="vuLevel" class="vu-level"></div>
      </div>
    </div>

    <!-- Main Call & Microphone Action Bar -->
    <div class="actions-row">
      <button id="btnStart" class="call-action-btn btn-start" title="Call Anand Kumar">📞</button>
      <button id="btnEnd" class="call-action-btn btn-end" title="End Call">🔴</button>

      <button id="btnPtt" class="ptt-btn" style="display:none;">
        🎙️ HOLD TO SPEAK
      </button>

      <button id="btnMute" class="aux-btn" style="display:none;" onclick="toggleMute()">
        🎤 Mic Live
      </button>

      <button id="btnInterrupt" class="aux-btn btn-interrupt" onclick="sendManualInterrupt()">
        ✋ Stop Anand
      </button>
    </div>

    <!-- Transcripts -->
    <div id="transcriptBox" class="transcript-box">
      <div class="msg-ai"><strong>Anand:</strong> Ready. Click 📞 Call to start your live phone conversation.</div>
    </div>

    <!-- Presets & Custom Simulation -->
    <div class="presets-container">
      <div class="presets-title">Simulate Caller Speech:</div>
      <button class="preset-btn" onclick="simulateSpeech('Hello Anand, what services does Associative offer?')">
        💼 "What services does Associative offer?"
      </button>
      <button class="preset-btn" onclick="simulateSpeech('Hi Anand, I am a Python and React developer looking for a job at Associative.')">
        🧑‍💻 "I am a developer looking for a job at Associative."
      </button>
      <button class="preset-btn" onclick="simulateSpeech('Can you help me schedule a project discovery consultation?')">
        📅 "Can I schedule a project discovery consultation?"
      </button>
      <button class="preset-btn" onclick="simulateSpeech('I want to speak with a human manager right now, I am very frustrated!')">
        😠 "Transfer me to a human manager right now!"
      </button>
      
      <div class="custom-input-row">
        <input type="text" id="customTextInput" class="custom-input" placeholder="Type custom speech..." onkeydown="if(event.key==='Enter') sendCustomSpeech()">
        <button class="custom-send-btn" onclick="sendCustomSpeech()">Speak</button>
      </div>
    </div>
  </div>

  <script>
    let ws = null;
    let streamSid = null;
    let audioCtx = null;
    let mediaStream = null;
    let scriptNode = null;
    let nextPlayTime = 0;
    let callTimer = null;
    let callSeconds = 0;
    let isConnected = false;
    let currentMode = 'ptt'; // 'ptt' or 'hands-free'
    let isPttActive = false;
    let isMuted = false;
    let isAiSpeaking = false;

    const btnStart = document.getElementById('btnStart');
    const btnEnd = document.getElementById('btnEnd');
    const btnPtt = document.getElementById('btnPtt');
    const btnMute = document.getElementById('btnMute');
    const btnInterrupt = document.getElementById('btnInterrupt');
    const modePtt = document.getElementById('modePtt');
    const modeHandsFree = document.getElementById('modeHandsFree');
    const statusText = document.getElementById('statusText');
    const statusDot = document.getElementById('statusDot');
    const avatarPulse = document.getElementById('avatarPulse');
    const transcriptBox = document.getElementById('transcriptBox');
    const vuLevel = document.getElementById('vuLevel');
    const vuStatusLabel = document.getElementById('vuStatusLabel');
    const vuValueLabel = document.getElementById('vuValueLabel');

    function setMode(mode) {
      currentMode = mode;
      if (mode === 'ptt') {
        modePtt.className = 'mode-btn active';
        modeHandsFree.className = 'mode-btn';
        if (isConnected) {
          btnPtt.style.display = 'flex';
          btnMute.style.display = 'none';
          statusText.innerText = "Connected • Hold button to speak";
        }
      } else {
        modePtt.className = 'mode-btn';
        modeHandsFree.className = 'mode-btn active';
        if (isConnected) {
          btnPtt.style.display = 'none';
          btnMute.style.display = 'flex';
          statusText.innerText = isAiSpeaking ? "Anand is speaking..." : "Connected • Listening to you...";
        }
      }
    }

    function toggleMute() {
      isMuted = !isMuted;
      if (isMuted) {
        btnMute.className = 'aux-btn muted';
        btnMute.innerText = '🔇 Muted';
        vuStatusLabel.innerText = 'Mic Muted';
        vuLevel.style.width = '0%';
        vuValueLabel.innerText = '0%';
      } else {
        btnMute.className = 'aux-btn';
        btnMute.innerText = '🎤 Mic Live';
        vuStatusLabel.innerText = 'Microphone Input Level';
      }
    }

    function mulawToFloat(mulawBytes) {
      const pcm = new Float32Array(mulawBytes.length);
      for (let i = 0; i < mulawBytes.length; i++) {
        let u = ~mulawBytes[i] & 0xff;
        let sign = (u & 0x80);
        let exponent = (u >> 4) & 0x07;
        let mantissa = u & 0x0f;
        let sample = ((mantissa << 3) + 0x84) << exponent;
        sample -= 0x84;
        sample = sign ? -sample : sample;
        pcm[i] = sample / 32768.0;
      }
      return pcm;
    }

    function floatToMulaw(sample) {
      const BIAS = 0x84;
      const CLIP = 32635;
      let s = Math.max(-1, Math.min(1, sample));
      let intSample = Math.floor(s * 32767);
      let sign = (intSample < 0) ? 0x80 : 0;
      if (intSample < 0) intSample = -intSample;
      if (intSample > CLIP) intSample = CLIP;
      intSample += BIAS;
      let exponent = 7;
      for (let expMask = 0x4000; (intSample & expMask) === 0 && exponent > 0; expMask >>= 1) exponent--;
      let mantissa = (intSample >> (exponent + 3)) & 0x0f;
      return ~(sign | (exponent << 4) | mantissa) & 0xff;
    }

    function addTranscript(speaker, text) {
      const div = document.createElement('div');
      div.className = speaker === 'Caller' ? 'msg-user' : 'msg-ai';
      div.innerHTML = `<strong>${speaker}:</strong> ${text}`;
      transcriptBox.appendChild(div);
      transcriptBox.scrollTop = transcriptBox.scrollHeight;
    }

    async function startCall() {
      if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      if (audioCtx.state === 'suspended') await audioCtx.resume();

      statusText.innerText = "Dialing Anand Kumar...";
      streamSid = "web-call-" + Date.now();
      const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const wsUrl = `${wsProtocol}//${window.location.host}/ws/twilio/stream`;

      ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        isConnected = true;
        btnStart.style.display = 'none';
        btnEnd.style.display = 'flex';
        statusDot.className = 'status-dot active';
        
        if (currentMode === 'ptt') {
          btnPtt.style.display = 'flex';
          btnMute.style.display = 'none';
        } else {
          btnPtt.style.display = 'none';
          btnMute.style.display = 'flex';
        }

        ws.send(JSON.stringify({ event: "connected", protocol: "Call" }));
        ws.send(JSON.stringify({
          event: "start",
          sequenceNumber: "1",
          start: { streamSid: streamSid, accountSid: "AC_web", callSid: "CA_web_" + Date.now(), tracks: ["inbound"] },
          streamSid: streamSid
        }));

        callSeconds = 0;
        callTimer = setInterval(() => {
          callSeconds++;
          const mins = String(Math.floor(callSeconds / 60)).padStart(2, '0');
          const secs = String(callSeconds % 60).padStart(2, '0');
          if (!isAiSpeaking) {
            statusText.innerText = currentMode === 'ptt' 
              ? `Connected (${mins}:${secs}) • Hold button to speak` 
              : `Connected (${mins}:${secs}) • Listening...`;
          }
        }, 1000);

        startMicCapture();
      };

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          if (msg.event === "media" && msg.media && msg.media.payload) {
            playIncomingMulaw(msg.media.payload);
          } else if (msg.event === "transcript") {
            addTranscript(msg.role === 'user' ? 'Caller' : 'Anand', msg.text);
          } else if (msg.event === "ai_finished" || msg.event === "clear") {
            nextPlayTime = audioCtx.currentTime;
            avatarPulse.className = 'avatar-pulse';
            isAiSpeaking = false;
            btnInterrupt.style.display = 'none';
            statusText.innerText = currentMode === 'ptt' ? "Ready • Hold button to speak" : "Listening to you...";
          }
        } catch (e) {
          console.error("WS error:", e);
        }
      };

      ws.onclose = () => endCall();
      ws.onerror = (err) => {
        console.error("WS Error:", err);
        statusText.innerText = "Connection error";
        endCall();
      };
    }

    async function startMicCapture() {
      try {
        mediaStream = await navigator.mediaDevices.getUserMedia({ 
          audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true } 
        });
        const source = audioCtx.createMediaStreamSource(mediaStream);
        
        // Clean unity gain
        const micGain = audioCtx.createGain();
        micGain.gain.value = 1.0;

        scriptNode = audioCtx.createScriptProcessor(2048, 1, 1);
        const downsampleRatio = audioCtx.sampleRate / 8000;
        let mulawAccumulator = [];

        scriptNode.onaudioprocess = (e) => {
          if (!isConnected || !ws || ws.readyState !== WebSocket.OPEN) return;

          const input = e.inputBuffer.getChannelData(0);

          // Calculate RMS level for live VU meter
          let sumSquares = 0;
          for (let i = 0; i < input.length; i++) {
            sumSquares += input[i] * input[i];
          }
          let rms = Math.sqrt(sumSquares / input.length);
          let pct = Math.min(100, Math.round(rms * 400));
          
          if (!isMuted && (currentMode === 'hands-free' || isPttActive)) {
            vuLevel.style.width = pct + '%';
            vuValueLabel.innerText = pct + '%';
          } else {
            vuLevel.style.width = '0%';
            vuValueLabel.innerText = '0%';
          }

          // Echo prevention & muting gates:
          if (isMuted) return;
          if (currentMode === 'ptt' && !isPttActive) return; // Push-to-Talk gate
          if (currentMode === 'hands-free' && isAiSpeaking) return; // Echo suppression gate!

          for (let i = 0; i < input.length; i += downsampleRatio) {
            let sum = 0;
            let count = 0;
            let end = Math.min(input.length, Math.floor(i + downsampleRatio));
            for (let k = Math.floor(i); k < end; k++) {
              sum += input[k];
              count++;
            }
            let avg = count > 0 ? sum / count : 0;
            mulawAccumulator.push(floatToMulaw(avg));
            if (mulawAccumulator.length >= 160) {
              const chunk = new Uint8Array(mulawAccumulator.splice(0, 160));
              let binary = '';
              for (let j = 0; j < chunk.length; j++) binary += String.fromCharCode(chunk[j]);
              ws.send(JSON.stringify({
                event: "media",
                streamSid: streamSid,
                media: { payload: btoa(binary) }
              }));
            }
          }
        };

        source.connect(micGain);
        micGain.connect(scriptNode);

        // Prevent mic from echoing into local speakers
        const silentMute = audioCtx.createGain();
        silentMute.gain.value = 0;
        scriptNode.connect(silentMute);
        silentMute.connect(audioCtx.destination);
      } catch (err) {
        console.warn("Microphone access declined or unavailable:", err);
        statusText.innerText = "Mic offline (use preset speech buttons below)";
      }
    }

    function playIncomingMulaw(b64) {
      avatarPulse.className = 'avatar-pulse speaking';
      statusText.innerText = "Anand is speaking...";
      isAiSpeaking = true;
      btnInterrupt.style.display = 'inline-flex';

      const binary = atob(b64);
      const bytes = new Uint8Array(binary.length);
      for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
      const floatPcm = mulawToFloat(bytes);

      // Resample smoothly to native audioCtx.sampleRate with anti-aliasing
      const targetRate = audioCtx.sampleRate;
      const ratio = 8000 / targetRate;
      const outLength = Math.round(floatPcm.length / ratio);
      const nativePcm = new Float32Array(outLength);
      for (let i = 0; i < outLength; i++) {
        const srcIdx = i * ratio;
        const i0 = Math.floor(srcIdx);
        const i1 = Math.min(i0 + 1, floatPcm.length - 1);
        const frac = srcIdx - i0;
        nativePcm[i] = floatPcm[i0] * (1 - frac) + floatPcm[i1] * frac;
      }

      const buffer = audioCtx.createBuffer(1, nativePcm.length, targetRate);
      buffer.copyToChannel(nativePcm, 0);

      const src = audioCtx.createBufferSource();
      src.buffer = buffer;
      src.connect(audioCtx.destination);

      const now = audioCtx.currentTime;
      if (nextPlayTime < now) {
        nextPlayTime = now + 0.03;
      }
      src.start(nextPlayTime);
      nextPlayTime += buffer.duration;

      src.onended = () => {
        if (nextPlayTime <= audioCtx.currentTime + 0.12) {
          avatarPulse.className = 'avatar-pulse';
          isAiSpeaking = false;
          btnInterrupt.style.display = 'none';
          statusText.innerText = currentMode === 'ptt' ? "Ready • Hold button to speak" : "Listening to you...";
        }
      };
    }

    function sendManualInterrupt() {
      if (!isConnected || !ws) return;
      ws.send(JSON.stringify({ event: "interrupt", streamSid: streamSid }));
      nextPlayTime = audioCtx.currentTime;
      avatarPulse.className = 'avatar-pulse';
      isAiSpeaking = false;
      btnInterrupt.style.display = 'none';
      statusText.innerText = "Interrupted • Listening...";
    }

    /* Push-to-Talk Event Handlers */
    function startPtt() {
      if (!isConnected || isPttActive) return;
      isPttActive = true;
      btnPtt.classList.add('active');
      btnPtt.innerText = '🔴 LISTENING... RELEASE TO SEND';
      statusText.innerText = "Streaming your voice to Anand...";
    }

    function stopPtt() {
      if (!isPttActive) return;
      isPttActive = false;
      btnPtt.classList.remove('active');
      btnPtt.innerText = '🎙️ HOLD TO SPEAK';
      statusText.innerText = "Anand is thinking...";
      vuLevel.style.width = '0%';
      vuValueLabel.innerText = '0%';

      // Flush trailing silence frames so server VAD promptly triggers turn end
      if (isConnected && ws && ws.readyState === WebSocket.OPEN) {
        const silenceB64 = btoa(String.fromCharCode(...new Array(160).fill(0xff)));
        for (let i = 0; i < 28; i++) {
          ws.send(JSON.stringify({
            event: "media",
            streamSid: streamSid,
            media: { payload: silenceB64 }
          }));
        }
      }
    }

    btnPtt.addEventListener('mousedown', startPtt);
    window.addEventListener('mouseup', stopPtt);
    btnPtt.addEventListener('touchstart', (e) => { e.preventDefault(); startPtt(); });
    window.addEventListener('touchend', stopPtt);

    // Keyboard Spacebar for Push-to-Talk
    window.addEventListener('keydown', (e) => {
      if (e.code === 'Space' && currentMode === 'ptt' && isConnected && document.activeElement.tagName !== 'INPUT') {
        e.preventDefault();
        startPtt();
      }
    });
    window.addEventListener('keyup', (e) => {
      if (e.code === 'Space' && currentMode === 'ptt' && isConnected && document.activeElement.tagName !== 'INPUT') {
        e.preventDefault();
        stopPtt();
      }
    });

    async function simulateSpeech(text) {
      if (!isConnected) {
        await startCall();
        await new Promise(r => setTimeout(r, 600));
      }
      addTranscript('Caller', text);
      statusText.innerText = "Transmitting voice to Anand...";
      avatarPulse.className = 'avatar-pulse';

      try {
        const resp = await fetch('/api/voice/synthesize-mulaw', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text })
        });
        const data = await resp.json();
        if (!data.mulaw_b64) throw new Error(data.error || 'Failed');

        const rawMulaw = atob(data.mulaw_b64);
        const chunkSize = 160;
        for (let i = 0; i < rawMulaw.length; i += chunkSize) {
          const slice = rawMulaw.slice(i, i + chunkSize);
          ws.send(JSON.stringify({
            event: "media",
            streamSid: streamSid,
            media: { payload: btoa(slice) }
          }));
          await new Promise(r => setTimeout(r, 5));
        }

        // Send silence to trigger VAD
        const silenceB64 = btoa(String.fromCharCode(...new Array(160).fill(0xff)));
        for (let j = 0; j < 30; j++) {
          ws.send(JSON.stringify({
            event: "media",
            streamSid: streamSid,
            media: { payload: silenceB64 }
          }));
          await new Promise(r => setTimeout(r, 10));
        }
        statusText.innerText = "Anand Kumar is thinking...";
      } catch (err) {
        console.error(err);
        statusText.innerText = "Speech generation failed";
      }
    }

    function sendCustomSpeech() {
      const input = document.getElementById('customTextInput');
      const val = input.value.trim();
      if (val) {
        simulateSpeech(val);
        input.value = '';
      }
    }

    function endCall() {
      isConnected = false;
      clearInterval(callTimer);
      if (ws) {
        try { ws.send(JSON.stringify({ event: "stop", streamSid: streamSid })); ws.close(); } catch {}
        ws = null;
      }
      if (mediaStream) {
        mediaStream.getTracks().forEach(t => t.stop());
        mediaStream = null;
      }
      if (scriptNode) {
        try { scriptNode.disconnect(); } catch {}
        scriptNode = null;
      }
      btnStart.style.display = 'flex';
      btnEnd.style.display = 'none';
      btnPtt.style.display = 'none';
      btnMute.style.display = 'none';
      btnInterrupt.style.display = 'none';
      statusDot.className = 'status-dot';
      avatarPulse.className = 'avatar-pulse';
      vuLevel.style.width = '0%';
      vuValueLabel.innerText = '0%';
      statusText.innerText = "Call ended";
    }

    btnStart.onclick = startCall;
    btnEnd.onclick = endCall;
  </script>
</body>
</html>
"""
    return HTMLResponse(content=html_content)

