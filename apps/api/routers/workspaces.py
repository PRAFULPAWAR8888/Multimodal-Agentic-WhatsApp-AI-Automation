import uuid
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from whatsapp_agent.database.session import get_db_session
from whatsapp_agent.database.models.workspaces import Workspace, BusinessProfile
from whatsapp_agent.database.models.users import User
from whatsapp_agent.security.dependencies import get_current_user

router = APIRouter(prefix="/workspaces", tags=["workspaces"])

class BusinessProfileUpdate(BaseModel):
    business_name: Optional[str] = None
    business_description: Optional[str] = None
    ai_persona_name: Optional[str] = None
    ai_persona_role: Optional[str] = None
    ai_persona_tone: Optional[str] = None
    ai_response_language: Optional[str] = None
    ai_max_response_length: Optional[int] = None
    ai_use_emoji: Optional[bool] = None
    ai_custom_instructions: Optional[str] = None
    ai_restrictions: Optional[str] = None
    escalation_keywords_json: Optional[List[str]] = None

class PlaygroundChatRequest(BaseModel):
    message: Optional[str] = ""
    sender_id: Optional[str] = "playground_user"
    modality: Optional[str] = "text"
    file_name: Optional[str] = None
    file_type: Optional[str] = None
    file_data: Optional[str] = None


async def _process_playground_multimodal(
    modality: str,
    raw_message: str,
    file_data: Optional[str],
    file_name: Optional[str],
    file_type: Optional[str]
) -> Dict[str, Any]:
    """
    Process incoming playground media:
    - Base64 image -> vision analysis via OpenAI / Qwen
    - Base64 PDF/doc -> document text extraction
    - Voice -> transcription
    """
    image_analysis = ""
    document_text = ""
    transcription = ""
    effective_modality = modality or "text"

    if file_data and (effective_modality == "image" or (file_type and file_type.startswith("image/"))):
        effective_modality = "image"
        try:
            import base64
            from openai import AsyncOpenAI
            from whatsapp_agent.config.settings import get_settings

            b64 = file_data.split(",", 1)[1] if "," in file_data else file_data
            img_bytes = base64.b64decode(b64)
            b64_str = base64.b64encode(img_bytes).decode("utf-8")
            mime = file_type or "image/jpeg"

            settings = get_settings()
            prompt = raw_message.strip() if raw_message.strip() else "Please describe this image in detail, extract any visible text, and identify key objects, charts, or details."

            client = AsyncOpenAI(api_key=settings.openai_api_key)
            resp = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64_str}"}}
                        ]
                    }
                ],
                max_tokens=600
            )
            image_analysis = resp.choices[0].message.content or "Image analyzed successfully."
        except Exception as e:
            image_analysis = f"Image attached ({file_name or 'image'}). Analysis note: {e}"

    elif file_data and (effective_modality == "document" or (file_type and any(k in file_type for k in ["pdf", "word", "document", "text"])) or (file_name and any(file_name.lower().endswith(ext) for ext in [".pdf", ".docx", ".doc", ".txt", ".md"]))):
        effective_modality = "document"
        try:
            import base64
            from whatsapp_agent.documents.parser import extract_document_text
            b64 = file_data.split(",", 1)[1] if "," in file_data else file_data
            doc_bytes = base64.b64decode(b64)
            document_text = await extract_document_text(doc_bytes, filename=file_name, mime_type=file_type)
            if not document_text.strip():
                document_text = f"Document attached: {file_name or 'document'}."
            image_analysis = f"Document text extracted from {file_name or 'document'}:\n{document_text[:4000]}"
        except Exception as e:
            document_text = f"Error extracting document text: {e}"
            image_analysis = document_text

    elif effective_modality == "voice":
        transcription = raw_message or "Voice note received"
        if file_data and (not raw_message or raw_message == "Voice message"):
            try:
                import base64
                import tempfile
                import os
                from openai import AsyncOpenAI
                from whatsapp_agent.config.settings import get_settings

                b64 = file_data.split(",", 1)[1] if "," in file_data else file_data
                audio_bytes = base64.b64decode(b64)

                with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as tmp:
                    tmp.write(audio_bytes)
                    tmp_path = tmp.name

                settings = get_settings()
                client = AsyncOpenAI(api_key=settings.openai_api_key)
                with open(tmp_path, "rb") as audio_file:
                    tr_resp = await client.audio.transcriptions.create(
                        model="whisper-1",
                        file=audio_file
                    )
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass

                if tr_resp.text:
                    transcription = tr_resp.text
            except Exception:
                pass

    return {
        "modality": effective_modality,
        "image_analysis": image_analysis,
        "document_text": document_text,
        "transcription": transcription
    }


