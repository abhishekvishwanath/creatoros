from typing import Annotated, Optional

import jwt
from fastapi import Depends, Header, HTTPException, status
from jwt import PyJWKClient
from pydantic import BaseModel, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.domain.creator.models import Creator
from app.domain.creator.service import resolve_or_provision_user
from app.infrastructure.db.session import get_db

DbSession = Annotated[AsyncSession, Depends(get_db)]

# One PyJWKClient per Supabase project URL, reused across requests — it
# caches the fetched public keys itself, so this only hits the network on a
# genuine cache miss (a key rotation), not on every request.
_jwks_clients: dict[str, PyJWKClient] = {}


def _get_jwks_client(supabase_url: str) -> PyJWKClient:
    if supabase_url not in _jwks_clients:
        _jwks_clients[supabase_url] = PyJWKClient(f"{supabase_url}/auth/v1/.well-known/jwks.json")
    return _jwks_clients[supabase_url]


def _decode_supabase_jwt(token: str, *, supabase_url: str, jwt_secret: str) -> dict:
    """Verifies a Supabase-issued access token (CLAUDE.md §46). Supabase
    projects sign access tokens one of two ways depending on project
    settings: asymmetric ES256/RS256 keys (the current default for new
    projects — verified against the project's public JWKS, no shared secret
    needed) or the legacy shared HS256 secret (older projects, or ones that
    haven't opted into the newer signing keys). The token's own (unverified
    at this point) header names which one was used, so branch on that
    rather than guessing. PyJWT validates `exp` automatically; `aud=
    "authenticated"` matches every access token Supabase issues to a signed-
    in user."""
    try:
        alg = jwt.get_unverified_header(token).get("alg", "")
    except jwt.PyJWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"Invalid session token: {exc}") from exc

    try:
        if alg == "HS256":
            if not jwt_secret:
                raise HTTPException(
                    status.HTTP_401_UNAUTHORIZED,
                    "This session token is HS256-signed but SUPABASE_JWT_SECRET is not configured on the backend.",
                )
            return jwt.decode(token, jwt_secret, algorithms=["HS256"], audience="authenticated")

        signing_key = _get_jwks_client(supabase_url).get_signing_key_from_jwt(token)
        return jwt.decode(token, signing_key.key, algorithms=[alg or "ES256"], audience="authenticated")
    except HTTPException:
        raise
    except jwt.PyJWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"Invalid or expired session: {exc}") from exc


async def get_current_user_id(
    db: DbSession,
    authorization: Optional[str] = Header(default=None),
    x_debug_user_id: Optional[str] = Header(default=None, alias="X-Debug-User-Id"),
) -> str:
    """Resolves the authenticated user's id (CLAUDE.md §46: enforce
    authorization on every creator-scoped operation).

    Real path: a Supabase-issued `Authorization: Bearer <jwt>` header,
    verified (see _decode_supabase_jwt) and mapped to (or auto-provisioning)
    our own User row via app/domain/creator/service.py::
    resolve_or_provision_user.

    Dev/test fallback: `X-Debug-User-Id`, accepted only when SUPABASE_URL
    isn't configured — same "gracefully degrade when a dependency isn't
    configured" precedent as ModelRouter (CLAUDE.md §12), applied to auth so
    the backend/test suite work with zero Supabase setup. SUPABASE_URL
    (rather than SUPABASE_JWT_SECRET) is the "is real auth configured"
    signal because JWKS-based verification, the default for new Supabase
    projects, only needs the project URL — the secret is only required for
    older HS256 projects. A Bearer token always takes priority when both are
    present, and a Bearer token with real auth unconfigured is a hard error
    (never silently ignored in favor of the debug header) — accepting an
    unverifiable token would be worse than rejecting it outright.
    """
    settings = get_settings()

    if authorization and authorization.lower().startswith("bearer "):
        if not settings.supabase_url:
            raise HTTPException(
                status.HTTP_401_UNAUTHORIZED,
                "A Bearer token was given but SUPABASE_URL is not configured on the backend.",
            )
        token = authorization.split(" ", 1)[1]
        claims = _decode_supabase_jwt(token, supabase_url=settings.supabase_url, jwt_secret=settings.supabase_jwt_secret)
        supabase_auth_id = claims.get("sub")
        email = claims.get("email")
        if not supabase_auth_id or not email:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session token is missing required claims.")
        user = await resolve_or_provision_user(db, supabase_auth_id=supabase_auth_id, email=email)
        return user.id

    if x_debug_user_id and not settings.supabase_url:
        return x_debug_user_id

    raise HTTPException(
        status.HTTP_401_UNAUTHORIZED,
        "Missing or invalid credentials — send an Authorization: Bearer <token> header "
        "(or X-Debug-User-Id when SUPABASE_URL isn't configured, for local dev/tests).",
    )


async def get_owned_creator(
    creator_id: str,
    db: DbSession,
    user_id: str = Depends(get_current_user_id),
) -> Creator:
    """Tenant isolation gate (CLAUDE.md 3.1, 46): every creator-scoped route
    depends on this instead of loading by creator_id alone, so one user can
    never read or mutate another user's creator data."""
    result = await db.execute(select(Creator).where(Creator.id == creator_id))
    creator = result.scalar_one_or_none()
    if creator is None or creator.user_id != user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Creator not found")
    return creator


def validate_or_502(model_cls: type[BaseModel], obj: object, *, label: str) -> BaseModel:
    """Shared across every route that turns a freshly-applied agent proposal
    into a response schema (content briefs/scripts, performance diagnoses,
    ...). Agents only guarantee their JSON has the one required key
    `_parse_json` looks for (CLAUDE.md §40 output contracts are enforced at
    the model layer, not guaranteed by the LLM) — a field with the wrong
    shape (e.g. a list field returned as a string) would otherwise reach
    `.model_validate()` straight from a freshly-applied DB write and crash
    the request with a raw 500. Surfacing it as a 502 keeps this on the same
    "agent produced something unusable" path as a parse failure, instead of
    an unhandled exception."""
    try:
        return model_cls.model_validate(obj)
    except ValidationError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"{label} produced an unexpected shape: {exc}") from exc
