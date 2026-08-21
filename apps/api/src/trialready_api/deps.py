"""FastAPI dependency wiring — the one place that decides "real Azure client" vs
"local/test double," based on config. Routers and services never construct these
themselves, which is what keeps the services layer unit-testable without mocking
frameworks: tests just pass fakes directly to the service functions instead of
going through this module at all.
"""

from __future__ import annotations

from fastapi import Depends

from trialready_api.agents.classification_agent import (
    AzureOpenAIDocumentClassifier,
    DocumentClassifier,
    FakeDocumentClassifier,
)
from trialready_api.agents.ocr_client import AzureDocumentOcrClient, DocumentOcrClient, FakeDocumentOcrClient
from trialready_api.config import Settings, get_settings
from trialready_api.services.blob_storage import AzureBlobStore, BlobStore, InMemoryBlobStore

_in_memory_blob_store = InMemoryBlobStore()  # shared across a local dev process's lifetime


# Not module-level singletons: each of these just holds config strings and opens
# its Azure SDK client lazily per call (see `async with` in ocr_client.py /
# blob_storage.py), so re-constructing the wrapper per request is cheap. If
# production profiling shows credential-token-fetch overhead is worth avoiding,
# promote DefaultAzureCredential to a single app-lifespan instance first — that's
# where the real per-call cost lives, not this wrapper object.
def get_ocr_client(settings: Settings = Depends(get_settings)) -> DocumentOcrClient:
    if settings.doc_intelligence_endpoint:
        return AzureDocumentOcrClient(settings.doc_intelligence_endpoint)
    return FakeDocumentOcrClient()


def get_classifier(settings: Settings = Depends(get_settings)) -> DocumentClassifier:
    if settings.azure_openai_endpoint:
        return AzureOpenAIDocumentClassifier(
            endpoint=settings.azure_openai_endpoint,
            deployment=settings.azure_openai_deployment_fast,
            api_version=settings.azure_openai_api_version,
        )
    return FakeDocumentClassifier()


def get_blob_store(settings: Settings = Depends(get_settings)) -> BlobStore:
    if settings.storage_account_url:
        return AzureBlobStore(settings.storage_account_url)
    return _in_memory_blob_store
