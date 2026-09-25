"""
ARQ async worker entry point.

ARQ (Async Redis Queue) is used for background task processing:
- Webhook event processing (async after HTTP 200 return)
- Media download and processing (STT, OCR, vision)
- Agent runs (LLM calls, RAG retrieval)
- CRM sync operations
- Knowledge source ingestion

Workers are stateless and idempotent. Any job can be retried safely.
"""

from __future__ import annotations

import signal
import sys
from pathlib import Path

# Ensure src/ is on the Python path when running directly
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from arq import Worker, cron
from arq.connections import RedisSettings

from whatsapp_agent.config.settings import get_settings
from whatsapp_agent.observability.logging import configure_logging, get_logger
from whatsapp_agent.voice.stt.faster_whisper import get_stt_provider
from whatsapp_agent.documents.ocr import get_ocr_provider
from whatsapp_agent.vision.moondream import get_vision_provider
from whatsapp_agent.whatsapp.providers.factory import get_whatsapp_provider
from whatsapp_agent.database.models.whatsapp import (
    WhatsAppMessage, WhatsAppContact, WhatsAppConversation, WhatsAppAccount,
    MessageDirection, MessageType, MessageStatus, Modality, ConversationStatus
)
from whatsapp_agent.database.models.agents import AgentRun, AgentRunStatus
from sqlalchemy import select
from whatsapp_agent.database.session import _get_session_factory
import uuid
import time

settings = get_settings()
logger = get_logger(__name__)


# ── Task Definitions ───────────────────────────────────────────────────────────
# Each task is an async function. ARQ serializes arguments via pickle.
# Keep task arguments simple (IDs, not objects) for reliability.


