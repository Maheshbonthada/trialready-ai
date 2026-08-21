"""Binder document file storage.

Blob names are content-addressed (protocol_id/document_type_id/uuid-filename) and
the container is private with managed-identity-only access — see
infra/bicep/modules/storage.bicep. No SAS tokens are generated for this MVP; all
reads go through the API, which enforces the same authz as everything else.
"""

from __future__ import annotations

import uuid
from typing import Protocol

from azure.identity.aio import DefaultAzureCredential
from azure.storage.blob.aio import BlobServiceClient


class BlobStore(Protocol):
    async def upload(self, container: str, path_hint: str, data: bytes, content_type: str) -> str: ...
    async def download(self, container: str, blob_path: str) -> bytes: ...


class AzureBlobStore:
    def __init__(self, account_url: str) -> None:
        self._account_url = account_url

    async def upload(self, container: str, path_hint: str, data: bytes, content_type: str) -> str:
        blob_path = f"{path_hint}/{uuid.uuid4()}"
        async with DefaultAzureCredential() as credential, BlobServiceClient(
            account_url=self._account_url, credential=credential
        ) as client:
            container_client = client.get_container_client(container)
            await container_client.upload_blob(
                name=blob_path, data=data, content_type=content_type, overwrite=False
            )
        return blob_path

    async def download(self, container: str, blob_path: str) -> bytes:
        async with DefaultAzureCredential() as credential, BlobServiceClient(
            account_url=self._account_url, credential=credential
        ) as client:
            container_client = client.get_container_client(container)
            stream = await container_client.download_blob(blob_path)
            return await stream.readall()


class InMemoryBlobStore:
    """Test double."""

    def __init__(self) -> None:
        self._store: dict[str, bytes] = {}

    async def upload(self, container: str, path_hint: str, data: bytes, content_type: str) -> str:
        blob_path = f"{path_hint}/{uuid.uuid4()}"
        self._store[f"{container}/{blob_path}"] = data
        return blob_path

    async def download(self, container: str, blob_path: str) -> bytes:
        return self._store[f"{container}/{blob_path}"]
