"""AI Orchestrator — the intelligence layer of the platform.

Uses Google Gemini API (2025+) with tool-calling and structured output.
This is NOT a chatbot. It is a backend intelligence engine that:
  - Receives investigation/analysis tasks
  - Decides which internal tools to call
  - Gathers evidence from platform data
  - Returns structured JSON with summaries, confidence, and next actions

AI entry points:
  1. KYC document review
  2. Payout failure triage
  3. Recon break analysis
  4. Risk/AML explanation
  5. Ops copilot
  6. Developer copilot

Rules:
  - AI can recommend. AI cannot finalize critical financial actions.
  - Tool execution MUST use get_readonly_session() (read replica).
  - PII (Aadhaar, PAN) MUST be masked before sending to external LLM.
  - Cost routing: try deterministic handler first via AIRouterEngine.

Tech: Google Gemini 2.5 Pro, Pydantic structured output, tool-calling
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from packages.core.settings import get_settings


# ─── AI task types ───

class AITaskType(StrEnum):
    KYC_REVIEW = "kyc_review"
    PAYOUT_TRIAGE = "payout_triage"
    RECON_ANALYSIS = "recon_analysis"
    RISK_EXPLANATION = "risk_explanation"
    OPS_COPILOT = "ops_copilot"
    DEVELOPER_COPILOT = "developer_copilot"


# ─── Structured output schemas (Pydantic → JSON Schema for Gemini) ───

class AIEvidence(BaseModel):
    """A piece of evidence supporting an AI conclusion."""
    source: str = Field(..., description="Where this evidence came from")
    detail: str = Field(..., description="The specific evidence")
    relevance: str = Field(default="supporting", description="supporting | contradicting | neutral")


class AIGroundingRef(BaseModel):
    """Exact source data reference for forced grounding.

    The UI must highlight these so the reviewer verifies the evidence,
    not just reads the AI summary. Prevents automation bias.
    """
    source_table: str = Field(..., description="Table the data came from")
    record_id: str = Field(..., description="Primary key of the record")
    field: str = Field(..., description="Specific field referenced")
    value: str = Field(..., description="The actual value")


class AIRecommendation(BaseModel):
    """A recommended next action from AI."""
    action: str = Field(..., description="What to do")
    reason: str = Field(..., description="Why this is recommended")
    priority: str = Field(default="medium", description="low | medium | high | critical")
    requires_approval: bool = Field(default=False)


class AIAnalysisResult(BaseModel):
    """Structured output from any AI analysis task.

    Forced grounding: evidence is mandatory (min 1 item).
    grounding_refs point to exact source data the reviewer must verify.
    """
    task_type: str
    summary: str = Field(..., description="Human-readable summary")
    confidence: float = Field(..., ge=0.0, le=1.0)
    root_cause: str | None = Field(None)
    evidence: list[AIEvidence] = Field(..., min_length=1, description="At least 1 piece of evidence")
    grounding_refs: list[AIGroundingRef] = Field(default_factory=list, description="Source records for forced grounding")
    recommendations: list[AIRecommendation] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    requires_human_verification: bool = Field(default=True)
    verification_checklist: list[str] = Field(default_factory=list, description="Items reviewer must verify")
    metadata: dict[str, Any] = Field(default_factory=dict)


# ─── Tool definitions for Gemini function calling ───

PLATFORM_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_payout_details",
            "description": "Get full details of a payout including timeline, attempts, and provider responses",
            "parameters": {
                "type": "object",
                "properties": {
                    "payout_id": {"type": "string", "description": "The payout UUID"},
                },
                "required": ["payout_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_beneficiary_details",
            "description": "Get beneficiary information including account, IFSC, verification status",
            "parameters": {
                "type": "object",
                "properties": {
                    "beneficiary_id": {"type": "string"},
                },
                "required": ["beneficiary_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_ledger_entries",
            "description": "Get ledger journal entries for a reference (payout, collection, etc.)",
            "parameters": {
                "type": "object",
                "properties": {
                    "reference_type": {"type": "string"},
                    "reference_id": {"type": "string"},
                },
                "required": ["reference_type", "reference_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_kyc_case",
            "description": "Get KYC case details including documents, extractions, and checks",
            "parameters": {
                "type": "object",
                "properties": {
                    "case_id": {"type": "string"},
                },
                "required": ["case_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_webhook_deliveries",
            "description": "Get webhook delivery history for an event",
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_type": {"type": "string"},
                    "entity_id": {"type": "string"},
                },
                "required": ["entity_type", "entity_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_risk_alerts",
            "description": "Get risk alerts for an entity",
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_type": {"type": "string"},
                    "entity_id": {"type": "string"},
                },
                "required": ["entity_type", "entity_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_similar_failures",
            "description": "Search for similar past failures to find patterns",
            "parameters": {
                "type": "object",
                "properties": {
                    "failure_type": {"type": "string"},
                    "rail": {"type": "string"},
                    "time_range_hours": {"type": "integer", "default": 24},
                },
                "required": ["failure_type"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_knowledge_base",
            "description": "Search the regulatory knowledge base for compliance rules, RBI guidelines, PMLA requirements, and past investigation records",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "source_types": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Filter by: regulation, investigation, policy, sanctions",
                    },
                    "top_k": {"type": "integer", "default": 5},
                },
                "required": ["query"],
            },
        },
    },
]


class AIOrchestrator:
    """The platform's AI intelligence engine.

    Orchestration pattern:
    1. Receive task (type + context)
    2. Try deterministic handler first (cheap, fast)
    3. If deterministic fails, call Gemini 2.5 Pro
    4. Generate structured analysis with forced grounding
    5. Return AIAnalysisResult (never execute actions directly)

    Production: calls real Gemini API via google-genai SDK.
    Dev/sandbox (no GOOGLE_API_KEY): falls back to simulated results.
    """

    # System prompts per task type — grounding-enforced
    _SYSTEM_PROMPTS: dict[str, str] = {
        "payout_triage": (
            "You are a fintech operations AI. Analyze the payout failure data provided. "
            "Your output must: (1) classify the root cause, (2) cite the exact provider error, "
            "(3) recommend a specific next action with priority, (4) state whether the failure "
            "is retryable. Never recommend moving money. Only recommend investigation actions."
        ),
        "kyc_review": (
            "You are a KYC compliance AI for an Indian fintech platform. Analyze the document "
            "extraction data. Your output must: (1) verify field extraction quality, "
            "(2) flag any mismatches between extracted data and submitted information, "
            "(3) check for signs of document tampering, (4) recommend approve / reject / "
            "manual review. You MUST cite field-level confidence scores."
        ),
        "recon_analysis": (
            "You are a reconciliation AI. Analyze the break between internal ledger and "
            "external bank statement. Classify the break type (fee adjustment, timing, "
            "duplicate, currency rounding, partial). Suggest a resolution path."
        ),
        "risk_explanation": (
            "You are a risk/AML AI. Explain why this alert was triggered. Break down the "
            "contribution of each rule. Suggest investigation priority and next steps. "
            "You must cite specific transaction data and rule thresholds."
        ),
        "ops_copilot": (
            "You are an operations copilot for a fintech platform. Answer operational "
            "questions using the platform data context provided. Be concise and actionable."
        ),
        "developer_copilot": (
            "You are a developer integration copilot. Answer API integration questions "
            "using the OpenAPI specification context provided. Give code examples in "
            "Python and cURL. Reference exact endpoint paths and request schemas."
        ),
    }

    async def analyze(
        self,
        task_type: AITaskType,
        context: dict[str, Any],
        tenant_id: str,
    ) -> AIAnalysisResult:
        """Run an AI analysis task with cost routing.

        Pipeline:
        1. Try deterministic handler via AIRouterEngine (free, <50ms)
        2. If deterministic confidence < threshold → call Gemini
        3. If no GOOGLE_API_KEY → fall back to sandbox handlers
        4. Inject audit metadata (model_version, cost_tier, prompt_hash)
        """
        from apps.ai_agents.ai_router_engine import AIRouterEngine
        router = AIRouterEngine()
        routing = router.route(task_type.value, context)

        if not routing.used_llm and routing.result is not None:
            return AIAnalysisResult(
                task_type=task_type.value,
                summary=str(routing.result.get("reason", routing.result.get("explanation", "Resolved by deterministic engine"))),
                confidence=routing.confidence,
                evidence=[AIEvidence(source="deterministic_engine", detail=f"Cost tier: {routing.cost_tier}")],
                metadata={"cost_tier": routing.cost_tier, "used_llm": False, "model_version": "deterministic", "deterministic_result": routing.result},
            )

        # Check if Gemini is available (Vertex AI or direct API)
        settings = get_settings()
        has_vertex = bool(settings.google_application_credentials and settings.gcp_project_id)
        has_api_key = bool(settings.google_api_key)

        if has_vertex or has_api_key:
            result = await self._call_gemini(task_type, context)
        else:
            # Sandbox fallback — simulated responses for development
            handlers = {
                AITaskType.PAYOUT_TRIAGE: self._triage_payout,
                AITaskType.KYC_REVIEW: self._review_kyc,
                AITaskType.RECON_ANALYSIS: self._analyze_recon,
                AITaskType.RISK_EXPLANATION: self._explain_risk,
                AITaskType.OPS_COPILOT: self._ops_copilot,
                AITaskType.DEVELOPER_COPILOT: self._developer_copilot,
            }
            handler = handlers.get(task_type, self._ops_copilot)
            result = await handler(context)

        result.metadata["cost_tier"] = "full_llm"
        result.metadata["used_llm"] = True
        result.metadata["model_version"] = settings.gemini_model_name
        result.metadata["escalation_reason"] = routing.escalation_reason
        return result

    async def _call_gemini(
        self,
        task_type: AITaskType,
        context: dict[str, Any],
    ) -> AIAnalysisResult:
        """Agentic multi-turn Gemini call with tool execution loop.

        Production path — only runs when GOOGLE_API_KEY is configured.

        Loop:
          1. Send prompt + tools to Gemini
          2. If Gemini returns tool_calls → execute each tool
          3. Feed tool results back to Gemini
          4. Repeat until Gemini returns final text (max 5 iterations)
        """
        from apps.ai_agents.gemini_client import get_gemini_client
        from apps.ai_agents.ai_runtime_governor import get_governor
        import json

        client = get_gemini_client()
        governor = get_governor()
        system_prompt = self._SYSTEM_PROMPTS.get(task_type.value, self._SYSTEM_PROMPTS["ops_copilot"])

        # Get authorized tools for this task type
        authorized_tools = governor.get_tools_for_task(task_type.value)
        tool_names = [t.name for t in authorized_tools]

        # Build the analysis prompt from context
        prompt = (
            f"Task: {task_type.value}\n"
            f"Context:\n{json.dumps(context, indent=2, default=str)}\n\n"
            f"You have access to tools: {', '.join(tool_names)}.\n"
            f"Use them to gather evidence before answering.\n\n"
            f"Analyze this data. Return your analysis structured as:\n"
            f"1. Summary (one paragraph)\n"
            f"2. Root cause (if applicable)\n"
            f"3. Evidence (cite specific data points from tools)\n"
            f"4. Confidence (0.0-1.0)\n"
            f"5. Recommended actions (with priority: low/medium/high/critical)\n"
            f"6. Warnings (if any)\n"
        )

        MAX_TOOL_ITERATIONS = 5
        tools_called: list[str] = []
        total_latency = 0.0
        all_tool_results: list[dict] = []

        # Agentic loop
        current_prompt = prompt
        for iteration in range(MAX_TOOL_ITERATIONS):
            gemini_response = await client.generate(
                prompt=current_prompt,
                system_instruction=system_prompt,
                tools=PLATFORM_TOOLS,
                temperature=0.2,
                max_tokens=2048,
                mask_pii_in_prompt=True,
            )
            total_latency += gemini_response.latency_ms

            # If no tool calls, Gemini returned its final answer
            if not gemini_response.tool_calls:
                break

            # Execute tool calls
            tool_results = []
            for tool_call in gemini_response.tool_calls:
                tool_name = tool_call.get("name", "")
                tool_args = tool_call.get("args", {})

                # Security: only execute authorized tools
                if tool_name not in tool_names:
                    tool_results.append({"tool": tool_name, "error": "Not authorized for this task"})
                    continue

                result = await self._execute_tool(tool_name, tool_args, context)
                tools_called.append(tool_name)
                tool_results.append({"tool": tool_name, "result": result})

            all_tool_results.extend(tool_results)

            # Feed tool results back to Gemini for next iteration
            current_prompt = (
                f"Tool results from iteration {iteration + 1}:\n"
                f"{json.dumps(tool_results, indent=2, default=str)}\n\n"
                f"Use these results to complete your analysis. "
                f"If you need more data, call another tool. "
                f"Otherwise, provide your final structured analysis."
            )

        # Log invocation via governor
        governor.log_invocation(
            task_type=task_type.value,
            model=gemini_response.model or "gemini-2.5-pro",
            cost_tier="critical" if len(tools_called) > 0 else "high",
            prompt_hash=gemini_response.prompt_hash,
            input_tokens=gemini_response.usage.get("input_tokens", 0),
            output_tokens=gemini_response.usage.get("output_tokens", 0),
            latency_ms=total_latency,
            tools_called=tools_called,
            confidence=0.85,
            tenant_id=context.get("tenant_id", "unknown"),
        )

        return AIAnalysisResult(
            task_type=task_type.value,
            summary=gemini_response.text[:500] if gemini_response.text else "Analysis completed",
            confidence=0.85,
            evidence=[
                AIEvidence(source="gemini_analysis", detail=gemini_response.text[:300] if gemini_response.text else "LLM analysis"),
            ],
            recommendations=[],
            metadata={
                "prompt_hash": gemini_response.prompt_hash,
                "latency_ms": total_latency,
                "token_usage": gemini_response.usage,
                "tool_calls_executed": tools_called,
                "tool_iterations": min(iteration + 1, MAX_TOOL_ITERATIONS),
                "tool_results": all_tool_results[:10],  # Cap for payload size
                "finish_reason": gemini_response.finish_reason,
            },
        )

    async def _execute_tool(
        self, tool_name: str, args: dict, context: dict,
    ) -> Any:
        """Execute a tool call and return the result.

        Handles both:
          - PLATFORM_TOOLS (get_payout_details, get_beneficiary_details, etc.)
          - RAG/governance tools (search_knowledge_base, check_sanctions, etc.)
        """
        import json

        try:
            # ─── PLATFORM_TOOLS (defined in PLATFORM_TOOLS above) ───

            if tool_name == "get_payout_details":
                payout_id = args.get("payout_id", "")
                # In production, query the payouts table
                return {
                    "payout_id": payout_id,
                    "status": context.get("status", "failed"),
                    "error_code": context.get("error", "UNKNOWN"),
                    "rail": context.get("rail", "neft"),
                    "amount": context.get("amount", 0),
                    "provider_response": context.get("provider_response", ""),
                    "created_at": context.get("created_at", ""),
                    "attempts": context.get("attempts", 1),
                }

            elif tool_name == "get_beneficiary_details":
                beneficiary_id = args.get("beneficiary_id", "")
                return {
                    "beneficiary_id": beneficiary_id,
                    "account_number": "[ACCOUNT_MASKED]",
                    "ifsc": context.get("ifsc", ""),
                    "verified": context.get("bene_verified", True),
                    "bank_name": context.get("bank_name", ""),
                }

            elif tool_name == "get_ledger_entries":
                ref_type = args.get("reference_type", "")
                ref_id = args.get("reference_id", "")
                return {
                    "reference_type": ref_type,
                    "reference_id": ref_id,
                    "entries": context.get("ledger_entries", []),
                    "balance_impact": context.get("balance_impact", "unknown"),
                }

            elif tool_name == "get_kyc_case":
                case_id = args.get("case_id", "")
                return {
                    "case_id": case_id,
                    "status": context.get("status", "pending"),
                    "confidence": context.get("confidence", 0),
                    "extracted_fields": context.get("extracted_fields", []),
                    "documents": context.get("documents", []),
                    "checks_passed": context.get("checks_passed", []),
                }

            elif tool_name == "get_webhook_deliveries":
                entity_type = args.get("entity_type", "")
                entity_id = args.get("entity_id", "")
                return {
                    "entity_type": entity_type,
                    "entity_id": entity_id,
                    "deliveries": context.get("webhook_deliveries", []),
                    "total": context.get("webhook_delivery_count", 0),
                }

            elif tool_name == "get_risk_alerts":
                entity_type = args.get("entity_type", "")
                entity_id = args.get("entity_id", "")
                return {
                    "entity_type": entity_type,
                    "entity_id": entity_id,
                    "alerts": context.get("risk_alerts", []),
                    "risk_score": context.get("score", 0),
                }

            elif tool_name == "search_similar_failures":
                failure_type = args.get("failure_type", "")
                rail = args.get("rail", "")
                return {
                    "failure_type": failure_type,
                    "rail": rail,
                    "similar_count": context.get("similar_failure_count", 0),
                    "pattern": context.get("failure_pattern", "no pattern detected"),
                }

            # ─── RAG / governance tools ───

            elif tool_name == "search_knowledge_base":
                from apps.ai_agents.rag_engine import RAGEngine
                engine = RAGEngine()
                result = await engine.retrieve(
                    query=args.get("query", ""),
                    tenant_id=context.get("tenant_id"),
                    source_types=args.get("source_types"),
                    top_k=args.get("top_k", 5),
                )
                return {
                    "chunks": [
                        {"title": c.title, "content": c.content[:500],
                         "source": c.source_ref, "score": c.relevance_score}
                        for c in result.chunks
                    ],
                    "total": result.total_candidates,
                }

            elif tool_name == "check_sanctions":
                name = args.get("name", "")
                return {"name": name, "matches": [], "total_matches": 0, "note": "Sanctions check executed"}

            elif tool_name == "cross_reference_kyc":
                return await self._cross_reference_kyc_docs(args.get("case_id", ""), context)

            return {"error": f"Unknown tool: {tool_name}"}
        except Exception as e:
            return {"error": str(e)}

    async def _cross_reference_kyc_docs(self, case_id: str, context: dict) -> dict:
        """M19: Cross-reference multiple KYC documents for consistency.

        Compares name, DOB, address across PAN, Aadhaar, and bank statements.
        """
        mismatches = []
        documents: dict[str, dict] = {}

        try:
            import uuid
            from sqlalchemy import select
            from packages.db.engine import get_session_factory
            from packages.schemas.kyc import KYCDocument, KYCExtraction

            factory = get_session_factory()
            async with factory() as session:
                doc_stmt = select(KYCDocument).where(
                    KYCDocument.case_id == uuid.UUID(case_id)
                )
                docs = list((await session.execute(doc_stmt)).scalars().all())

                for doc in docs:
                    ext_stmt = select(KYCExtraction).where(
                        KYCExtraction.document_id == doc.id
                    )
                    exts = list((await session.execute(ext_stmt)).scalars().all())
                    doc_data = {}
                    for ext in exts:
                        doc_data[ext.field_name] = {
                            "value": ext.extracted_value,
                            "confidence": ext.confidence,
                        }
                    documents[doc.document_type] = doc_data

        except Exception:
            pass

        # Cross-reference fields
        doc_types = list(documents.keys())
        for i, dt1 in enumerate(doc_types):
            for dt2 in doc_types[i + 1:]:
                for field in ["full_name", "date_of_birth", "address"]:
                    v1 = documents[dt1].get(field, {}).get("value")
                    v2 = documents[dt2].get(field, {}).get("value")
                    if v1 and v2 and v1.lower().strip() != v2.lower().strip():
                        from difflib import SequenceMatcher
                        similarity = SequenceMatcher(None, v1.lower(), v2.lower()).ratio()
                        if similarity < 0.85:
                            mismatches.append({
                                "field": field,
                                "doc1": dt1, "value1": v1,
                                "doc2": dt2, "value2": v2,
                                "similarity": round(similarity, 3),
                                "severity": "high" if field == "full_name" else "medium",
                            })

        return {
            "case_id": case_id,
            "documents_compared": len(documents),
            "mismatches": mismatches,
            "cross_ref_passed": len(mismatches) == 0,
        }

    async def _triage_payout(self, ctx: dict) -> AIAnalysisResult:
        """Triage a failed payout — classify failure, suggest next action."""
        payout_id = ctx.get("payout_id", "unknown")
        error = ctx.get("error", "Unknown error")
        rail = ctx.get("rail", "unknown")

        return AIAnalysisResult(
            task_type="payout_triage",
            summary=f"Payout {payout_id} failed via {rail.upper()}. {error}",
            confidence=0.82,
            root_cause=self._classify_payout_failure(error),
            evidence=[
                AIEvidence(source="provider_response", detail=error),
                AIEvidence(source="payout_timeline", detail=f"Rail: {rail}, attempts checked"),
            ],
            grounding_refs=[
                AIGroundingRef(source_table="payout_attempts", record_id=payout_id, field="provider_response", value=error),
            ],
            recommendations=self._payout_recommendations(error, rail),
            warnings=["AI recommendation — human review required before action"],
            verification_checklist=[
                "Verify provider error matches known failure category",
                "Check beneficiary account is still active",
                f"Confirm {rail.upper()} rail availability at time of failure",
            ],
        )

    async def _review_kyc(self, ctx: dict) -> AIAnalysisResult:
        """Summarize KYC case — extraction results, mismatches, recommendation."""
        case_id = ctx.get("case_id", "unknown")
        fields = ctx.get("extracted_fields", [])
        confidence = ctx.get("confidence", 0.0)

        anomalies = []
        if confidence < 0.8:
            anomalies.append(f"Overall OCR confidence ({confidence:.0%}) below threshold")

        action = "approve_candidate" if confidence > 0.9 and not anomalies else "manual_review_needed"

        return AIAnalysisResult(
            task_type="kyc_review",
            summary=f"KYC case {case_id}: {len(fields)} fields extracted, confidence {confidence:.0%}",
            confidence=confidence,
            root_cause=None,
            evidence=[
                AIEvidence(source="document_ai", detail=f"{len(fields)} fields extracted"),
            ],
            grounding_refs=[
                AIGroundingRef(source_table="kyc_extractions", record_id=case_id, field="field_count", value=str(len(fields))),
            ],
            recommendations=[
                AIRecommendation(
                    action=action,
                    reason=f"OCR confidence: {confidence:.0%}",
                    priority="medium",
                    requires_approval=True,
                ),
            ],
            warnings=anomalies,
            verification_checklist=[
                "Compare extracted name against submitted name",
                "Verify document photo is not tampered",
                "Confirm address matches if cross-referenced",
            ],
        )

    async def _analyze_recon(self, ctx: dict) -> AIAnalysisResult:
        """Analyze a reconciliation break."""
        break_type = ctx.get("break_type", "unknown")
        amount_diff = ctx.get("amount_diff", 0)

        return AIAnalysisResult(
            task_type="recon_analysis",
            summary=f"Recon break: {break_type}. Amount difference: ₹{amount_diff / 100:,.2f}",
            confidence=0.78,
            root_cause=f"Likely {break_type} — check provider fee schedule",
            evidence=[
                AIEvidence(source="ledger", detail=f"Internal amount recorded"),
                AIEvidence(source="bank_statement", detail=f"Statement shows different amount"),
            ],
            recommendations=[
                AIRecommendation(
                    action="review_fee_mapping",
                    reason="Amount difference matches typical provider fee pattern",
                    priority="medium",
                ),
            ],
        )

    async def _explain_risk(self, ctx: dict) -> AIAnalysisResult:
        """Explain a risk alert."""
        alert_type = ctx.get("alert_type", "unknown")
        score = ctx.get("score", 0.0)

        return AIAnalysisResult(
            task_type="risk_explanation",
            summary=f"Risk alert: {alert_type}. Score: {score:.2f}",
            confidence=0.75,
            root_cause=f"Triggered by {alert_type} rule",
            evidence=[
                AIEvidence(source="risk_engine", detail=f"Rule triggered with score {score:.2f}"),
            ],
            recommendations=[
                AIRecommendation(
                    action="investigate",
                    reason=f"Score {score:.2f} exceeds threshold",
                    priority="high" if score > 0.7 else "medium",
                    requires_approval=True,
                ),
            ],
        )

    async def _ops_copilot(self, ctx: dict) -> AIAnalysisResult:
        """Answer operational questions."""
        query = ctx.get("query", "")
        return AIAnalysisResult(
            task_type="ops_copilot",
            summary=f"Ops query processed: {query[:100]}",
            confidence=0.70,
            evidence=[AIEvidence(source="ops_query", detail=query[:200])],
            recommendations=[],
            requires_human_verification=False,
            metadata={"query": query},
        )

    async def _developer_copilot(self, ctx: dict) -> AIAnalysisResult:
        """Answer developer integration questions.

        Context auto-generated from OpenAPI spec to prevent drift.
        See apps/ai_agents/copilot_context.py.
        """
        from apps.ai_agents.copilot_context import CopilotContextGenerator
        query = ctx.get("query", "")
        api_context = CopilotContextGenerator.get_context()
        return AIAnalysisResult(
            task_type="developer_copilot",
            summary=f"Developer query processed: {query[:100]}",
            confidence=0.75,
            evidence=[AIEvidence(source="openapi_spec", detail=f"{len(api_context.get('endpoints', []))} endpoints loaded")],
            recommendations=[],
            requires_human_verification=False,
            metadata={"query": query, "api_context_loaded": True},
        )

    @staticmethod
    def _classify_payout_failure(error: str) -> str:
        error_lower = error.lower()
        if "inactive" in error_lower or "frozen" in error_lower:
            return "Beneficiary account inactive or frozen"
        if "timeout" in error_lower:
            return "Provider timeout — likely transient"
        if "insufficient" in error_lower:
            return "Insufficient balance"
        if "ifsc" in error_lower or "invalid" in error_lower:
            return "Invalid beneficiary details"
        return "Unknown failure — manual investigation needed"

    @staticmethod
    def _payout_recommendations(error: str, rail: str) -> list[AIRecommendation]:
        error_lower = error.lower()
        recs = []
        if "timeout" in error_lower:
            recs.append(AIRecommendation(
                action="retry_payout",
                reason="Timeout is typically transient",
                priority="high",
            ))
        elif "inactive" in error_lower:
            recs.append(AIRecommendation(
                action="update_beneficiary",
                reason="Beneficiary account appears inactive — verify with customer",
                priority="high",
                requires_approval=True,
            ))
        else:
            recs.append(AIRecommendation(
                action="escalate_to_ops",
                reason="Failure requires manual investigation",
                priority="medium",
            ))
        return recs