async def process_whatsapp_webhook(ctx: dict, message_dict: dict, phone_number_id: str | None) -> None:
    """
    Process a received WhatsApp webhook event asynchronously.
    """
    logger.info("processing_whatsapp_webhook", wamid=message_dict.get("id"))
    from datetime import datetime, timezone
    factory = _get_session_factory()
    
    async with factory() as db:
        # 1. Ensure we have an account for this phone_number_id
        if phone_number_id:
            acc_stmt = select(WhatsAppAccount).where(WhatsAppAccount.phone_number_id == phone_number_id)
            account = (await db.execute(acc_stmt)).scalar_one_or_none()
        else:
            account = (await db.execute(select(WhatsAppAccount).limit(1))).scalar_one_or_none()
            
        if not account:
            # Create a mock account and workspace for testing if missing
            from whatsapp_agent.database.models.workspaces import Workspace
            workspace = (await db.execute(select(Workspace).limit(1))).scalar_one_or_none()
            if not workspace:
                workspace = Workspace(name="Default Workspace", slug="default")
                db.add(workspace)
                await db.commit()
            account = WhatsAppAccount(
                workspace_id=workspace.id, phone_number="1234567890", phone_number_id=phone_number_id or "mock"
            )
            db.add(account)
            await db.commit()
            
        # 2. Find or create Contact
        wa_id = message_dict.get("from_")
        contact_stmt = select(WhatsAppContact).where(WhatsAppContact.wa_id == wa_id, WhatsAppContact.workspace_id == account.workspace_id)
        contact = (await db.execute(contact_stmt)).scalar_one_or_none()
        if not contact:
            contact = WhatsAppContact(
                workspace_id=account.workspace_id, wa_id=wa_id, phone_number=wa_id, profile_name="Customer"
            )
            db.add(contact)
            await db.commit()
            
        # 3. Find or create Conversation
        conv_stmt = select(WhatsAppConversation).where(
            WhatsAppConversation.account_id == account.id,
            WhatsAppConversation.contact_id == contact.id
        )
        conversation = (await db.execute(conv_stmt)).scalar_one_or_none()
        if not conversation:
            conversation = WhatsAppConversation(
                workspace_id=account.workspace_id, account_id=account.id, contact_id=contact.id
            )
            db.add(conversation)
            
        # 4. Insert Message
        wamid = message_dict.get("id")
        existing_msg = (await db.execute(select(WhatsAppMessage).where(WhatsAppMessage.wamid == wamid))).scalar_one_or_none()
        if existing_msg:
            return  # Idempotent
            
        msg_type_str = message_dict.get("type", "text").upper()
        msg_type = getattr(MessageType, msg_type_str, MessageType.UNKNOWN)
        modality = Modality.TEXT
        
        # Determine modality
        media_id = None
        is_voice = False
        body = ""
        
        if msg_type == MessageType.AUDIO:
            modality = Modality.VOICE
            media_id = message_dict.get("audio", {}).get("id")
            is_voice = message_dict.get("audio", {}).get("voice", False)
        elif msg_type == MessageType.IMAGE:
            modality = Modality.IMAGE
            media_id = message_dict.get("image", {}).get("id")
        elif msg_type == MessageType.DOCUMENT:
            modality = Modality.DOCUMENT
            media_id = message_dict.get("document", {}).get("id")
        else:
            body = message_dict.get("text", {}).get("body", "")
            
        msg = WhatsAppMessage(
            workspace_id=account.workspace_id,
            conversation_id=conversation.id,
            account_id=account.id,
            contact_id=contact.id,
            wamid=wamid,
            direction=MessageDirection.INBOUND,
            message_type=msg_type,
            modality=modality,
            body=body,
            media_id=media_id,
            is_voice_note=is_voice,
            status=MessageStatus.RECEIVED,
            timestamp=datetime.fromtimestamp(int(message_dict.get("timestamp", time.time())), tz=timezone.utc)
        )
        db.add(msg)
        
        conversation.message_count += 1
        conversation.last_message_at = msg.timestamp
        await db.commit()
        
        logger.info("webhook_message_persisted", message_id=str(msg.id))
        
        if conversation.status == ConversationStatus.ESCALATED or not conversation.ai_enabled:
            logger.info("ai_paused_skipping_agent_run", conversation_id=str(conversation.id))
            return
            
        # 5. Enqueue processing
        redis = ctx.get("redis")
        if not redis:
            return
            
        if modality == Modality.TEXT:
            # Enqueue agent directly
            agent_run = AgentRun(
                id=uuid.uuid4(),
                workspace_id=account.workspace_id,
                message_id=msg.id,
                status=AgentRunStatus.PENDING,
            )
            db.add(agent_run)
            await db.commit()
            await redis.enqueue_job("run_agent", str(agent_run.id))
        elif modality == Modality.VOICE:
            await redis.enqueue_job("process_voice_message", str(msg.id))
        elif modality == Modality.IMAGE:
            await redis.enqueue_job("process_image_message", str(msg.id))
        elif modality == Modality.DOCUMENT:
            await redis.enqueue_job("process_document_message", str(msg.id))


async def process_voice_message(ctx: dict, message_id: str) -> None:
    """
    Download and transcribe a WhatsApp voice message.

    Pipeline:
    1. Retrieve media URL from WhatsApp API
    2. Download OGG/Opus audio file
    3. Validate audio (format, duration, size)
    4. Transcribe with faster-whisper (local, free)
    5. Detect language
    6. Update message record with transcription
    7. Enqueue agent_run task

    Args:
        ctx: ARQ worker context.
        message_id: UUID of the WhatsAppMessage to process.
    """
    logger.info("processing_voice_message_started", message_id=message_id)
    
    try:
        msg_uuid = uuid.UUID(message_id)
    except ValueError:
        logger.error("invalid_message_id", message_id=message_id)
        return

    factory = _get_session_factory()
    provider = get_whatsapp_provider()
    stt = get_stt_provider()

    async with factory() as db:
        # 1. Fetch message from DB
        stmt = select(WhatsAppMessage).where(WhatsAppMessage.id == msg_uuid)
        result = await db.execute(stmt)
        msg = result.scalar_one_or_none()

        if not msg:
            logger.error("voice_message_not_found_in_db", message_id=message_id)
            return
            
        if not msg.media_id:
            logger.error("voice_message_missing_media_id", message_id=message_id)
            return

        workspace_id = str(msg.workspace_id)

        try:
            # 2. Download media
            audio_bytes = await provider.download_media(msg.media_id)
            
            # 3. Transcribe
            stt_result = await stt.transcribe_bytes(audio_bytes, audio_format="ogg")
            
            # Bounds checking for transcription to prevent token explosion
            transcript = stt_result.text
            if len(transcript) > 3000:
                transcript = transcript[:3000] + "... [TRUNCATED]"
            
            # 4. Update message
            msg.transcription = transcript
            msg.language_detected = stt_result.language
            await db.commit()
            
            logger.info(
                "voice_message_transcribed", 
                message_id=message_id, 
                text_len=len(stt_result.text),
                latency_ms=stt_result.latency_ms
            )

            # 5. Enqueue Agent Run Task
            # Create the AgentRun record
            agent_run_id = uuid.uuid4()
            agent_run = AgentRun(
                id=agent_run_id,
                workspace_id=msg.workspace_id,
                message_id=msg.id,
                status=AgentRunStatus.PENDING,
            )
            db.add(agent_run)
            await db.commit()

            # Enqueue the background agent execution
            await ctx["redis"].enqueue_job("run_agent", str(agent_run_id))
            logger.info(
                "agent_run_enqueued_for_voice",
                agent_run_id=str(agent_run_id),
                message_id=message_id,
            )

        except Exception as e:
            logger.error("voice_processing_failed", message_id=message_id, error=str(e), exc_info=e)
            # We could optionally update message status to FAILED here


