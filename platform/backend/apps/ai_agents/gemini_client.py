"""Gemini client — production-grade wrapper using Vertex AI.

Authentication priority:
  1. Vertex AI (GOOGLE_APPLICATION_CREDENTIALS + GCP_PROJECT_ID) — production
  2. Direct Gemini API (GOOGLE_API_KEY) — development fallback

The google-genai SDK supports both modes with the same API:
  - Vertex AI: genai.Client(vertexai=True, project=..., location=...)
  - Direct:    genai.Client(api_key=...)

Features:
  - Function calling (tool-use) for AI orchestrator
  - Structured JSON output via response_schema
  - Automatic PII masking before sending to LLM
  - Token usage tracking for cost monitoring
  - Prompt hashing for audit trail
"""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass, field
from typing import Any

from packages.core.settings import get_settings


@dataclass
class GeminiResponse:
    """Structured response from Gemini."""
    text: str = ""
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    usage: dict[str, int] = field(default_factory=dict)
    model: str = ""
    prompt_hash: str = ""
    latency_ms: float = 0.0
    finish_reason: str = ""


# PII patterns for masking before sending to external LLM
_PII_PATTERNS = {
    "aadhaar": re.compile(r"\b\d{4}\s?\d{4}\s?\d{4}\b"),
    "pan": re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b"),
    "phone": re.compile(r"\b(?:\+91|0)?[6-9]\d{9}\b"),
    "email": re.compile(r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b"),
    "account_number": re.compile(r"\b\d{9,18}\b"),
}


def mask_pii(text: str) -> str:
    """Mask Indian PII before sending to external LLM.

    Replaces:
    - Aadhaar numbers (12 digits) → [AADHAAR_MASKED]
    - PAN numbers (ABCDE1234F) → [PAN_MASKED]
    - Phone numbers (+91...) → [PHONE_MASKED]
    - Email addresses → [EMAIL_MASKED]
    - Account numbers (9-18 digits) → [ACCOUNT_MASKED]
    """
    for pii_type, pattern in _PII_PATTERNS.items():
        text = pattern.sub(f"[{pii_type.upper()}_MASKED]", text)
    return text


class GeminiClient:
    """Production Gemini client via Vertex AI or direct API.

    Initialization:
      - If GOOGLE_APPLICATION_CREDENTIALS + GCP_PROJECT_ID are set:
        Uses Vertex AI (vertexai=True) with service account auth.
      - Else if GOOGLE_API_KEY is set:
        Uses direct Gemini API with API key.
      - Else: raises RuntimeError.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._api_key = settings.google_api_key
        self._credentials_path = settings.google_application_credentials
        self._project_id = settings.gcp_project_id
        self._location = settings.gcp_location
        self._model_name = settings.gemini_model_name
        self._client = None
        self._using_vertex = False

    def _get_client(self):
        """Lazy-init the google-genai client."""
        if self._client is not None:
            return self._client

        try:
            from google import genai
        except ImportError:
            raise RuntimeError(
                "google-genai is not installed. "
                "Install with: pip install 'google-genai>=1.14.0'"
            )

        # Priority 1: Vertex AI with service account
        if self._credentials_path and self._project_id:
            # Set GOOGLE_APPLICATION_CREDENTIALS env var for ADC
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = self._credentials_path
            self._client = genai.Client(
                vertexai=True,
                project=self._project_id,
                location=self._location,
            )
            self._using_vertex = True

        # Priority 2: Direct Gemini API key
        elif self._api_key:
            self._client = genai.Client(api_key=self._api_key)
            self._using_vertex = False

        else:
            raise RuntimeError(
                "No Gemini credentials configured. Set either:\n"
                "  1. GOOGLE_APPLICATION_CREDENTIALS + GCP_PROJECT_ID (Vertex AI)\n"
                "  2. GOOGLE_API_KEY (direct Gemini API)"
            )

        return self._client

    async def generate(
        self,
        *,
        prompt: str,
        system_instruction: str | None = None,
        tools: list[dict] | None = None,
        response_schema: dict | None = None,
        temperature: float = 0.2,
        max_tokens: int = 4096,
        mask_pii_in_prompt: bool = True,
    ) -> GeminiResponse:
        """Generate a response from Gemini via Vertex AI.

        Args:
            prompt: The user prompt (will be PII-masked if enabled)
            system_instruction: System prompt for the model
            tools: Function declarations for tool-use
            response_schema: JSON schema for structured output
            temperature: Model temperature (0.0-2.0)
            max_tokens: Maximum output tokens
            mask_pii_in_prompt: Whether to mask PII before sending
        """
        import time
        start = time.monotonic()

        if mask_pii_in_prompt:
            prompt = mask_pii(prompt)

        prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()[:16]

        client = self._get_client()

        from google.genai import types

        config_kwargs: dict[str, Any] = {
            "temperature": temperature,
            "max_output_tokens": max_tokens,
        }

        if system_instruction:
            config_kwargs["system_instruction"] = system_instruction

        if response_schema:
            config_kwargs["response_mime_type"] = "application/json"
            config_kwargs["response_schema"] = response_schema

        if tools:
            gemini_tools = []
            for tool in tools:
                func = tool.get("function", {})
                gemini_tools.append(types.FunctionDeclaration(
                    name=func.get("name", ""),
                    description=func.get("description", ""),
                    parameters=func.get("parameters", {}),
                ))
            config_kwargs["tools"] = [types.Tool(function_declarations=gemini_tools)]

        config = types.GenerateContentConfig(**config_kwargs)

        response = await client.aio.models.generate_content(
            model=self._model_name,
            contents=prompt,
            config=config,
        )

        elapsed_ms = (time.monotonic() - start) * 1000

        # Parse response
        text = ""
        tool_calls = []
        finish_reason = ""

        if response.candidates:
            candidate = response.candidates[0]
            finish_reason = str(getattr(candidate, "finish_reason", ""))

            for part in candidate.content.parts:
                if hasattr(part, "text") and part.text:
                    text += part.text
                if hasattr(part, "function_call") and part.function_call:
                    tool_calls.append({
                        "name": part.function_call.name,
                        "args": dict(part.function_call.args) if part.function_call.args else {},
                    })

        usage = {}
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            usage = {
                "prompt_tokens": getattr(response.usage_metadata, "prompt_token_count", 0),
                "output_tokens": getattr(response.usage_metadata, "candidates_token_count", 0),
                "total_tokens": getattr(response.usage_metadata, "total_token_count", 0),
            }

        return GeminiResponse(
            text=text,
            tool_calls=tool_calls,
            usage=usage,
            model=self._model_name,
            prompt_hash=prompt_hash,
            latency_ms=elapsed_ms,
            finish_reason=finish_reason,
        )

    @property
    def is_vertex_ai(self) -> bool:
        """Whether this client is using Vertex AI or direct API."""
        self._get_client()  # Ensure initialized
        return self._using_vertex


# Singleton
_gemini_client: GeminiClient | None = None


def get_gemini_client() -> GeminiClient:
    """Get the singleton Gemini client."""
    global _gemini_client
    if _gemini_client is None:
        _gemini_client = GeminiClient()
    return _gemini_client
