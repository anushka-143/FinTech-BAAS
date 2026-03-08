"""AI Runtime Governor — governance layer for all AI operations.

Controls:
  - Prompt registry and versioning
  - Tool registry and authorization
  - Confidence thresholds per task type
  - Human-review thresholds
  - Token/cost accounting
  - Fallback behavior
  - Output schema validation
  - Model routing decisions
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any


class AIModel(StrEnum):
    GEMINI_25_PRO = "gemini-2.5-pro"
    GEMINI_25_FLASH = "gemini-2.5-flash"
    GEMINI_EMBEDDING = "gemini-embedding-001"


class CostTier(StrEnum):
    FREE = "free"           # Deterministic rules
    LOW = "low"             # Embedding only
    MEDIUM = "medium"       # Flash model
    HIGH = "high"           # Pro model
    CRITICAL = "critical"   # Pro + tool-calling loop


@dataclass
class PromptTemplate:
    """Registered prompt template with version tracking."""
    name: str
    version: str
    template: str
    system_instruction: str
    task_type: str
    max_tokens: int = 4096
    temperature: float = 0.2
    required_tools: list[str] = field(default_factory=list)
    output_schema: dict | None = None

    @property
    def prompt_hash(self) -> str:
        return hashlib.sha256(
            f"{self.name}:{self.version}:{self.template}".encode()
        ).hexdigest()[:16]


@dataclass
class ToolDeclaration:
    """Registered tool that AI agents can invoke."""
    name: str
    description: str
    parameters_schema: dict
    requires_approval: bool = False
    max_calls_per_session: int = 10
    allowed_task_types: list[str] = field(default_factory=list)


@dataclass
class AIInvocationLog:
    """Audit record of an AI invocation."""
    invocation_id: str
    task_type: str
    model: str
    cost_tier: str
    prompt_hash: str
    input_tokens: int
    output_tokens: int
    latency_ms: float
    tools_called: list[str]
    confidence: float
    required_human_review: bool
    tenant_id: str
    timestamp: datetime


# ─── Confidence thresholds per task type ───

CONFIDENCE_THRESHOLDS = {
    "kyc_review": {"auto_approve": 0.95, "human_review": 0.70, "reject": 0.40},
    "payout_triage": {"auto_approve": 0.90, "human_review": 0.65, "reject": 0.30},
    "recon_analysis": {"auto_approve": 0.85, "human_review": 0.60, "reject": 0.30},
    "risk_explanation": {"auto_approve": 0.90, "human_review": 0.70, "reject": 0.40},
    "ops_copilot": {"auto_approve": 0.80, "human_review": 0.50, "reject": 0.20},
    "developer_copilot": {"auto_approve": 0.80, "human_review": 0.50, "reject": 0.20},
    "compliance_query": {"auto_approve": 0.95, "human_review": 0.75, "reject": 0.50},
}

# ─── Token cost estimates (per 1K tokens, USD) ───

TOKEN_COSTS = {
    AIModel.GEMINI_25_PRO: {"input": 0.00125, "output": 0.005},
    AIModel.GEMINI_25_FLASH: {"input": 0.000075, "output": 0.0003},
    AIModel.GEMINI_EMBEDDING: {"input": 0.00001, "output": 0.0},
}


# ─── Registered tools ───

TOOL_REGISTRY: dict[str, ToolDeclaration] = {
    "search_knowledge_base": ToolDeclaration(
        name="search_knowledge_base",
        description="Search the RAG knowledge base for regulatory docs, past cases, policies",
        parameters_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "source_types": {
                    "type": "array", "items": {"type": "string"},
                    "description": "Filter: regulation, investigation, policy, sanctions",
                },
                "top_k": {"type": "integer", "default": 5},
            },
            "required": ["query"],
        },
        allowed_task_types=["ops_copilot", "compliance_query", "kyc_review", "risk_explanation"],
    ),
    "query_database": ToolDeclaration(
        name="query_database",
        description="Query live database for tenant-specific data (ledger, payouts, KYC)",
        parameters_schema={
            "type": "object",
            "properties": {
                "table": {"type": "string", "description": "Table name"},
                "filters": {"type": "object", "description": "Column filters"},
                "limit": {"type": "integer", "default": 10},
            },
            "required": ["table"],
        },
        requires_approval=False,
        allowed_task_types=["payout_triage", "recon_analysis", "risk_explanation"],
    ),
    "check_sanctions": ToolDeclaration(
        name="check_sanctions",
        description="Screen a name against UAPA/MHA/OFAC/FATF sanctions lists",
        parameters_schema={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Name to screen"},
            },
            "required": ["name"],
        },
        allowed_task_types=["kyc_review", "risk_explanation", "compliance_query"],
    ),
    "cross_reference_kyc": ToolDeclaration(
        name="cross_reference_kyc",
        description="Cross-reference multiple KYC documents for consistency",
        parameters_schema={
            "type": "object",
            "properties": {
                "case_id": {"type": "string", "description": "KYC case ID"},
            },
            "required": ["case_id"],
        },
        allowed_task_types=["kyc_review"],
    ),
}


class AIRuntimeGovernor:
    """Central governance for all AI operations.

    Responsibilities:
      1. Validate tool access per task type
      2. Enforce confidence thresholds
      3. Track token usage and costs
      4. Determine if human review required
      5. Log every invocation for audit
    """

    def __init__(self):
        self._invocation_log: list[AIInvocationLog] = []

    def get_tools_for_task(self, task_type: str) -> list[ToolDeclaration]:
        """Return tools authorized for this task type."""
        return [
            tool for tool in TOOL_REGISTRY.values()
            if not tool.allowed_task_types or task_type in tool.allowed_task_types
        ]

    def get_confidence_threshold(self, task_type: str) -> dict[str, float]:
        """Return confidence thresholds for a task type."""
        return CONFIDENCE_THRESHOLDS.get(task_type, {
            "auto_approve": 0.90,
            "human_review": 0.60,
            "reject": 0.30,
        })

    def evaluate_confidence(self, task_type: str, confidence: float) -> str:
        """Determine action based on confidence score.

        Returns: "auto_approve" | "human_review" | "reject"
        """
        thresholds = self.get_confidence_threshold(task_type)
        if confidence >= thresholds["auto_approve"]:
            return "auto_approve"
        elif confidence >= thresholds["human_review"]:
            return "human_review"
        return "reject"

    def estimate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """Estimate cost in USD for an AI invocation."""
        costs = TOKEN_COSTS.get(model, TOKEN_COSTS[AIModel.GEMINI_25_PRO])
        return (input_tokens / 1000 * costs["input"]) + (output_tokens / 1000 * costs["output"])

    def select_model(self, task_type: str, context_size: int) -> str:
        """Select optimal model based on task type and context size.

        Cost routing: Flash for simple tasks, Pro for complex.
        """
        # Complex analytical tasks → Pro
        if task_type in ("kyc_review", "compliance_query", "risk_explanation"):
            return AIModel.GEMINI_25_PRO
        # Large context → Pro (better at long-context reasoning)
        if context_size > 10000:
            return AIModel.GEMINI_25_PRO
        # Simple copilot/triage → Flash
        return AIModel.GEMINI_25_FLASH

    def log_invocation(
        self,
        task_type: str,
        model: str,
        cost_tier: str,
        prompt_hash: str,
        input_tokens: int,
        output_tokens: int,
        latency_ms: float,
        tools_called: list[str],
        confidence: float,
        tenant_id: str,
    ) -> AIInvocationLog:
        """Log an AI invocation for audit and cost tracking."""
        log = AIInvocationLog(
            invocation_id=f"AI-{uuid.uuid4().hex[:12].upper()}",
            task_type=task_type,
            model=model,
            cost_tier=cost_tier,
            prompt_hash=prompt_hash,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            tools_called=tools_called,
            confidence=confidence,
            required_human_review=self.evaluate_confidence(task_type, confidence) == "human_review",
            tenant_id=tenant_id,
            timestamp=datetime.now(timezone.utc),
        )
        self._invocation_log.append(log)
        return log

    def get_cost_summary(self, tenant_id: str | None = None) -> dict:
        """Get token usage and cost summary."""
        logs = self._invocation_log
        if tenant_id:
            logs = [l for l in logs if l.tenant_id == tenant_id]

        total_input = sum(l.input_tokens for l in logs)
        total_output = sum(l.output_tokens for l in logs)
        total_cost = sum(
            self.estimate_cost(l.model, l.input_tokens, l.output_tokens)
            for l in logs
        )

        return {
            "total_invocations": len(logs),
            "total_input_tokens": total_input,
            "total_output_tokens": total_output,
            "estimated_cost_usd": round(total_cost, 4),
            "by_task_type": {
                tt: len([l for l in logs if l.task_type == tt])
                for tt in set(l.task_type for l in logs)
            },
        }


# Singleton
_governor: AIRuntimeGovernor | None = None


def get_governor() -> AIRuntimeGovernor:
    global _governor
    if _governor is None:
        _governor = AIRuntimeGovernor()
    return _governor
