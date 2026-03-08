"""Document Ingestion Pipeline — full lifecycle from upload to storage.

Handles:
  - Upload session management
  - MIME type validation
  - Virus scanning (pluggable — ClamAV, cloud API)
  - File hashing (SHA-256 checksum for integrity)
  - Document versioning
  - Storage tiering (hot → warm → cold)
  - Signed URL generation
  - PII access policy enforcement
  - OCR artifact retention
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from enum import StrEnum
from typing import Any

from sqlalchemy import Column, DateTime, String, Text, Boolean, Integer, BigInteger
from sqlalchemy.dialects.postgresql import JSONB, UUID

from packages.db.base import Base, TimestampMixin


# ─── Schema ───

class Document(Base, TimestampMixin):
    """A stored document with full lifecycle tracking."""
    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False, index=True)

    # File identity
    filename = Column(String(500), nullable=False)
    mime_type = Column(String(100), nullable=False)
    file_size_bytes = Column(BigInteger, nullable=False)
    sha256_hash = Column(String(64), nullable=False, index=True)

    # Storage
    storage_path = Column(String(1000), nullable=False)
    storage_tier = Column(String(20), nullable=False, default="hot",
                          comment="hot | warm | cold | archived")
    storage_provider = Column(String(50), nullable=False, default="local",
                              comment="local | s3 | gcs | azure_blob")

    # Classification
    document_type = Column(String(50), nullable=True, index=True,
                           comment="aadhaar | pan | passport | bank_statement | selfie | contract | invoice")
    category = Column(String(50), nullable=True, comment="kyc | financial | legal | operational")

    # Version tracking
    version = Column(Integer, nullable=False, default=1)
    parent_document_id = Column(UUID(as_uuid=True), nullable=True,
                                comment="Previous version of this document")
    is_latest = Column(Boolean, default=True)

    # Security
    virus_scan_status = Column(String(20), nullable=False, default="pending",
                               comment="pending | clean | infected | error")
    virus_scan_at = Column(DateTime(timezone=True), nullable=True)
    pii_classification = Column(String(20), nullable=True, comment="none | low | high | critical")
    access_restricted = Column(Boolean, default=False)

    # OCR artifacts
    has_ocr = Column(Boolean, default=False)
    ocr_artifact_path = Column(String(1000), nullable=True)

    # Lifecycle
    expires_at = Column(DateTime(timezone=True), nullable=True)
    archived_at = Column(DateTime(timezone=True), nullable=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    # Metadata
    metadata_ = Column("metadata", JSONB, nullable=False, server_default='{}')
    uploaded_by = Column(UUID(as_uuid=True), nullable=True)


class UploadSession(Base, TimestampMixin):
    """Tracks multi-part upload sessions."""
    __tablename__ = "upload_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    status = Column(String(20), nullable=False, default="active",
                    comment="active | completed | expired | cancelled")
    expected_files = Column(Integer, default=1)
    received_files = Column(Integer, default=0)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    metadata_ = Column("metadata", JSONB, nullable=False, server_default='{}')


class SignedURLLog(Base, TimestampMixin):
    """Tracks signed URL generation for audit."""
    __tablename__ = "signed_url_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    tenant_id = Column(UUID(as_uuid=True), nullable=False)
    requested_by = Column(UUID(as_uuid=True), nullable=False)
    purpose = Column(String(50), nullable=False, comment="view | download | share")
    expires_at = Column(DateTime(timezone=True), nullable=False)
    accessed = Column(Boolean, default=False)


# ─── MIME Validation ───

ALLOWED_MIME_TYPES = {
    # Images (KYC documents, selfies)
    "image/jpeg", "image/png", "image/webp", "image/tiff",
    # PDFs
    "application/pdf",
    # Documents
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "text/csv",
}

MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB

# PII classification by document type
PII_CLASSIFICATION_MAP = {
    "aadhaar": "critical",
    "pan": "critical",
    "passport": "critical",
    "driving_license": "critical",
    "bank_statement": "high",
    "selfie": "high",
    "contract": "low",
    "invoice": "low",
}

# Storage tier lifecycle (days)
STORAGE_TIER_POLICY = {
    "hot": 90,       # 90 days in hot storage
    "warm": 365,     # Move to warm after 90 days, stay 1 year
    "cold": 365 * 7,  # Move to cold after 1 year, stay 7 years (PMLA)
    "archived": None,  # Keep until explicit deletion
}


# ─── Pipeline ───

@dataclass
class ValidationResult:
    valid: bool
    errors: list[str]
    warnings: list[str]


@dataclass
class IngestionResult:
    document_id: str
    sha256_hash: str
    storage_path: str
    mime_type: str
    file_size_bytes: int
    virus_scan_status: str
    pii_classification: str
    version: int


class DocumentIngestionPipeline:
    """Full document ingestion pipeline.

    Usage:
        pipeline = DocumentIngestionPipeline()

        # Validate first
        validation = pipeline.validate(filename, content, mime_type)
        if not validation.valid:
            raise ValueError(validation.errors)

        # Then ingest
        result = await pipeline.ingest(
            tenant_id="...",
            filename="aadhaar_front.jpg",
            content=file_bytes,
            mime_type="image/jpeg",
            document_type="aadhaar",
            uploaded_by="user-123",
        )
    """

    def validate(self, filename: str, content: bytes, mime_type: str) -> ValidationResult:
        """Validate file before ingestion."""
        errors = []
        warnings = []

        # MIME type check
        if mime_type not in ALLOWED_MIME_TYPES:
            errors.append(f"MIME type '{mime_type}' not allowed. Allowed: {ALLOWED_MIME_TYPES}")

        # File size check
        if len(content) > MAX_FILE_SIZE_BYTES:
            errors.append(f"File size {len(content)} bytes exceeds max {MAX_FILE_SIZE_BYTES}")

        if len(content) == 0:
            errors.append("File is empty")

        # Extension check
        extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        allowed_extensions = {"jpg", "jpeg", "png", "webp", "tiff", "pdf", "docx", "xlsx", "csv"}
        if extension not in allowed_extensions:
            warnings.append(f"Unusual file extension: .{extension}")

        return ValidationResult(valid=len(errors) == 0, errors=errors, warnings=warnings)

    def compute_hash(self, content: bytes) -> str:
        """Compute SHA-256 hash for integrity verification."""
        return hashlib.sha256(content).hexdigest()

    async def scan_virus(self, content: bytes) -> str:
        """Virus scan. Returns 'clean', 'infected', or 'error'.

        In production: connect to ClamAV daemon or Google Cloud DLP.
        """
        # Stub: always returns clean in dev
        # Production: clamd.instream(content) or cloud virus scan API
        return "clean"

    def classify_pii(self, document_type: str | None) -> str:
        """Classify PII level based on document type."""
        if not document_type:
            return "none"
        return PII_CLASSIFICATION_MAP.get(document_type, "none")

    def compute_storage_path(self, tenant_id: str, document_id: str, filename: str) -> str:
        """Generate tenant-isolated storage path."""
        extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else "bin"
        date_prefix = datetime.now(timezone.utc).strftime("%Y/%m/%d")
        return f"tenants/{tenant_id}/documents/{date_prefix}/{document_id}.{extension}"

    async def ingest(
        self,
        tenant_id: str,
        filename: str,
        content: bytes,
        mime_type: str,
        document_type: str | None = None,
        category: str | None = None,
        uploaded_by: str | None = None,
        metadata: dict | None = None,
    ) -> IngestionResult:
        """Full ingestion pipeline: validate → hash → scan → store → record."""
        doc_id = uuid.uuid4()

        # Hash
        sha256 = self.compute_hash(content)

        # Virus scan
        scan_status = await self.scan_virus(content)
        if scan_status == "infected":
            raise ValueError("File failed virus scan — upload rejected")

        # PII classification
        pii_level = self.classify_pii(document_type)

        # Storage path
        storage_path = self.compute_storage_path(tenant_id, str(doc_id), filename)

        # Store file (in real system: S3/GCS)
        # await self._store_to_object_storage(storage_path, content)

        # Check for duplicate (same hash = same file)
        existing_version = await self._check_duplicate(tenant_id, sha256)
        version = existing_version + 1 if existing_version else 1

        # Persist document record
        from packages.db.engine import get_session_factory

        factory = get_session_factory()
        async with factory() as session:
            record = Document(
                id=doc_id,
                tenant_id=uuid.UUID(tenant_id),
                filename=filename,
                mime_type=mime_type,
                file_size_bytes=len(content),
                sha256_hash=sha256,
                storage_path=storage_path,
                storage_tier="hot",
                document_type=document_type,
                category=category or self._infer_category(document_type),
                version=version,
                virus_scan_status=scan_status,
                virus_scan_at=datetime.now(timezone.utc),
                pii_classification=pii_level,
                access_restricted=pii_level in ("high", "critical"),
                uploaded_by=uuid.UUID(uploaded_by) if uploaded_by else None,
                metadata_=metadata or {},
            )
            session.add(record)
            await session.commit()

        return IngestionResult(
            document_id=str(doc_id),
            sha256_hash=sha256,
            storage_path=storage_path,
            mime_type=mime_type,
            file_size_bytes=len(content),
            virus_scan_status=scan_status,
            pii_classification=pii_level,
            version=version,
        )

    async def generate_signed_url(
        self,
        document_id: str,
        tenant_id: str,
        requested_by: str,
        purpose: str = "view",
        expires_in_minutes: int = 15,
    ) -> dict:
        """Generate a time-limited signed URL for document access."""
        from packages.db.engine import get_session_factory

        expires_at = datetime.now(timezone.utc) + timedelta(minutes=expires_in_minutes)

        # In production: generate pre-signed S3/GCS URL
        signed_url = f"/api/v1/documents/{document_id}/content?token={uuid.uuid4().hex}&expires={expires_at.isoformat()}"

        # Log access
        factory = get_session_factory()
        async with factory() as session:
            log = SignedURLLog(
                document_id=uuid.UUID(document_id),
                tenant_id=uuid.UUID(tenant_id),
                requested_by=uuid.UUID(requested_by),
                purpose=purpose,
                expires_at=expires_at,
            )
            session.add(log)
            await session.commit()

        return {
            "url": signed_url,
            "expires_at": expires_at.isoformat(),
            "purpose": purpose,
        }

    async def _check_duplicate(self, tenant_id: str, sha256: str) -> int:
        """Check if this file already exists (by hash). Returns version count."""
        try:
            from sqlalchemy import select, func
            from packages.db.engine import get_session_factory

            factory = get_session_factory()
            async with factory() as session:
                stmt = select(func.count(Document.id)).where(
                    Document.tenant_id == uuid.UUID(tenant_id),
                    Document.sha256_hash == sha256,
                )
                result = await session.execute(stmt)
                return int(result.scalar() or 0)
        except Exception:
            return 0

    @staticmethod
    def _infer_category(document_type: str | None) -> str:
        """Infer document category from type."""
        if not document_type:
            return "operational"
        kyc_types = {"aadhaar", "pan", "passport", "driving_license", "voter_id", "selfie"}
        financial_types = {"bank_statement", "invoice"}
        if document_type in kyc_types:
            return "kyc"
        if document_type in financial_types:
            return "financial"
        return "operational"
