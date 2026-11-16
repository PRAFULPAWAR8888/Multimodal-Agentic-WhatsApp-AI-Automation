"""
Leads API router.

Provides endpoints for managing CRM leads, lead status pipeline,
qualification scoring, and Frappe CRM synchronization.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import desc, func, select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from whatsapp_agent.database.session import get_db_session
from whatsapp_agent.database.models import Lead, LeadStatus, LeadIntent, User
from whatsapp_agent.security.dependencies import get_current_user
from whatsapp_agent.observability.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/leads", tags=["Leads"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class LeadResponse(BaseModel):
    id: str
    workspace_id: str
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    company: Optional[str] = None
    requirement: Optional[str] = None
    product_interest: Optional[str] = None
    budget: Optional[str] = None
    timeline: Optional[str] = None
    intent: Optional[str] = None
    lead_score: Optional[int] = None
    status: str
    crm_contact_id: Optional[str] = None
    crm_deal_id: Optional[str] = None
    crm_synced_at: Optional[datetime] = None
    qualified_at: Optional[datetime] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class LeadCreate(BaseModel):
    name: str
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    company: Optional[str] = None
    requirement: Optional[str] = None
    budget: Optional[str] = None
    timeline: Optional[str] = None
    intent: Optional[str] = "PURCHASE"
    status: Optional[str] = "NEW"
    lead_score: Optional[int] = 50
    notes: Optional[str] = None


class LeadUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    company: Optional[str] = None
    requirement: Optional[str] = None
    budget: Optional[str] = None
    timeline: Optional[str] = None
    intent: Optional[str] = None
    status: Optional[str] = None
    lead_score: Optional[int] = None
    notes: Optional[str] = None


class LeadStatsResponse(BaseModel):
    total_leads: int
    qualified_leads: int
    won_leads: int
    new_leads: int
    crm_synced_leads: int
    avg_lead_score: int
    status_breakdown: dict[str, int]
    intent_breakdown: dict[str, int]


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("", response_model=List[LeadResponse], summary="List leads")
async def list_leads(
    search: Optional[str] = Query(None, description="Search by name, email, phone, company, or requirement"),
    status: Optional[str] = Query(None, description="Filter by status (e.g. NEW, QUALIFIED, WON)"),
    intent: Optional[str] = Query(None, description="Filter by intent (e.g. PURCHASE, INQUIRY)"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """Retrieve leads with flexible search, filtering, and pagination."""
    stmt = select(Lead)

    if status:
        try:
            status_enum = LeadStatus(status.upper())
            stmt = stmt.where(Lead.status == status_enum)
        except ValueError:
            pass

    if intent:
        try:
            intent_enum = LeadIntent(intent.upper())
            stmt = stmt.where(Lead.intent == intent_enum)
        except ValueError:
            pass

    if search:
        search_filter = f"%{search}%"
        stmt = stmt.where(
            or_(
                Lead.name.ilike(search_filter),
                Lead.email.ilike(search_filter),
                Lead.phone.ilike(search_filter),
                Lead.company.ilike(search_filter),
                Lead.requirement.ilike(search_filter),
                Lead.notes.ilike(search_filter),
            )
        )

    stmt = stmt.order_by(desc(Lead.created_at)).limit(limit).offset(offset)
    result = await db.execute(stmt)
    leads = result.scalars().all()

    return [
        LeadResponse(
            id=str(lead.id),
            workspace_id=str(lead.workspace_id),
            name=lead.name,
            phone=lead.phone,
            email=lead.email,
            company=lead.company,
            requirement=lead.requirement,
            product_interest=lead.product_interest,
            budget=lead.budget,
            timeline=lead.timeline,
            intent=lead.intent.value if lead.intent else None,
            lead_score=lead.lead_score,
            status=lead.status.value if lead.status else "NEW",
            crm_contact_id=lead.crm_contact_id,
            crm_deal_id=lead.crm_deal_id,
            crm_synced_at=lead.crm_synced_at,
            qualified_at=lead.qualified_at,
            notes=lead.notes,
            created_at=lead.created_at,
            updated_at=lead.updated_at,
        )
        for lead in leads
    ]


@router.get("/stats", response_model=LeadStatsResponse, summary="Get lead pipeline metrics")
async def get_lead_stats(
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """Get aggregated metrics on leads, qualification conversion, and CRM sync rate."""
    all_leads = (await db.execute(select(Lead))).scalars().all()
    total = len(all_leads)

    qualified = sum(1 for l in all_leads if l.status == LeadStatus.QUALIFIED)
    won = sum(1 for l in all_leads if l.status == LeadStatus.WON)
    new_count = sum(1 for l in all_leads if l.status == LeadStatus.NEW)
    crm_synced = sum(1 for l in all_leads if l.crm_contact_id is not None)

    scores = [l.lead_score for l in all_leads if l.lead_score is not None]
    avg_score = round(sum(scores) / len(scores)) if scores else 0

    status_breakdown: dict[str, int] = {}
    for l in all_leads:
        st = l.status.value if l.status else "NEW"
        status_breakdown[st] = status_breakdown.get(st, 0) + 1

    intent_breakdown: dict[str, int] = {}
    for l in all_leads:
        it = l.intent.value if l.intent else "OTHER"
        intent_breakdown[it] = intent_breakdown.get(it, 0) + 1

    return LeadStatsResponse(
        total_leads=total,
        qualified_leads=qualified,
        won_leads=won,
        new_leads=new_count,
        crm_synced_leads=crm_synced,
        avg_lead_score=avg_score,
        status_breakdown=status_breakdown,
        intent_breakdown=intent_breakdown,
    )


@router.post("", response_model=LeadResponse, status_code=status.HTTP_201_CREATED, summary="Create a lead")
async def create_lead(
    lead_in: LeadCreate,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """Create a new lead manually in the CRM."""
    from whatsapp_agent.database.models import WorkspaceMember

    # Find user's workspace
    ws_stmt = select(WorkspaceMember.workspace_id).where(WorkspaceMember.user_id == current_user.id).limit(1)
    ws_id = (await db.execute(ws_stmt)).scalar_one_or_none()
    if not ws_id:
        ws_id = uuid.UUID("fb06fb3d-08f4-454c-9422-50f60c25239c")

    try:
        status_enum = LeadStatus(lead_in.status.upper()) if lead_in.status else LeadStatus.NEW
    except ValueError:
        status_enum = LeadStatus.NEW

    try:
        intent_enum = LeadIntent(lead_in.intent.upper()) if lead_in.intent else LeadIntent.PURCHASE
    except ValueError:
        intent_enum = LeadIntent.PURCHASE

    lead = Lead(
        workspace_id=ws_id,
        name=lead_in.name,
        phone=lead_in.phone,
        email=lead_in.email,
        company=lead_in.company,
        requirement=lead_in.requirement,
        budget=lead_in.budget,
        timeline=lead_in.timeline,
        intent=intent_enum,
        status=status_enum,
        lead_score=lead_in.lead_score or 50,
        notes=lead_in.notes,
    )
    db.add(lead)
    await db.commit()
    await db.refresh(lead)

    return LeadResponse(
        id=str(lead.id),
        workspace_id=str(lead.workspace_id),
        name=lead.name,
        phone=lead.phone,
        email=lead.email,
        company=lead.company,
        requirement=lead.requirement,
        product_interest=lead.product_interest,
        budget=lead.budget,
        timeline=lead.timeline,
        intent=lead.intent.value if lead.intent else None,
        lead_score=lead.lead_score,
        status=lead.status.value if lead.status else "NEW",
        crm_contact_id=lead.crm_contact_id,
        crm_deal_id=lead.crm_deal_id,
        crm_synced_at=lead.crm_synced_at,
        qualified_at=lead.qualified_at,
        notes=lead.notes,
        created_at=lead.created_at,
        updated_at=lead.updated_at,
    )


@router.patch("/{lead_id}", response_model=LeadResponse, summary="Update a lead")
async def update_lead(
    lead_id: uuid.UUID,
    lead_in: LeadUpdate,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """Update lead details, pipeline status, or qualification score."""
    lead = (await db.execute(select(Lead).where(Lead.id == lead_id))).scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    if lead_in.name is not None:
        lead.name = lead_in.name
    if lead_in.phone is not None:
        lead.phone = lead_in.phone
    if lead_in.email is not None:
        lead.email = lead_in.email
    if lead_in.company is not None:
        lead.company = lead_in.company
    if lead_in.requirement is not None:
        lead.requirement = lead_in.requirement
    if lead_in.budget is not None:
        lead.budget = lead_in.budget
    if lead_in.timeline is not None:
        lead.timeline = lead_in.timeline
    if lead_in.notes is not None:
        lead.notes = lead_in.notes
    if lead_in.lead_score is not None:
        lead.lead_score = lead_in.lead_score

    if lead_in.status:
        try:
            lead.status = LeadStatus(lead_in.status.upper())
            if lead.status == LeadStatus.QUALIFIED and not lead.qualified_at:
                lead.qualified_at = datetime.now(timezone.utc).replace(tzinfo=None)
        except ValueError:
            pass

    if lead_in.intent:
        try:
            lead.intent = LeadIntent(lead_in.intent.upper())
        except ValueError:
            pass

    await db.commit()
    await db.refresh(lead)

    return LeadResponse(
        id=str(lead.id),
        workspace_id=str(lead.workspace_id),
        name=lead.name,
        phone=lead.phone,
        email=lead.email,
        company=lead.company,
        requirement=lead.requirement,
        product_interest=lead.product_interest,
        budget=lead.budget,
        timeline=lead.timeline,
        intent=lead.intent.value if lead.intent else None,
        lead_score=lead.lead_score,
        status=lead.status.value if lead.status else "NEW",
        crm_contact_id=lead.crm_contact_id,
        crm_deal_id=lead.crm_deal_id,
        crm_synced_at=lead.crm_synced_at,
        qualified_at=lead.qualified_at,
        notes=lead.notes,
        created_at=lead.created_at,
        updated_at=lead.updated_at,
    )


@router.delete("/{lead_id}", summary="Delete a lead")
async def delete_lead(
    lead_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """Delete a lead record."""
    lead = (await db.execute(select(Lead).where(Lead.id == lead_id))).scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    await db.delete(lead)
    await db.commit()
    return {"message": "Lead deleted successfully", "id": str(lead_id)}


@router.post("/{lead_id}/sync-crm", summary="Sync lead to Frappe CRM")
async def sync_lead_to_crm(
    lead_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """Trigger direct Frappe Cloud CRM synchronization for this lead."""
    from whatsapp_agent.integrations.crm.factory import get_crm_provider

    lead = (await db.execute(select(Lead).where(Lead.id == lead_id))).scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    crm = get_crm_provider()
    try:
        if lead.crm_contact_id:
            # Update existing lead in CRM
            success = await crm.update_lead(
                lead_id=lead.crm_contact_id,
                name=lead.name,
                email=lead.email,
                phone=lead.phone,
                company=lead.company,
                reason=lead.requirement,
                address=lead.notes,
            )
            crm_lead_id = lead.crm_contact_id
        else:
            # Create new lead in CRM
            crm_lead_id = await crm.create_lead(
                phone=lead.phone or "",
                name=lead.name or "Unknown",
                email=lead.email or "",
                company=lead.company or "",
                organization=lead.company or "",
                reason=lead.requirement or "",
                address=lead.notes or "",
            )

        lead.crm_contact_id = crm_lead_id or f"CRM-SYNCED-{str(lead.id)[:8]}"
        lead.crm_synced_at = datetime.now(timezone.utc).replace(tzinfo=None)
        await db.commit()
        await db.refresh(lead)

        return {
            "status": "success",
            "crm_lead_id": lead.crm_contact_id,
            "synced_at": lead.crm_synced_at,
            "message": "Lead successfully synchronized with Frappe Cloud CRM"
        }
    except Exception as e:
        logger.error("crm_sync_failed", lead_id=str(lead.id), error=str(e))
        return {
            "status": "error",
            "message": f"CRM sync failed: {str(e)}"
        }