async def process_image_message(ctx: dict, message_id: str) -> None:
    """
    Download and analyze a WhatsApp image message.

    Pipeline:
    1. Download image from WhatsApp API
    2. Validate image (MIME, size, dimensions)
    3. Run PaddleOCR for text extraction
    4. Run moondream2 for image understanding
    5. Update message record with analysis
    6. Enqueue agent_run task

    Args:
        ctx: ARQ worker context.
        message_id: UUID of the WhatsAppMessage to process.
    """
    logger.info("processing_image_message_started", message_id=message_id)

    try:
        msg_uuid = uuid.UUID(message_id)
    except ValueError:
        logger.error("invalid_message_id", message_id=message_id)
        return

    factory = _get_session_factory()
    provider = get_whatsapp_provider()
    ocr = get_ocr_provider()
    vlm = get_vision_provider()

    async with factory() as db:
        stmt = select(WhatsAppMessage).where(WhatsAppMessage.id == msg_uuid)
        result = await db.execute(stmt)
        msg = result.scalar_one_or_none()

        if not msg or not msg.media_id:
            logger.error("image_message_invalid_or_missing_media", message_id=message_id)
            return

        try:
            # 1. Download image
            image_bytes = await provider.download_media(msg.media_id)

            # 2. Extract Text via OCR
            try:
                ocr_text = await ocr.extract_text(image_bytes)
                # Bounds checking for OCR to prevent token explosion
                if len(ocr_text) > 2000:
                    ocr_text = ocr_text[:2000] + "... [TRUNCATED]"
            except Exception as e:
                logger.warning("ocr_failed", error=str(e))
                ocr_text = ""

            # 3. Describe Image via VLM
            try:
                vlm_desc = await vlm.describe_image(image_bytes, "Describe this image in detail.")
                # Bounds checking for VLM
                if len(vlm_desc) > 1000:
                    vlm_desc = vlm_desc[:1000] + "... [TRUNCATED]"
            except Exception as e:
                logger.warning("vlm_failed", error=str(e))
                vlm_desc = "Image analysis failed."

            # 4. Combine and Save
            analysis = []
            if vlm_desc:
                analysis.append(f"<IMAGE_DESCRIPTION>\n{vlm_desc}\n</IMAGE_DESCRIPTION>")
            if ocr_text:
                analysis.append(f"<OCR_TEXT>\n{ocr_text}\n</OCR_TEXT>")

            msg.image_analysis = "\n\n".join(analysis)
            await db.commit()

            logger.info("image_message_processed", message_id=message_id, has_ocr=bool(ocr_text))

            # 5. Enqueue Agent Run Task
            agent_run_id = uuid.uuid4()
            agent_run = AgentRun(
                id=agent_run_id,
                workspace_id=msg.workspace_id,
                message_id=msg.id,
                status=AgentRunStatus.PENDING,
            )
            db.add(agent_run)
            await db.commit()

            await ctx["redis"].enqueue_job("run_agent", str(agent_run_id))

        except Exception as e:
            logger.error("image_processing_failed", message_id=message_id, error=str(e), exc_info=e)


