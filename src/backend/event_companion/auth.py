import os
import time
from collections.abc import Awaitable, Callable
from uuid import UUID

import httpx
import jwt
from fastapi import Request
from jwt import InvalidTokenError, PyJWK

from .models import ApiError

JwksFetcher = Callable[[str], Awaitable[dict]]
TOKEN_ERRORS = (InvalidTokenError, jwt.PyJWKError, KeyError, StopIteration, TypeError, ValueError)


class EntraAuthorizer:
    def __init__(self, jwks_fetcher: JwksFetcher | None = None):
        self.jwks_fetcher = jwks_fetcher or self._fetch_jwks
        self.jwks: dict[str, tuple[float, dict]] = {}
        self.config: tuple[str, str, set[str], set[str]] | None = None

    @staticmethod
    def _identifiers(variable: str) -> set[str]:
        values = {
            value.strip().lower() for value in os.getenv(variable, "").split(",") if value.strip()
        }
        try:
            return {str(UUID(value)) for value in values}
        except ValueError as exc:
            raise ApiError(
                503, "moderation_not_configured", "Moderation is not configured."
            ) from exc

    @staticmethod
    async def _fetch_jwks(tenant_id: str) -> dict:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(
                f"https://login.microsoftonline.com/{tenant_id}/discovery/v2.0/keys"
            )
            response.raise_for_status()
            return response.json()

    async def _keys(self, tenant_id: str) -> dict:
        cached = self.jwks.get(tenant_id)
        if cached and cached[0] > time.monotonic():
            return cached[1]
        try:
            keys = await self.jwks_fetcher(tenant_id)
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            raise ApiError(
                503, "identity_provider_unavailable", "Sign-in is temporarily unavailable."
            ) from exc
        if not isinstance(keys.get("keys"), list):
            raise ApiError(
                503, "identity_provider_unavailable", "Sign-in is temporarily unavailable."
            )
        self.jwks[tenant_id] = (time.monotonic() + 3600, keys)
        return keys

    def _configuration(self) -> tuple[str, str, set[str], set[str]]:
        if self.config:
            return self.config
        tenant_id = os.getenv("ENTRA_TENANT_ID", "")
        client_id = os.getenv("ENTRA_CLIENT_ID", "")
        groups = self._identifiers("ENTRA_MODERATOR_GROUP_IDS")
        allowlist = self._identifiers("ENTRA_MODERATOR_OBJECT_IDS")
        if not tenant_id or not client_id or not (groups or allowlist):
            raise ApiError(503, "moderation_not_configured", "Moderation is not configured.")
        try:
            tenant_id = str(UUID(tenant_id))
            client_id = str(UUID(client_id))
        except ValueError as exc:
            raise ApiError(
                503, "moderation_not_configured", "Moderation is not configured."
            ) from exc
        self.config = tenant_id, client_id, groups, allowlist
        return self.config

    async def authorize(self, request: Request) -> None:
        tenant_id, client_id, groups, allowlist = self._configuration()
        authorization = request.headers.get("Authorization", "")
        if not authorization.startswith("Bearer "):
            raise ApiError(401, "moderator_sign_in_required", "Moderator sign-in is required.")
        token = authorization.removeprefix("Bearer ").strip()
        if not token:
            raise ApiError(401, "moderator_sign_in_required", "Moderator sign-in is required.")
        try:
            header = jwt.get_unverified_header(token)
            key = next(
                key for key in (await self._keys(tenant_id))["keys"] if key["kid"] == header["kid"]
            )
            claims = jwt.decode(
                token,
                PyJWK.from_dict(key).key,
                algorithms=["RS256"],
                audience=[client_id, f"api://{client_id}"],
                issuer=f"https://login.microsoftonline.com/{tenant_id}/v2.0",
                options={"require": ["aud", "exp", "iss", "oid", "tid"]},
            )
        except TOKEN_ERRORS:
            raise ApiError(
                401, "invalid_moderator_token", "Moderator sign-in is required."
            ) from None
        if claims["tid"].lower() != tenant_id:
            raise ApiError(401, "invalid_moderator_token", "Moderator sign-in is required.")
        token_groups = {
            group.lower() for group in claims.get("groups", []) if isinstance(group, str)
        }
        if claims["oid"].lower() not in allowlist and not groups.intersection(token_groups):
            raise ApiError(403, "moderator_not_authorized", "Moderator access is not authorized.")
