import json
import base64
import audioop
import wave
import io
import asyncio
import uuid
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from loguru import logger

from whatsapp_agent.voice.stt.faster_whisper import get_stt_provider
from whatsapp_agent.voice.tts.piper_tts import get_tts_provider
from whatsapp_agent.workflows.main_workflow import get_workflow

router = APIRouter()

# Energy threshold for Voice Activity Detection
VAD_ENERGY_THRESHOLD = 500
# How many consecutive silent frames (each ~20ms from Twilio) before we consider speech ended
SILENCE_FRAMES_THRESHOLD = 50  # approx 1 second of silence

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
    is_user_speaking = False
    
    # Interruption State
    ai_speaking = False
    current_response_task = None
    
    # Providers
    stt = get_stt_provider()
    tts = get_tts_provider()
    workflow = get_workflow()
    
    # Hardcode workspace for this demo phone agent
    # In production, we'd look this up based on the Twilio phone number
    workspace_id = "00000000-0000-0000-0000-000000000001" 
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
            
            # 3. Transcribe with Whisper
            logger.info("twilio_stt_started", stream_sid=sid)
            stt_result = await stt.transcribe_bytes(wav_bytes, audio_format="wav")
            user_text = stt_result.text.strip()
            
            if not user_text:
                logger.debug("twilio_stt_empty", stream_sid=sid)
                return
                
            logger.info("twilio_user_said", text=user_text, stream_sid=sid)
            
            # 3.5 Live Sentiment Analysis & Handoff
            from whatsapp_agent.config.settings import get_settings
            settings = get_settings()
            
            if settings.enable_live_sentiment_analysis:
                from whatsapp_agent.agents.llm_provider import get_llm_provider
                llm = get_llm_provider()
                sentiment_prompt = "Analyze the customer's sentiment. If they are angry, highly frustrated, or explicitly demanding a human/manager, reply with ONLY the word 'FRUSTRATED'. Otherwise, reply 'OK'."
                
                # Fast inference for sentiment
                sentiment_result, _ = await llm.complete(system_prompt=sentiment_prompt, user_message=user_text, temperature=0, max_tokens=10)
                
                if "FRUSTRATED" in sentiment_result.upper():
                    logger.warning("twilio_live_sentiment_escalation", stream_sid=sid, text=user_text)
                    
                    handoff_msg = "I understand this is frustrating. I am transferring your call to a human representative right now. Please hold the line."
                    handoff_audio = await tts.generate_twilio_audio(handoff_msg)
                    
                    # Clear any ongoing audio
                    await websocket.send_text(json.dumps({"event": "clear", "streamSid": sid}))
                    
                    # Play handoff message
                    for i in range(0, len(handoff_audio), 4000):
                        chunk = handoff_audio[i:i+4000]
                        payload_base64 = base64.b64encode(chunk).decode('utf-8')
                        await websocket.send_text(json.dumps({
                            "event": "media",
                            "streamSid": sid,
                            "media": {"payload": payload_base64}
                        }))
                        await asyncio.sleep(0.05)
                        
                    # Here we would normally use Twilio REST API to modify the live call
                    # and bridge it to a human SIP/PSTN number. For now, we halt AI processing.
                    return
            
            # 4. Run LangGraph Agent
            state = {
                "workspace_id": workspace_id,
                "message_id": str(uuid.uuid4()),
                "contact_wa_id": contact_id,
                "raw_text": user_text,
                "transcription": "",
                "input_modality": "voice",
                "conversation_history": [] # For full implementation, fetch from DB
            }
            
            logger.info("twilio_agent_running", stream_sid=sid)
            result_state = await workflow.ainvoke(state)
            
            ai_text = result_state.get("final_response", "I'm sorry, I encountered an error.")
            logger.info("twilio_ai_replied", text=ai_text, stream_sid=sid)
            
            # 5. Generate TTS via Piper
            ai_speaking = True
            logger.info("twilio_tts_started", stream_sid=sid)
            ai_mulaw_bytes = await tts.generate_twilio_audio(ai_text)
            
            # 6. Stream back to Twilio
            # Twilio recommends sending media in small chunks, but we can send it as one payload
            # if it's small, or chunk it. For simplicity, we chunk it into 20ms chunks (160 bytes for 8kHz mulaw)
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
                # Sleep briefly to simulate streaming and allow interruption checks
                await asyncio.sleep(0.1)

        except asyncio.CancelledError:
            logger.info("twilio_process_cancelled_by_interruption", stream_sid=sid)
        except Exception as e:
            logger.error("twilio_process_failed", error=str(e), stream_sid=sid)
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
                
            elif event == "media":
                if not stream_sid:
                    continue
                    
                payload = message["media"]["payload"]
                audio_chunk = base64.b64decode(payload)
                
                # VAD using audioop RMS (Root Mean Square energy)
                linear_chunk = audioop.ulaw2lin(audio_chunk, 2)
                energy = audioop.rms(linear_chunk, 2)
                
                if energy > VAD_ENERGY_THRESHOLD:
                    # User is actively speaking
                    silence_frames = 0
                    if not is_user_speaking:
                        is_user_speaking = True
                        logger.debug("twilio_vad_speech_started")
                        
                        # INTERRUPTIBILITY: If AI is speaking, interrupt it!
                        if ai_speaking:
                            logger.info("twilio_interrupting_ai", stream_sid=stream_sid)
                            ai_speaking = False
                            if current_response_task and not current_response_task.done():
                                current_response_task.cancel()
                            # Send clear event to Twilio to halt playback
                            await websocket.send_text(json.dumps({
                                "event": "clear",
                                "streamSid": stream_sid
                            }))
                            
                    audio_buffer.extend(audio_chunk)
                else:
                    # Silence detected
                    if is_user_speaking:
                        silence_frames += 1
                        audio_buffer.extend(audio_chunk)
                        
                        # If silence has been long enough, user stopped speaking
                        if silence_frames > SILENCE_FRAMES_THRESHOLD:
                            is_user_speaking = False
                            logger.debug("twilio_vad_speech_ended")
                            
                            # Grab the accumulated buffer and clear it
                            speech_bytes = bytes(audio_buffer)
                            audio_buffer.clear()
                            
                            # Only process if we have enough audio (avoid blips)
                            if len(speech_bytes) > 8000: # at least 1 second of audio
                                current_response_task = asyncio.create_task(
                                    process_speech_and_respond(speech_bytes, stream_sid)
                                )
                                
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