async def _resolve_workspace(workspace_id_str: str, db: AsyncSession, current_user: Optional[User] = None) -> Workspace:
    """
    Resolve workspace by UUID, slug, name, or fall back to user's workspace or default workspace.
    Guarantees that a valid Workspace object is returned, never failing with 422 for arbitrary string IDs.
    """
    # 1. Try parsing as UUID
    try:
        ws_uuid = uuid.UUID(workspace_id_str)
        stmt = (
            select(Workspace)
            .options(selectinload(Workspace.business_profile))
            .where(Workspace.id == ws_uuid)
        )
        ws = (await db.execute(stmt)).scalar_one_or_none()
        if ws:
            return ws
    except (ValueError, AttributeError):
        pass

    # 2. Try lookup by slug or name
    stmt = (
        select(Workspace)
        .options(selectinload(Workspace.business_profile))
        .where((Workspace.slug == workspace_id_str) | (Workspace.name == workspace_id_str))
    )
    ws = (await db.execute(stmt)).scalar_one_or_none()
    if ws:
        return ws

    # 3. Try lookup by current_user membership if available
    if current_user:
        from whatsapp_agent.database.models import WorkspaceMember
        stmt = (
            select(Workspace)
            .options(selectinload(Workspace.business_profile))
            .join(WorkspaceMember, Workspace.id == WorkspaceMember.workspace_id)
            .where(WorkspaceMember.user_id == current_user.id)
            .limit(1)
        )
        ws = (await db.execute(stmt)).scalar_one_or_none()
        if ws:
            return ws

    # 4. Fallback to default workspace in database
    stmt = select(Workspace).options(selectinload(Workspace.business_profile)).limit(1)
    ws = (await db.execute(stmt)).scalar_one_or_none()
    if ws:
        return ws

    raise HTTPException(status_code=404, detail="Workspace not found")


@router.get("/{workspace_id}")
async def get_workspace(
    workspace_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Get workspace details including business profile."""
    workspace = await _resolve_workspace(workspace_id, db, current_user)

    bp = workspace.business_profile
    return {
        "id": workspace.id,
        "name": workspace.name,
        "slug": workspace.slug,
        "business_profile": {
            "business_name": bp.business_name if bp else "Our Business",
            "business_description": bp.business_description if bp else "",
            "ai_persona_name": bp.ai_persona_name if bp else "AI Assistant",
            "ai_persona_role": bp.ai_persona_role if bp else "Customer Support",
            "ai_persona_tone": bp.ai_persona_tone if bp else "professional",
            "ai_response_language": bp.ai_response_language if bp else "en",
            "ai_max_response_length": bp.ai_max_response_length if bp else 300,
            "ai_use_emoji": bp.ai_use_emoji if bp is not None and bp.ai_use_emoji is not None else True,
            "ai_custom_instructions": bp.ai_custom_instructions if bp else "",
            "ai_restrictions": bp.ai_restrictions if bp else "",
            "escalation_keywords_json": bp.escalation_keywords_json if bp and bp.escalation_keywords_json else ["human", "agent", "support", "help"],
        } if bp else None
    }

@router.patch("/{workspace_id}")
@router.patch("/{workspace_id}/business-profile")
async def update_business_profile(
    workspace_id: str,
    profile_update: BusinessProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Update a workspace's business profile and AI persona settings."""
    workspace = await _resolve_workspace(workspace_id, db, current_user)

    profile = workspace.business_profile
    if not profile:
        profile = BusinessProfile(
            workspace_id=workspace.id,
            business_name=workspace.name
        )
        db.add(profile)

    update_data = profile_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(profile, key, value)

    await db.commit()
    return {"status": "success"}

@router.post("/{workspace_id}/playground/chat")
async def playground_chat(
    workspace_id: str,
    request: PlaygroundChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Execute LangGraph multi-agent workflow synchronously in interactive Playground mode."""
    import time
    from whatsapp_agent.workflows.main_workflow import get_workflow

    workspace = await _resolve_workspace(workspace_id, db, current_user)
    actual_ws_id = str(workspace.id)

    start_time = time.monotonic()

    # Process multimodal media (image, document, voice)
    media_res = await _process_playground_multimodal(
        modality=request.modality or "text",
        raw_message=request.message or "",
        file_data=request.file_data,
        file_name=request.file_name,
        file_type=request.file_type
    )

    effective_raw_text = (request.message or "").strip()
    if media_res["modality"] == "image":
        if not effective_raw_text:
            effective_raw_text = "Please analyze the uploaded image."
    elif media_res["modality"] == "document":
        if not effective_raw_text:
            effective_raw_text = f"Please review this document ({request.file_name or 'file'})."
    elif media_res["modality"] == "voice":
        if not effective_raw_text:
            effective_raw_text = media_res["transcription"] or "Voice note received."

    state = {
        "workspace_id": actual_ws_id,
        "message_id": str(uuid.uuid4()),
        "contact_wa_id": request.sender_id or "playground_user",
        "contact_name": current_user.full_name or "Playground Tester",
        "raw_text": effective_raw_text,
        "transcription": media_res["transcription"],
        "image_analysis": media_res["image_analysis"],
        "document_text": media_res["document_text"],
        "input_modality": media_res["modality"],
        "conversation_history": []
    }

    try:
        workflow = get_workflow()
        result = await workflow.ainvoke(state)
        latency_ms = round((time.monotonic() - start_time) * 1000)
        response_val = result.get("response_text") or "No response generated"
        return {
            "response": response_val,
            "response_text": response_val,
            "intent": result.get("intent", "unknown"),
            "latency_ms": result.get("model_latency_ms") or latency_ms,
            "routed_agent": result.get("routed_to_agent", "supervisor"),
            "transcription": media_res["transcription"] or None,
            "image_analysis": media_res["image_analysis"] or None
        }
    except Exception as e:
        latency_ms = round((time.monotonic() - start_time) * 1000)
        return {
            "response": f"Error: {e}",
            "response_text": f"Error: {e}",
            "intent": "error",
            "latency_ms": latency_ms,
            "routed_agent": "error"
        }
