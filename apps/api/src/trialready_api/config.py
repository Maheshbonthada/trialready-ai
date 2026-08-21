"""Centralized, typed application configuration.

All runtime configuration comes from environment variables (12-factor). In Azure,
these are injected as Container Apps environment variables backed by Key Vault
references — nothing secret is ever baked into the image or checked into git.
See infra/bicep/modules/container-app-api.bicep for how each of these is wired.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- App / environment ---
    environment: Literal["local", "dev", "staging", "prod"] = "local"
    app_name: str = "trialready-api"
    log_level: str = "INFO"
    api_root_path: str = ""

    # Comma-separated. In Azure this is set to the Static Web App's actual
    # hostname (see infra/bicep/modules/static-web-app.bicep's output +
    # container-app-api.bicep's CORS_ALLOWED_ORIGINS env var) — never guessed
    # or hardcoded, since the default *.azurestaticapps.net hostname exists
    # before any custom domain is configured and CORS has to work against it
    # from the first deploy.
    cors_allowed_origins: str = "http://localhost:5173,http://localhost:3000"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]

    # --- Database (Azure Database for PostgreSQL Flexible Server) ---
    database_url: str = Field(
        # Port 5433, not Postgres's default 5432 — see docker-compose.yml's comment:
        # plenty of dev machines already run a native Postgres on 5432.
        default="postgresql+asyncpg://trialready:trialready@localhost:5433/trialready",
        description="Async SQLAlchemy DSN. In Azure, injected via Key Vault reference.",
    )
    db_pool_size: int = 5
    db_max_overflow: int = 5

    # --- Auth (Microsoft Entra External ID) ---
    entra_tenant_id: str = ""
    entra_client_id: str = ""
    entra_issuer: str = ""  # e.g. https://<tenant>.ciamlogin.com/<tenant-id>/v2.0
    entra_audience: str = ""
    auth_disabled_for_local_dev: bool = False

    # --- LLM provider ---
    # "azure_openai" is the production target (managed identity, no API key —
    # see infra/bicep/modules/openai.bicep). "openai" (api.openai.com direct) is
    # a pragmatic pre-Azure option: point it at a personal/team OpenAI API key
    # so the classification agent runs for real in local dev, not just against
    # fakes, before there's an Azure subscription to deploy Azure OpenAI into.
    # Swap this one value back to "azure_openai" at deploy time — nothing else
    # in the codebase changes.
    ai_provider: Literal["azure_openai", "openai"] = "azure_openai"

    azure_openai_endpoint: str = ""
    azure_openai_deployment_fast: str = "gpt-4o-mini"  # classification/extraction (cheap, low latency)
    azure_openai_deployment_reasoning: str = "gpt-4o"  # gap-report narrative only (low volume)
    azure_openai_api_version: str = "2024-08-01-preview"

    # --- OpenAI (api.openai.com) — local-dev-until-Azure path ---
    openai_api_key: str = ""
    openai_model_fast: str = "gpt-4o-mini"

    # --- Azure AI Document Intelligence ---
    doc_intelligence_endpoint: str = ""

    # --- Azure Blob Storage ---
    storage_account_url: str = ""
    binder_documents_container: str = "binder-documents"

    # --- Azure Key Vault (managed identity auth, no secret client-side) ---
    key_vault_url: str = ""

    # --- Application Insights ---
    applicationinsights_connection_string: str = ""

    # --- Classification confidence gate ---
    # Below this confidence, a document is routed to human review rather than
    # auto-accepted. This threshold is the single most important compliance
    # control in the system — see docs/compliance-checklist.md.
    classification_min_confidence: float = 0.85

    # --- Gap-check alert thresholds (days) applied on top of per-document overrides ---
    default_alert_window_days: int = 30


@lru_cache
def get_settings() -> Settings:
    return Settings()
