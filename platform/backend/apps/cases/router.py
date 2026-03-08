"""Case Management — generic ops case lifecycle for fintech.

Provides a unified case system for:
  - KYC review cases
  - Payout failure triage
  - Recon investigation
  - Risk alert review
  - Compliance investigation
  - Customer support

Features:
  - Assignment (auto or manual)
  - State machine (open → in_progress → pending_info → resolved → closed)
  - SLA timers with escalation
  - Comments/notes timeline
  - Related entities linking
  - AI summary attachment
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta
from enum import StrEnum
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import Column, DateTime, String, Text, Integer
from sqlalchemy.dialects.postgresql import JSONB, UUID, ARRAY

from packages.core.models import APIResponse, BaseDTO
from packages.db.base import Base, TimestampMixin


# ─── Schema ───

class Case(Base, TimestampMixin):
    """A generic operations case."""
    __tablename__ = "cases"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False, index=True)

    # Classification
    case_type = Column(String(50), nullable=False, index=True,
                       comment="kyc_review | payout_triage | recon_investigation | risk_alert | compliance | support")
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    priority = Column(String(20), nullable=False, default="medium",
                      comment="low | medium | high | critical")
    severity = Column(String(20), nullable=True, comment="P1 | P2 | P3 | P4")

    # State
    status = Column(String(30), nullable=False, default="open", index=True,
                    comment="open | assigned | in_progress | pending_info | resolved | closed | escalated")

    # Assignment
    assigned_to = Column(UUID(as_uuid=True), nullable=True, index=True)
    assigned_at = Column(DateTime(timezone=True), nullable=True)
    escalated_to = Column(UUID(as_uuid=True), nullable=True)
    escalation_reason = Column(Text, nullable=True)

    # SLA
    sla_due_at = Column(DateTime(timezone=True), nullable=True)
    sla_breached = Column(String(10), nullable=True, default="no", comment="no | warning | breached")

    # Related entities
    related_entity_type = Column(String(50), nullable=True, comment="payout | kyc_case | recon_run | risk_score")
    related_entity_id = Column(String(200), nullable=True, index=True)

    # Resolution
    resolution = Column(Text, nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    resolved_by = Column(UUID(as_uuid=True), nullable=True)

    # AI
    ai_summary = Column(Text, nullable=True)
    ai_recommendation = Column(Text, nullable=True)

    # Rich metadata
    tags = Column(JSONB, nullable=False, server_default='[]')
    metadata_ = Column("metadata", JSONB, nullable=False, server_default='{}')


class CaseComment(Base, TimestampMixin):
    """A comment/note on a case (timeline entry)."""
    __tablename__ = "case_comments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    author_id = Column(UUID(as_uuid=True), nullable=False)
    comment_type = Column(String(20), nullable=False, default="note",
                          comment="note | status_change | assignment | escalation | ai_analysis | resolution")
    content = Column(Text, nullable=False)
    metadata_ = Column("metadata", JSONB, nullable=False, server_default='{}')


# ─── SLA configuration per case type ───

SLA_HOURS = {
    "kyc_review": {"low": 48, "medium": 24, "high": 4, "critical": 1},
    "payout_triage": {"low": 24, "medium": 4, "high": 1, "critical": 0.5},
    "recon_investigation": {"low": 72, "medium": 48, "high": 24, "critical": 4},
    "risk_alert": {"low": 48, "medium": 12, "high": 2, "critical": 0.5},
    "compliance": {"low": 120, "medium": 72, "high": 24, "critical": 4},
    "support": {"low": 72, "medium": 24, "high": 8, "critical": 2},
}


# ─── DTOs ───

class CaseStatus(StrEnum):
    OPEN = "open"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    PENDING_INFO = "pending_info"
    RESOLVED = "resolved"
    CLOSED = "closed"
    ESCALATED = "escalated"


class CreateCaseRequest(BaseModel):
    case_type: str
    title: str
    description: str | None = None
    priority: str = "medium"
    related_entity_type: str | None = None
    related_entity_id: str | None = None
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class UpdateCaseRequest(BaseModel):
    status: str | None = None
    assigned_to: str | None = None
    priority: str | None = None
    resolution: str | None = None
    ai_summary: str | None = None
    ai_recommendation: str | None = None


class AddCommentRequest(BaseModel):
    content: str
    comment_type: str = "note"


class CaseDTO(BaseDTO):
    id: str
    case_type: str
    title: str
    status: str
    priority: str
    assigned_to: str | None = None
    sla_due_at: datetime | None = None
    sla_breached: str = "no"
    related_entity_type: str | None = None
    related_entity_id: str | None = None
    created_at: datetime
    ai_summary: str | None = None


# ─── Router ───

router = APIRouter()


@router.post("/", response_model=APIResponse[CaseDTO])
async def create_case(
    body: CreateCaseRequest,
    x_tenant_id: str = Header(...),
    x_user_id: str = Header(...),
):
    """Create a new operations case."""
    from packages.db.engine import get_session_factory

    case_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    # Calculate SLA deadline
    sla_map = SLA_HOURS.get(body.case_type, SLA_HOURS["support"])
    sla_hours = sla_map.get(body.priority, 24)
    sla_due = now + timedelta(hours=sla_hours)

    case = Case(
        id=case_id,
        tenant_id=uuid.UUID(x_tenant_id),
        case_type=body.case_type,
        title=body.title,
        description=body.description,
        priority=body.priority,
        status=CaseStatus.OPEN.value,
        sla_due_at=sla_due,
        related_entity_type=body.related_entity_type,
        related_entity_id=body.related_entity_id,
        tags=body.tags,
        metadata_=body.metadata,
    )

    factory = get_session_factory()
    async with factory() as session:
        session.add(case)
        # Add creation comment
        comment = CaseComment(
            case_id=case_id,
            author_id=uuid.UUID(x_user_id),
            comment_type="status_change",
            content=f"Case created: {body.title}",
        )
        session.add(comment)
        await session.commit()

    return APIResponse.ok(CaseDTO(
        id=str(case_id),
        case_type=body.case_type,
        title=body.title,
        status="open",
        priority=body.priority,
        sla_due_at=sla_due,
        related_entity_type=body.related_entity_type,
        related_entity_id=body.related_entity_id,
        created_at=now,
    ))


@router.patch("/{case_id}", response_model=APIResponse[dict])
async def update_case(
    case_id: str,
    body: UpdateCaseRequest,
    x_tenant_id: str = Header(...),
    x_user_id: str = Header(...),
):
    """Update a case (status, assignment, resolution, AI summary)."""
    from sqlalchemy import select
    from packages.db.engine import get_session_factory

    factory = get_session_factory()
    async with factory() as session:
        stmt = select(Case).where(
            Case.id == uuid.UUID(case_id),
            Case.tenant_id == uuid.UUID(x_tenant_id),
        )
        result = await session.execute(stmt)
        case = result.scalar_one_or_none()
        if not case:
            raise HTTPException(status_code=404, detail="Case not found")

        changes = []
        now = datetime.now(timezone.utc)

        if body.status:
            old_status = case.status
            case.status = body.status
            changes.append(f"Status: {old_status} → {body.status}")
            if body.status == CaseStatus.RESOLVED.value:
                case.resolved_at = now
                case.resolved_by = uuid.UUID(x_user_id)

        if body.assigned_to:
            case.assigned_to = uuid.UUID(body.assigned_to)
            case.assigned_at = now
            case.status = CaseStatus.ASSIGNED.value
            changes.append(f"Assigned to {body.assigned_to}")

        if body.resolution:
            case.resolution = body.resolution
            changes.append("Resolution added")

        if body.ai_summary:
            case.ai_summary = body.ai_summary
            changes.append("AI summary updated")

        if body.ai_recommendation:
            case.ai_recommendation = body.ai_recommendation

        if body.priority:
            case.priority = body.priority
            changes.append(f"Priority → {body.priority}")

        # Add timeline comment for changes
        if changes:
            comment = CaseComment(
                case_id=uuid.UUID(case_id),
                author_id=uuid.UUID(x_user_id),
                comment_type="status_change",
                content="; ".join(changes),
            )
            session.add(comment)

        await session.commit()

    return APIResponse.ok({"case_id": case_id, "changes": changes})


@router.post("/{case_id}/comments", response_model=APIResponse[dict])
async def add_comment(
    case_id: str,
    body: AddCommentRequest,
    x_tenant_id: str = Header(...),
    x_user_id: str = Header(...),
):
    """Add a comment/note to a case timeline."""
    from packages.db.engine import get_session_factory

    comment_id = uuid.uuid4()
    factory = get_session_factory()
    async with factory() as session:
        comment = CaseComment(
            id=comment_id,
            case_id=uuid.UUID(case_id),
            author_id=uuid.UUID(x_user_id),
            comment_type=body.comment_type,
            content=body.content,
        )
        session.add(comment)
        await session.commit()

    return APIResponse.ok({"comment_id": str(comment_id)})


@router.get("/", response_model=APIResponse[list[CaseDTO]])
async def list_cases(
    x_tenant_id: str = Header(...),
    case_type: str | None = Query(None),
    status: str | None = Query(None),
    assigned_to: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    """List cases with filters."""
    from sqlalchemy import select
    from packages.db.engine import get_session_factory

    factory = get_session_factory()
    async with factory() as session:
        stmt = (
            select(Case)
            .where(Case.tenant_id == uuid.UUID(x_tenant_id))
            .order_by(Case.created_at.desc())
            .limit(limit)
        )
        if case_type:
            stmt = stmt.where(Case.case_type == case_type)
        if status:
            stmt = stmt.where(Case.status == status)
        if assigned_to:
            stmt = stmt.where(Case.assigned_to == uuid.UUID(assigned_to))

        result = await session.execute(stmt)
        rows = list(result.scalars().all())

    return APIResponse.ok([
        CaseDTO(
            id=str(c.id),
            case_type=c.case_type,
            title=c.title,
            status=c.status,
            priority=c.priority,
            assigned_to=str(c.assigned_to) if c.assigned_to else None,
            sla_due_at=c.sla_due_at,
            sla_breached=c.sla_breached or "no",
            related_entity_type=c.related_entity_type,
            related_entity_id=c.related_entity_id,
            created_at=c.created_at,
            ai_summary=c.ai_summary,
        )
        for c in rows
    ])


@router.get("/{case_id}/timeline", response_model=APIResponse[list[dict]])
async def get_timeline(
    case_id: str,
    x_tenant_id: str = Header(...),
):
    """Get the full timeline of a case (comments, status changes, AI analysis)."""
    from sqlalchemy import select
    from packages.db.engine import get_session_factory

    factory = get_session_factory()
    async with factory() as session:
        stmt = (
            select(CaseComment)
            .where(CaseComment.case_id == uuid.UUID(case_id))
            .order_by(CaseComment.created_at.asc())
        )
        result = await session.execute(stmt)
        comments = list(result.scalars().all())

    return APIResponse.ok([
        {
            "id": str(c.id),
            "type": c.comment_type,
            "content": c.content,
            "author_id": str(c.author_id),
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in comments
    ])