async def process_document_message(ctx: dict, message_id: str) -> None:
    """
    Download and extract content from a WhatsApp document.

    Args:
        ctx: ARQ worker context.
        message_id: UUID of the WhatsAppMessage to process.
    """
    logger.info("processing_document_message", message_id=message_id)
    
    from whatsapp_agent.database.session import _get_session_factory
    from whatsapp_agent.database.models.whatsapp import WhatsAppMessage
    from whatsapp_agent.database.models.agents import AgentRun, AgentRunStatus
    from sqlalchemy import select
    import uuid

    factory = _get_session_factory()
    provider = get_whatsapp_provider()
    msg_uuid = uuid.UUID(message_id)

    async with factory() as db:
        stmt = select(WhatsAppMessage).where(WhatsAppMessage.id == msg_uuid)
        result = await db.execute(stmt)
        msg = result.scalar_one_or_none()

        if not msg or not msg.media_id:
            logger.error("document_message_invalid_or_missing_media", message_id=message_id)
            return

        try:
            # 1. Download document
            document_bytes = await provider.download_media(msg.media_id)

            # 2. Extract Text
            from whatsapp_agent.documents.parser import extract_pdf_text
            extracted_text = await extract_pdf_text(document_bytes)
            
            # Bounds checking for text to prevent token explosion
            if len(extracted_text) > 3000:
                extracted_text = extracted_text[:3000] + "... [TRUNCATED]"
                
            msg.body = extracted_text if extracted_text else "[Empty Document]"
            await db.commit()

            logger.info("document_message_processed", message_id=message_id, text_length=len(extracted_text))

            # 3. Enqueue Agent Run Task
            agent_run_id = uuid.uuid4()
            agent_run = AgentRun(
                id=agent_run_id,
                workspace_id=msg.workspace_id,
                message_id=msg.id,
                status=AgentRunStatus.PENDING,
            )
            db.add(agent_run)
            await db.commit()

            await ctx["redis"].enqueue_job("run_agent", str(agent_run_id))

        except Exception as e:
            logger.error("document_processing_failed", message_id=message_id, error=str(e), exc_info=e)


