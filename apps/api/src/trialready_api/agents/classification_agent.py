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


class AzureOpenAIDocumentClassifier:
    def __init__(self, endpoint: str, deployment: str, api_version: str) -> None:
        # Managed-identity auth (azure-identity's DefaultAzureCredential + a
        # token provider) is wired at construction time in api/deps.py; this class
        # only holds the already-configured Semantic Kernel service.
        self._service = AzureChatCompletion(
            deployment_name=deployment,
            endpoint=endpoint,
            api_version=api_version,
        )

    async def classify(
        self, ocr_text: str, kv_pairs: dict[str, str], candidate_types: list[DocumentTypeSpec]
    ) -> ClassificationResult:
        candidates_desc = "\n".join(
            f"- id={c.id!r}: {c.name} (category: {c.category})" for c in candidate_types
        )
        history = ChatHistory(system_message=_SYSTEM_PROMPT)
        history.add_user_message(
            "Candidate document types:\n"
            f"{candidates_desc}\n\n"
            f"Extracted key-value pairs:\n{json.dumps(kv_pairs, indent=2)}\n\n"
            f"OCR text (truncated to 8000 chars):\n{ocr_text[:8000]}"
        )

        settings = AzureChatPromptExecutionSettings(
            response_format=ClassificationResult,
            temperature=0.0,  # deterministic classification, not creative generation
            max_tokens=800,
        )

        response = await self._service.get_chat_message_content(chat_history=history, settings=settings)
        return ClassificationResult.model_validate_json(str(response))


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
