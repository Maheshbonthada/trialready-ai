"""The one genuinely agentic step in the pipeline: given OCR'd text from an unknown
binder document, decide what regulatory document type it is, extract the fields the
rules engine needs, and — critically — self-assess confidence and defer to a human
when unsure rather than guess.

This is deliberately scoped narrow: one LLM call, one structured output, no
open-ended tool loop. A classification agent that free-associates across multiple
tool calls is harder to audit and not needed for this task — matching the agent's
autonomy to the task, not maximizing it, is itself the design decision (see
docs/architecture.md).
"""

from __future__ import annotations

import json
from datetime import date
from typing import Protocol

from pydantic import BaseModel, Field
from semantic_kernel.connectors.ai.open_ai import (
    AzureChatCompletion,
    AzureChatPromptExecutionSettings,
    OpenAIChatCompletion,
    OpenAIChatPromptExecutionSettings,
)
from semantic_kernel.contents import ChatHistory

from trialready_api.services.document_types import DocumentTypeSpec

_SYSTEM_PROMPT = """You are a clinical trial regulatory document classifier.

You will be given the OCR'd text of one uploaded file and a list of candidate
document types from a site regulatory binder checklist. Decide which candidate
type (if any) the document is, and extract the requested fields.

Rules:
- If the document doesn't clearly match any candidate, or required fields (like a
  date) are illegible or ambiguous, set confidence low (below 0.5). Do not guess.
- Dates must be ISO 8601 (YYYY-MM-DD). If a date is not present in the text, leave
  it null — never infer a date that is not written in the document.
- confidence is your calibrated probability that document_type_id is correct AND
  the extracted dates are correct, in the range 0.0-1.0.

Respond with ONLY a single JSON object, no prose, no markdown fences, matching
exactly this shape:
{
  "document_type_id": string or null,
  "confidence": number between 0.0 and 1.0,
  "effective_date": "YYYY-MM-DD" or null,
  "expiry_date": "YYYY-MM-DD" or null,
  "signer_name": string or null,
  "signed_date": "YYYY-MM-DD" or null,
  "version_label": string or null,
  "rationale": "one sentence explaining the decision"
}
"""


class ClassificationResult(BaseModel):
    document_type_id: str | None = Field(description="Best-matching candidate id, or null")
    confidence: float = Field(ge=0.0, le=1.0)
    effective_date: date | None = None
    expiry_date: date | None = None
    signer_name: str | None = None
    signed_date: date | None = None
    version_label: str | None = None
    rationale: str = Field(description="One sentence explaining the decision, stored in the audit log")


class DocumentClassifier(Protocol):
    async def classify(
        self, ocr_text: str, kv_pairs: dict[str, str], candidate_types: list[DocumentTypeSpec]
    ) -> ClassificationResult: ...


def _parse_or_fallback(raw: str) -> ClassificationResult:
    """JSON mode guarantees syntactically valid JSON, not schema-conformant JSON —
    a model can still emit an extra field, a wrong type, or (rarely) nothing
    parseable at all. Never let that crash the ingestion pipeline or, worse,
    raise an exception that some caller might swallow into a false "accepted."
    A parse failure always resolves to confidence 0.0, which the confidence
    gate (see services/document_ingestion.py) routes to human review — the same
    safe default as a low-confidence-but-valid response.
    """
    try:
        return ClassificationResult.model_validate_json(raw)
    except Exception as exc:  # noqa: BLE001 — deliberately broad: any parse failure is the same safe outcome
        return ClassificationResult(
            document_type_id=None,
            confidence=0.0,
            rationale=f"Model response was not valid structured output ({type(exc).__name__}); needs human review.",
        )


def _build_history(
    ocr_text: str, kv_pairs: dict[str, str], candidate_types: list[DocumentTypeSpec]
) -> ChatHistory:
    candidates_desc = "\n".join(f"- id={c.id!r}: {c.name} (category: {c.category})" for c in candidate_types)
    history = ChatHistory(system_message=_SYSTEM_PROMPT)
    history.add_user_message(
        "Candidate document types:\n"
        f"{candidates_desc}\n\n"
        f"Extracted key-value pairs:\n{json.dumps(kv_pairs, indent=2)}\n\n"
        f"OCR text (truncated to 8000 chars):\n{ocr_text[:8000]}"
    )
    return history


class AzureOpenAIDocumentClassifier:
    """Production path. Auth is managed identity via `token_endpoint` — no API
    key ever lives in config or environment variables. See
    infra/bicep/modules/openai.bicep, which sets `disableLocalAuth: true` on
    the account so a key-based fallback isn't even possible.
    """

    def __init__(self, endpoint: str, deployment: str, api_version: str) -> None:
        self._service = AzureChatCompletion(
            deployment_name=deployment,
            endpoint=endpoint,
            api_version=api_version,
            ad_token_provider=_azure_ad_token_provider,
        )

    async def classify(
        self, ocr_text: str, kv_pairs: dict[str, str], candidate_types: list[DocumentTypeSpec]
    ) -> ClassificationResult:
        history = _build_history(ocr_text, kv_pairs, candidate_types)
        settings = AzureChatPromptExecutionSettings(
            response_format={"type": "json_object"}, temperature=0.0, max_tokens=800
        )
        response = await self._service.get_chat_message_content(chat_history=history, settings=settings)
        return _parse_or_fallback(str(response))


def _azure_ad_token_provider() -> str:
    from azure.identity import DefaultAzureCredential

    # Cognitive Services' fixed scope for AAD-authenticated data-plane calls.
    return DefaultAzureCredential().get_token("https://cognitiveservices.azure.com/.default").token


class OpenAIDocumentClassifier:
    """Pre-Azure path: talks to api.openai.com directly with an API key. Same
    prompt, same output contract, same confidence gate downstream — swapping
    this for `AzureOpenAIDocumentClassifier` at deploy time (via
    `Settings.ai_provider`) changes nothing else in the system.
    """

    def __init__(self, api_key: str, model: str) -> None:
        self._service = OpenAIChatCompletion(ai_model_id=model, api_key=api_key)

    async def classify(
        self, ocr_text: str, kv_pairs: dict[str, str], candidate_types: list[DocumentTypeSpec]
    ) -> ClassificationResult:
        history = _build_history(ocr_text, kv_pairs, candidate_types)
        settings = OpenAIChatPromptExecutionSettings(
            response_format={"type": "json_object"}, temperature=0.0, max_tokens=800
        )
        response = await self._service.get_chat_message_content(chat_history=history, settings=settings)
        return _parse_or_fallback(str(response))


class FakeDocumentClassifier:
    """Test double. Returns a queued canned result per call, or a default."""

    def __init__(self, results: list[ClassificationResult] | None = None) -> None:
        self._results = list(results or [])
        self._default = ClassificationResult(
            document_type_id=None, confidence=0.0, rationale="fake classifier default"
        )

    async def classify(
        self, ocr_text: str, kv_pairs: dict[str, str], candidate_types: list[DocumentTypeSpec]
    ) -> ClassificationResult:
        return self._results.pop(0) if self._results else self._default