async def run_agent(ctx: dict, agent_run_id: str) -> None:
    """
    Execute a supervisor agent run for a processed message.

    Args:
        ctx: ARQ worker context.
        agent_run_id: UUID of the AgentRun to execute.
    """
    logger.info("running_agent", agent_run_id=agent_run_id)
    
    from whatsapp_agent.database.session import _get_session_factory
    from whatsapp_agent.database.models.agents import AgentRun, AgentRunStatus
    from whatsapp_agent.database.models.whatsapp import WhatsAppMessage, WhatsAppContact, MessageDirection
    from whatsapp_agent.workflows.main_workflow import get_workflow
    from whatsapp_agent.core.governance import InputSizeGuard, ContextManager
    from sqlalchemy import select
    import uuid
    import time
    from datetime import datetime, timezone

    factory = _get_session_factory()
    run_uuid = uuid.UUID(agent_run_id)
    
    async with factory() as db:
        # Fetch the AgentRun
        result = await db.execute(select(AgentRun).where(AgentRun.id == run_uuid))
        agent_run = result.scalar_one_or_none()
        if not agent_run:
            logger.error("agent_run_not_found", agent_run_id=agent_run_id)
            return

        # Fetch the message
        msg_result = await db.execute(
            select(WhatsAppMessage).where(WhatsAppMessage.id == agent_run.message_id)
        )
        message = msg_result.scalar_one_or_none()
        
        if not message:
            logger.error("agent_run_message_not_found", message_id=str(agent_run.message_id))
            return

        # Fetch the contact to get wa_id
        contact_result = await db.execute(
            select(WhatsAppContact).where(WhatsAppContact.id == message.contact_id)
        )
        contact = contact_result.scalar_one_or_none()
        contact_wa_id = contact.wa_id if contact else ""

        raw_text = message.body or ""
        transcription = message.transcription or ""
        text_to_process = raw_text if raw_text else transcription
        
        # 1. Input Guard
        guard_result = InputSizeGuard.evaluate(text_to_process)
        if not guard_result.is_valid:
            logger.warning("message_rejected_by_input_guard", message_id=str(message.id), reason=guard_result.rejection_reason)
            # Update status to FAILED and return
            agent_run.status = AgentRunStatus.FAILED
            agent_run.error_message = guard_result.rejection_reason
            agent_run.completed_at = datetime.now(timezone.utc)
            await db.commit()
            # Note: We should ideally send a WhatsApp reply here, but for now we just fail the run.
            # A future phase would send `guard_result.rejection_reason` to the user via WhatsApp API.
            return
            
        processed_text = guard_result.text

        # 2. Context History Fetch
        # Get the last 20 messages for this conversation (before the current one)
        history_result = await db.execute(
            select(WhatsAppMessage)
            .where(
                WhatsAppMessage.conversation_id == message.conversation_id,
                WhatsAppMessage.timestamp < message.timestamp
            )
            .order_by(WhatsAppMessage.timestamp.desc())
            .limit(20)
        )
        recent_messages = history_result.scalars().all()
        
        # Convert to dict format
        history_dicts = []
        # recent_messages is desc (newest first).
        for m in recent_messages:
            role = "user" if m.direction == MessageDirection.INBOUND else "assistant"
            content = m.body or m.transcription or ""
            if content:
                history_dicts.append({"role": role, "content": content})
                
        # Filter with ContextManager
        history_dicts = ContextManager.filter_history(history_dicts)

        # Update status to RUNNING
        agent_run.status = AgentRunStatus.RUNNING
        agent_run.started_at = datetime.now(timezone.utc)
        await db.commit()
        
        # Build LangGraph state
        state = {
            "workspace_id": str(agent_run.workspace_id),
            "message_id": str(message.id),
            "contact_wa_id": contact_wa_id,
            "raw_text": processed_text,
            "transcription": transcription if guard_result.is_valid and guard_result.was_truncated == False else "",
            "input_modality": message.modality.value.lower() if message.modality else "text",
            "conversation_history": history_dicts
        }

    start_time = time.monotonic()
    
    try:
        workflow = get_workflow()
        result_state = await workflow.ainvoke(state)
        
        # Open a new session to update result
        async with factory() as db:
            result = await db.execute(select(AgentRun).where(AgentRun.id == run_uuid))
            agent_run = result.scalar_one_or_none()
            if agent_run:
                agent_run.status = AgentRunStatus.COMPLETED
                agent_run.completed_at = datetime.now(timezone.utc)
                agent_run.intent_detected = result_state.get("intent")
                if result_state.get("confidence_score") is not None:
                    agent_run.confidence_score = float(result_state.get("confidence_score"))
                agent_run.escalation_required = result_state.get("escalation_required", False)
                agent_run.escalation_reason = result_state.get("escalation_reason")
                agent_run.prompt_tokens = result_state.get("prompt_tokens")
                agent_run.completion_tokens = result_state.get("completion_tokens")
                agent_run.model_latency_ms = result_state.get("model_latency_ms")
                agent_run.total_latency_ms = round((time.monotonic() - start_time) * 1000)
                await db.commit()
                logger.info("agent_run_completed", agent_run_id=agent_run_id, intent=agent_run.intent_detected)
                
    except Exception as e:
        logger.exception("agent_run_failed", agent_run_id=agent_run_id, error=str(e))
        async with factory() as db:
            result = await db.execute(select(AgentRun).where(AgentRun.id == run_uuid))
            agent_run = result.scalar_one_or_none()
            if agent_run:
                agent_run.status = AgentRunStatus.FAILED
                agent_run.completed_at = datetime.now(timezone.utc)
                agent_run.error_message = str(e)
                agent_run.total_latency_ms = round((time.monotonic() - start_time) * 1000)
                await db.commit()


