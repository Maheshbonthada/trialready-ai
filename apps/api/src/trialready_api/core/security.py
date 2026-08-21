"""JWT validation against Microsoft Entra External ID.

We validate tokens ourselves (signature via JWKS, issuer, audience, expiry) rather
than take on a heavier auth SDK — the API is a pure OAuth2 resource server here;
Entra External ID (the CIAM product, successor to B2C for customer-facing apps)
issues the tokens and owns sign-up/sign-in/MFA. See infra/bicep/modules/entra-b2c.md
for the (largely portal-driven, not Bicep-expressible) tenant setup steps.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import httpx
import structlog
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import jwt
from jose.exceptions import JOSEError
from jose.utils import base64url_decode  # noqa: F401  (re-exported for callers/tests)

from trialready_api.config import Settings, get_settings

logger = structlog.get_logger(__name__)
_bearer_scheme = HTTPBearer(auto_error=False)

_JWKS_CACHE_TTL_SECONDS = 3600


@dataclass(frozen=True)
class AuthenticatedUser:
    subject: str
    email: str | None
    display_name: str | None


class JwksCache:
    """Fetches and caches an issuer's JWKS document so we're not round-tripping to
    Entra on every request. One instance per process, refreshed on TTL expiry or a
    cache miss on `kid` (covers Microsoft's routine key rotation).
    """

    def __init__(self, issuer: str, ttl_seconds: int = _JWKS_CACHE_TTL_SECONDS) -> None:
        self._jwks_uri = f"{issuer.rstrip('/')}/discovery/v2.0/keys"
        self._ttl_seconds = ttl_seconds
        self._keys_by_kid: dict[str, dict] = {}
        self._fetched_at: float = 0.0

    async def get_key(self, kid: str) -> dict:
        if kid not in self._keys_by_kid or self._is_stale():
            await self._refresh()
        if kid not in self._keys_by_kid:
            raise JOSEError(f"Unknown key id {kid!r} — not present in issuer JWKS")
        return self._keys_by_kid[kid]

    def _is_stale(self) -> bool:
        return (time.monotonic() - self._fetched_at) > self._ttl_seconds

    async def _refresh(self) -> None:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(self._jwks_uri)
            response.raise_for_status()
        self._keys_by_kid = {key["kid"]: key for key in response.json()["keys"]}
        self._fetched_at = time.monotonic()


def get_jwks_cache(settings: Settings = Depends(get_settings)) -> JwksCache:
    # Constructed per-request-dependency but internally memoizes; FastAPI's
    # dependency cache keeps this cheap within a single request, and the object
    # itself is safe to promote to a module-level singleton once wired in main.py.
    return JwksCache(settings.entra_issuer)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    settings: Settings = Depends(get_settings),
    jwks_cache: JwksCache = Depends(get_jwks_cache),
) -> AuthenticatedUser:
    if settings.auth_disabled_for_local_dev:
        return AuthenticatedUser(subject="local-dev-user", email="dev@example.com", display_name="Local Dev")

    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")

    try:
        header = jwt.get_unverified_header(credentials.credentials)
        key = await jwks_cache.get_key(header["kid"])
        claims = jwt.decode(
            credentials.credentials,
            key,
            algorithms=[header.get("alg", "RS256")],
            audience=settings.entra_audience,
            issuer=settings.entra_issuer,
        )
    except (JOSEError, httpx.HTTPError, KeyError) as exc:
        logger.warning("auth.token_rejected", error=str(exc))
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc

    return AuthenticatedUser(
        subject=claims["sub"],
        email=claims.get("email") or claims.get("preferred_username"),
        display_name=claims.get("name"),
    )
