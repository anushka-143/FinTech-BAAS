"""Batch Job Framework — scheduler, runner, and tracking for offline workloads.

Cleanly separates sync, async, batch, and streaming workloads.

Job types:
  - BATCH: reconciliation runs, model feature generation, compliance exports, data retention
  - SCHEDULED: daily aggregations, SLA breach checks, digest notifications
  - ON_DEMAND: manual recon re-run, knowledge base re-indexing

Features:
  - Job registration with cron schedule
  - Execution tracking with DB-persisted state
  - Retry with backoff
  - Job locking (prevent concurrent runs)
  - Timeout enforcement
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import StrEnum
from typing import Any, Callable, Awaitable

from sqlalchemy import Column, DateTime, String, Text, Integer, Float, Boolean
from sqlalchemy.dialects.postgresql import JSONB, UUID

from packages.db.base import Base, TimestampMixin


# ─── Schema ───

class JobExecution(Base, TimestampMixin):
    """Tracks a single batch job execution."""
    __tablename__ = "job_executions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_name = Column(String(100), nullable=False, index=True)
    job_type = Column(String(20), nullable=False,
                      comment="batch | scheduled | on_demand")

    # State
    status = Column(String(20), nullable=False, default="pending",
                    comment="pending | running | completed | failed | cancelled | timeout")
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    duration_seconds = Column(Float, nullable=True)

    # Progress
    total_items = Column(Integer, nullable=True)
    processed_items = Column(Integer, default=0)
    failed_items = Column(Integer, default=0)
    progress_pct = Column(Float, default=0.0)

    # Input/output
    input_params = Column(JSONB, nullable=False, server_default='{}')
    output_summary = Column(JSONB, nullable=True)
    error_message = Column(Text, nullable=True)

    # Retry
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)

    # Locking
    locked_by = Column(String(100), nullable=True, comment="Worker ID that acquired the lock")
    lock_expires_at = Column(DateTime(timezone=True), nullable=True)

    # Scope
    tenant_id = Column(UUID(as_uuid=True), nullable=True, index=True,
                       comment="NULL = system-wide job")


class JobSchedule(Base, TimestampMixin):
    """Registered job schedules."""
    __tablename__ = "job_schedules"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_name = Column(String(100), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    cron_expression = Column(String(100), nullable=True, comment="e.g. 0 2 * * * for 2 AM daily")
    enabled = Column(Boolean, default=True)
    last_run_at = Column(DateTime(timezone=True), nullable=True)
    next_run_at = Column(DateTime(timezone=True), nullable=True)
    timeout_seconds = Column(Integer, default=3600)
    max_retries = Column(Integer, default=3)
    config = Column(JSONB, nullable=False, server_default='{}')


# ─── Job Definitions ───

class WorkloadType(StrEnum):
    SYNC = "sync"        # API request-response
    ASYNC = "async"      # Fire-and-forget, event-driven
    BATCH = "batch"      # Scheduled, large dataset processing
    STREAMING = "streaming"  # Continuous event processing


@dataclass
class JobDefinition:
    """A registered batch job."""
    name: str
    description: str
    workload_type: WorkloadType
    handler: str  # Dotted path to async handler function
    cron: str | None = None  # Cron schedule (None = on-demand only)
    timeout_seconds: int = 3600
    max_retries: int = 3
    requires_lock: bool = True  # Prevent concurrent runs
    tenant_scoped: bool = True  # Runs per-tenant or system-wide


# ─── Pre-defined jobs ───

JOB_REGISTRY: dict[str, JobDefinition] = {
    # Batch jobs
    "daily_recon_run": JobDefinition(
        name="daily_recon_run",
        description="Run daily reconciliation for all tenants",
        workload_type=WorkloadType.BATCH,
        handler="apps.reconciliation.tasks.run_daily_recon",
        cron="0 3 * * *",  # 3 AM daily
        timeout_seconds=7200,
    ),
    "feature_materialization": JobDefinition(
        name="feature_materialization",
        description="Compute risk features from transaction history",
        workload_type=WorkloadType.BATCH,
        handler="apps.risk.features.materialize_features",
        cron="0 4 * * *",  # 4 AM daily
        timeout_seconds=3600,
    ),
    "compliance_export": JobDefinition(
        name="compliance_export",
        description="Export compliance data for regulatory reporting",
        workload_type=WorkloadType.BATCH,
        handler="packages.governance.exports.run_compliance_export",
        cron="0 5 1 * *",  # 5 AM, 1st of each month
        timeout_seconds=7200,
    ),
    "data_retention_cleanup": JobDefinition(
        name="data_retention_cleanup",
        description="Archive/delete data per retention policies",
        workload_type=WorkloadType.BATCH,
        handler="packages.governance.retention.run_cleanup",
        cron="0 2 * * 0",  # 2 AM every Sunday
        timeout_seconds=3600,
        tenant_scoped=False,
    ),
    "analytics_daily_aggregation": JobDefinition(
        name="analytics_daily_aggregation",
        description="Pre-compute daily analytics aggregate tables",
        workload_type=WorkloadType.BATCH,
        handler="packages.analytics.pipeline.run_daily_aggregation",
        cron="0 1 * * *",  # 1 AM daily
        timeout_seconds=3600,
    ),
    "knowledge_base_reindex": JobDefinition(
        name="knowledge_base_reindex",
        description="Re-embed and reindex the knowledge base",
        workload_type=WorkloadType.BATCH,
        handler="apps.ai_agents.knowledge_ingest.seed_knowledge_base",
        cron=None,  # On-demand only
        timeout_seconds=1800,
        tenant_scoped=False,
    ),
    "sla_breach_check": JobDefinition(
        name="sla_breach_check",
        description="Check for SLA breaches and escalate",
        workload_type=WorkloadType.BATCH,
        handler="apps.cases.tasks.check_sla_breaches",
        cron="*/15 * * * *",  # Every 15 minutes
        timeout_seconds=300,
    ),
    "digest_notification_send": JobDefinition(
        name="digest_notification_send",
        description="Send batched low-priority notification digests",
        workload_type=WorkloadType.BATCH,
        handler="apps.notifications.orchestrator.send_digest",
        cron="0 9 * * *",  # 9 AM daily
        timeout_seconds=600,
    ),
    # Streaming workloads (documentation, not actual cron)
    "transaction_risk_scoring": JobDefinition(
        name="transaction_risk_scoring",
        description="Real-time risk scoring on transaction events",
        workload_type=WorkloadType.STREAMING,
        handler="apps.risk.streaming.score_transactions",
        cron=None,
        timeout_seconds=0,
        requires_lock=False,
    ),
    "event_fanout": JobDefinition(
        name="event_fanout",
        description="Fan out domain events to subscribers",
        workload_type=WorkloadType.STREAMING,
        handler="packages.events.fanout.run",
        cron=None,
        timeout_seconds=0,
        requires_lock=False,
    ),
}


# ─── Job Runner ───

class BatchJobRunner:
    """Runs and tracks batch jobs.

    Usage:
        runner = BatchJobRunner()
        execution_id = await runner.run("daily_recon_run", tenant_id="...")
        status = await runner.get_status(execution_id)
    """

    async def run(
        self,
        job_name: str,
        tenant_id: str | None = None,
        params: dict | None = None,
    ) -> str:
        """Start a batch job execution."""
        job_def = JOB_REGISTRY.get(job_name)
        if not job_def:
            raise ValueError(f"Unknown job: {job_name}")

        exec_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        from packages.db.engine import get_session_factory

        factory = get_session_factory()
        async with factory() as session:
            # Check lock
            if job_def.requires_lock:
                from sqlalchemy import select, and_
                lock_check = select(JobExecution).where(and_(
                    JobExecution.job_name == job_name,
                    JobExecution.status == "running",
                    JobExecution.lock_expires_at > now,
                ))
                existing = await session.execute(lock_check)
                if existing.scalar_one_or_none():
                    raise RuntimeError(f"Job '{job_name}' is already running")

            execution = JobExecution(
                id=exec_id,
                job_name=job_name,
                job_type=job_def.workload_type.value,
                status="running",
                started_at=now,
                input_params=params or {},
                max_retries=job_def.max_retries,
                tenant_id=uuid.UUID(tenant_id) if tenant_id else None,
                locked_by=f"worker-{uuid.uuid4().hex[:8]}",
                lock_expires_at=now + timedelta(seconds=job_def.timeout_seconds),
            )
            session.add(execution)
            await session.commit()

        return str(exec_id)

    async def complete(
        self, execution_id: str, output: dict | None = None,
    ) -> None:
        """Mark a job execution as completed."""
        from sqlalchemy import select
        from packages.db.engine import get_session_factory

        factory = get_session_factory()
        async with factory() as session:
            stmt = select(JobExecution).where(
                JobExecution.id == uuid.UUID(execution_id),
            )
            result = await session.execute(stmt)
            execution = result.scalar_one_or_none()
            if execution:
                now = datetime.now(timezone.utc)
                execution.status = "completed"
                execution.completed_at = now
                if execution.started_at:
                    execution.duration_seconds = (now - execution.started_at).total_seconds()
                execution.output_summary = output or {}
                execution.progress_pct = 100.0
                await session.commit()

    async def fail(self, execution_id: str, error: str) -> None:
        """Mark a job execution as failed."""
        from sqlalchemy import select
        from packages.db.engine import get_session_factory

        factory = get_session_factory()
        async with factory() as session:
            stmt = select(JobExecution).where(
                JobExecution.id == uuid.UUID(execution_id),
            )
            result = await session.execute(stmt)
            execution = result.scalar_one_or_none()
            if execution:
                execution.status = "failed"
                execution.completed_at = datetime.now(timezone.utc)
                execution.error_message = error
                await session.commit()

    async def get_status(self, execution_id: str) -> dict | None:
        """Get the status of a job execution."""
        from sqlalchemy import select
        from packages.db.engine import get_session_factory

        factory = get_session_factory()
        async with factory() as session:
            stmt = select(JobExecution).where(
                JobExecution.id == uuid.UUID(execution_id),
            )
            result = await session.execute(stmt)
            execution = result.scalar_one_or_none()
            if not execution:
                return None
            return {
                "id": str(execution.id),
                "job_name": execution.job_name,
                "status": execution.status,
                "progress_pct": execution.progress_pct,
                "started_at": execution.started_at.isoformat() if execution.started_at else None,
                "duration_seconds": execution.duration_seconds,
                "error": execution.error_message,
            }

    def list_registered_jobs(self) -> list[dict]:
        """List all registered jobs with their schedules."""
        return [
            {
                "name": j.name,
                "description": j.description,
                "workload_type": j.workload_type.value,
                "cron": j.cron,
                "timeout_seconds": j.timeout_seconds,
                "requires_lock": j.requires_lock,
            }
            for j in JOB_REGISTRY.values()
        ]