async def ingest_knowledge_source(ctx: dict, source_id: str) -> None:
    """
    Ingest a knowledge source into the vector store.
    """
    logger.info("ingesting_knowledge_source", source_id=source_id)
    
    from whatsapp_agent.database.session import _get_session_factory
    from whatsapp_agent.database.models.knowledge import KnowledgeSource, KnowledgeSourceStatus, KnowledgeSourceType, DocumentChunk
    from whatsapp_agent.rag.chunking.text_splitter import RecursiveTextSplitter
    from whatsapp_agent.rag.embedding.sentence_transformers import SentenceTransformerEmbedding
    from sqlalchemy import select
    import uuid
    import hashlib
    from datetime import datetime, timezone

    factory = _get_session_factory()
    src_uuid = uuid.UUID(source_id)

    async with factory() as db:
        # 1. Load KnowledgeSource
        stmt = select(KnowledgeSource).where(KnowledgeSource.id == src_uuid)
        result = await db.execute(stmt)
        source = result.scalar_one_or_none()
        
        if not source:
            logger.error("knowledge_source_not_found", source_id=source_id)
            return

        source.status = KnowledgeSourceStatus.PROCESSING
        await db.commit()

        try:
            # 2. Extract text content
            text_content = ""
            if source.source_type == KnowledgeSourceType.TEXT:
                text_content = source.source_uri or ""
            elif source.source_type == KnowledgeSourceType.WEBSITE:
                import httpx
                # Very basic URL fetching, real prod would use a robust scraper
                async with httpx.AsyncClient() as client:
                    resp = await client.get(source.source_uri or "")
                    resp.raise_for_status()
                    text_content = resp.text
            else:
                text_content = f"Simulated content for {source.source_type.value}: {source.title}"
            
            # 3. Chunk content
            splitter = RecursiveTextSplitter(chunk_size=512, chunk_overlap=64)
            chunks = splitter.split_text(text_content, metadata={"source": source.title})

            # 4. Generate embeddings and store
            embedder = SentenceTransformerEmbedding()
            
            for chunk_data in chunks:
                vector = await embedder.embed_text(chunk_data.content)
                content_hash = hashlib.sha256(chunk_data.content.encode('utf-8')).hexdigest()
                
                doc_chunk = DocumentChunk(
                    workspace_id=source.workspace_id,
                    source_id=source.id,
                    chunk_index=chunk_data.chunk_index,
                    content=chunk_data.content,
                    content_hash=content_hash,
                    metadata_json=chunk_data.metadata,
                    embedding=vector
                )
                db.add(doc_chunk)

            # 5. Update source status
            source.status = KnowledgeSourceStatus.ACTIVE
            source.document_count = 1
            source.chunk_count = len(chunks)
            source.processed_at = datetime.now(timezone.utc)
            source.content_hash = hashlib.sha256(text_content.encode('utf-8')).hexdigest()
            
            await db.commit()
            logger.info("knowledge_source_ingested", source_id=source_id, chunk_count=len(chunks))

        except Exception as e:
            logger.exception("knowledge_ingestion_failed", source_id=source_id, error=str(e))
            source.status = KnowledgeSourceStatus.FAILED
            source.processing_error = str(e)
            await db.commit()


