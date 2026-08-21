"""OCR/layout extraction over uploaded binder documents.

Wraps Azure AI Document Intelligence's prebuilt-document model, which gives us
plain text plus key-value pairs and tables in one pass — materially better than
raw OCR for forms like the 1572 or a delegation-of-authority log, and far cheaper
in tokens than sending page images straight to a vision-capable chat model.

`DocumentOcrClient` is a Protocol so the classification pipeline never imports the
Azure SDK directly — tests inject `FakeDocumentOcrClient` and never touch the network.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from azure.ai.documentintelligence.aio import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import AnalyzeDocumentRequest
from azure.identity.aio import DefaultAzureCredential
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential


@dataclass
class OcrResult:
    full_text: str
    key_value_pairs: dict[str, str] = field(default_factory=dict)
    page_count: int = 1


class DocumentOcrClient(Protocol):
    async def extract(self, file_bytes: bytes, content_type: str) -> OcrResult: ...


class AzureDocumentOcrClient:
    """Production implementation. Auth is via managed identity — no API key ever
    lives in config or environment variables (see infra/bicep/modules/document-intelligence.bicep,
    which grants the container app's identity the Cognitive Services User role).
    """

    def __init__(self, endpoint: str) -> None:
        self._endpoint = endpoint

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type(Exception),
    )
    async def extract(self, file_bytes: bytes, content_type: str) -> OcrResult:
        async with DefaultAzureCredential() as credential, DocumentIntelligenceClient(
            endpoint=self._endpoint, credential=credential
        ) as client:
            poller = await client.begin_analyze_document(
                "prebuilt-document",
                AnalyzeDocumentRequest(bytes_source=file_bytes),
                content_type=content_type,
            )
            result = await poller.result()

        kv_pairs = {
            (kv.key.content if kv.key else ""): (kv.value.content if kv.value else "")
            for kv in (result.key_value_pairs or [])
        }
        return OcrResult(
            full_text=result.content or "",
            key_value_pairs=kv_pairs,
            page_count=len(result.pages or []) or 1,
        )


class FakeDocumentOcrClient:
    """Test double: returns a canned result regardless of input."""

    def __init__(self, canned_result: OcrResult | None = None) -> None:
        self._result = canned_result or OcrResult(full_text="", key_value_pairs={})

    async def extract(self, file_bytes: bytes, content_type: str) -> OcrResult:
        return self._result