async def sync_lead_to_crm(ctx: dict, lead_id: str) -> None:
    """
    Sync a qualified lead to the configured CRM provider.
    """
    logger.info("syncing_lead_to_crm", lead_id=lead_id)
    
    from whatsapp_agent.database.session import _get_session_factory
    from whatsapp_agent.database.models.leads import Lead
    from whatsapp_agent.integrations.crm.factory import get_crm_provider
    from sqlalchemy import select
    import uuid
    from datetime import datetime, timezone

    factory = _get_session_factory()
    lead_uuid = uuid.UUID(lead_id)
    crm = get_crm_provider()

    async with factory() as db:
        stmt = select(Lead).where(Lead.id == lead_uuid)
        result = await db.execute(stmt)
        lead = result.scalar_one_or_none()
        
        if not lead:
            logger.error("lead_not_found_for_sync", lead_id=lead_id)
            return

        try:
            # Create lead in CRM (we assume the customer's phone is the unique identifier for now)
            # In a real app we'd fetch the contact phone, but the Lead model might not store phone directly.
            # Wait, our Lead model does have phone, name, email.
            phone = lead.phone or "UnknownPhone"
            crm_id = await crm.create_lead(
                phone=phone,
                name=lead.name,
                email=lead.email
            )
            
            if crm_id:
                lead.crm_contact_id = crm_id
                lead.crm_synced_at = datetime.now(timezone.utc)
                await db.commit()
                logger.info("lead_synced_to_crm", lead_id=lead_id, crm_id=crm_id)
            else:
                logger.warning("lead_sync_failed_no_id", lead_id=lead_id)
                
        except Exception as e:
            logger.exception("lead_sync_failed", lead_id=lead_id, error=str(e))


# ── Startup/Shutdown Hooks ─────────────────────────────────────────────────────

async def startup(ctx: dict) -> None:
    """
    Worker startup: initialize DB connection and shared resources.
    Called once when the worker process starts.
    """
    configure_logging(
        log_level=settings.log_level,
        log_format=settings.log_format,
    )
    logger.info(
        "arq_worker_starting",
        redis_url=str(settings.redis_url).replace(
            str(settings.redis_url).split("@")[0].split("//")[1], "***"
        ) if "@" in str(settings.redis_url) else str(settings.redis_url),
    )

    from whatsapp_agent.database.engine import init_db
    await init_db()
    logger.info("arq_worker_db_initialized")
    
    from whatsapp_agent.tools.mcp_client import mcp_manager
    import sys
    import os
    # Connect MCP servers
    try:
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        # Make sure src is in python path
        env = os.environ.copy()
        env["PYTHONPATH"] = f"{project_root}/src;{env.get('PYTHONPATH', '')}"

        await mcp_manager.connect_and_register(
            server_name="CRM_Server",
            command=sys.executable,
            args=["-m", "whatsapp_agent.mcp_servers.crm_server"],
            env=env
        )
        await mcp_manager.connect_and_register(
            server_name="Calendar_Server",
            command=sys.executable,
            args=["-m", "whatsapp_agent.mcp_servers.calendar_server"],
            env=env
        )
    except Exception as e:
        logger.error("failed_to_init_mcp_servers", error=str(e))


async def shutdown(ctx: dict) -> None:
    """
    Worker shutdown: close DB connections and clean up resources.
    Called once when the worker process stops.
    """
    logger.info("arq_worker_shutting_down")
    
    from whatsapp_agent.tools.mcp_client import mcp_manager
    for stack in mcp_manager._exit_stacks:
        try:
            await stack.aclose()
        except Exception:
            pass
            
    from whatsapp_agent.database.engine import close_db
    await close_db()
    logger.info("arq_worker_stopped")


# ── Worker Configuration ───────────────────────────────────────────────────────

class WorkerSettings:
    """
    ARQ worker configuration class.

    ARQ discovers this class by convention.
    Run with: python -m arq apps.worker.main.WorkerSettings
    """

    # All registered task functions
    functions = [
        process_whatsapp_webhook,
        process_voice_message,
        process_image_message,
        process_document_message,
        run_agent,
        ingest_knowledge_source,
        sync_lead_to_crm,
    ]

    # Redis connection settings (ARQ uses its own connection pool)
    redis_settings = RedisSettings.from_dsn(str(settings.redis_url))

    # Worker capacity
    max_jobs = settings.worker_max_jobs
    job_timeout = settings.worker_job_timeout
    keep_result = 3600  # Keep job results in Redis for 1 hour
    poll_delay = 0.5  # Seconds between queue polls

    # Lifecycle hooks
    on_startup = startup
    on_shutdown = shutdown

    # Health check
    health_check_interval = settings.worker_health_check_interval
    health_check_key = "arq:health-check"


if __name__ == "__main__":
    """Allow running the worker directly: python -m apps.worker.main"""
    import asyncio
    from arq import run_worker

    asyncio.run(run_worker(WorkerSettings))
