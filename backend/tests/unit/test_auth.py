from datetime import datetime, timedelta, timezone

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import HTTPException

from app.api import deps as deps_module
from app.api.deps import _decode_supabase_jwt
from app.domain.creator.service import find_or_create_user_by_email, resolve_or_provision_user
from app.infrastructure.db.session import AsyncSessionLocal

SECRET = "unit-test-secret"


def _make_token(*, sub: str = "auth_user_1", email: str = "jwt@example.com", secret: str = SECRET, **overrides) -> str:
    payload = {
        "sub": sub,
        "email": email,
        "aud": "authenticated",
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        **overrides,
    }
    return jwt.encode(payload, secret, algorithm="HS256")


# These tests exercise the legacy HS256 path only (the algorithm named in
# the token's own header, which _make_token sets via algorithm="HS256") —
# the JWKS/asymmetric path needs a live Supabase project's JWKS endpoint and
# is instead covered by the live smoke test run during development (see the
# session's PR/commit notes), not by the hermetic unit suite.
DUMMY_URL = "https://example.supabase.co"


def test_decode_supabase_jwt_returns_claims_for_a_valid_token():
    token = _make_token()
    claims = _decode_supabase_jwt(token, supabase_url=DUMMY_URL, jwt_secret=SECRET)
    assert claims["sub"] == "auth_user_1"
    assert claims["email"] == "jwt@example.com"


def test_decode_supabase_jwt_rejects_wrong_secret():
    token = _make_token()
    with pytest.raises(HTTPException) as exc_info:
        _decode_supabase_jwt(token, supabase_url=DUMMY_URL, jwt_secret="wrong-secret")
    assert exc_info.value.status_code == 401


def test_decode_supabase_jwt_rejects_expired_token():
    token = _make_token(exp=datetime.now(timezone.utc) - timedelta(hours=1))
    with pytest.raises(HTTPException) as exc_info:
        _decode_supabase_jwt(token, supabase_url=DUMMY_URL, jwt_secret=SECRET)
    assert exc_info.value.status_code == 401


def test_decode_supabase_jwt_rejects_wrong_audience():
    token = _make_token(aud="something_else")
    with pytest.raises(HTTPException):
        _decode_supabase_jwt(token, supabase_url=DUMMY_URL, jwt_secret=SECRET)


def test_decode_supabase_jwt_rejects_hs256_token_with_no_secret_configured():
    token = _make_token()
    with pytest.raises(HTTPException) as exc_info:
        _decode_supabase_jwt(token, supabase_url=DUMMY_URL, jwt_secret="")
    assert exc_info.value.status_code == 401


# The JWKS/asymmetric path (ES256), the actual algorithm current Supabase
# projects sign access tokens with (verified directly against the real
# project during development). _get_jwks_client is monkeypatched so this
# stays hermetic — no real network call to a JWKS endpoint.
class _FakeSigningKey:
    def __init__(self, key):
        self.key = key


class _FakeJWKClient:
    def __init__(self, public_key):
        self._public_key = public_key

    def get_signing_key_from_jwt(self, token):
        return _FakeSigningKey(self._public_key)


def _make_es256_token(**overrides) -> tuple[str, object]:
    private_key = ec.generate_private_key(ec.SECP256R1())
    payload = {
        "sub": "auth_es256_1",
        "email": "es256@example.com",
        "aud": "authenticated",
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        **overrides,
    }
    token = jwt.encode(payload, private_key, algorithm="ES256")
    return token, private_key.public_key()


def test_decode_supabase_jwt_verifies_es256_token_via_jwks(monkeypatch):
    token, public_key = _make_es256_token()
    monkeypatch.setattr(deps_module, "_get_jwks_client", lambda url: _FakeJWKClient(public_key))

    claims = _decode_supabase_jwt(token, supabase_url=DUMMY_URL, jwt_secret="")
    assert claims["sub"] == "auth_es256_1"
    assert claims["email"] == "es256@example.com"


def test_decode_supabase_jwt_rejects_es256_token_with_wrong_key(monkeypatch):
    token, _real_public_key = _make_es256_token()
    _, wrong_public_key = _make_es256_token()
    monkeypatch.setattr(deps_module, "_get_jwks_client", lambda url: _FakeJWKClient(wrong_public_key))

    with pytest.raises(HTTPException) as exc_info:
        _decode_supabase_jwt(token, supabase_url=DUMMY_URL, jwt_secret="")
    assert exc_info.value.status_code == 401


_creator_counter = 0


def _unique_email() -> str:
    global _creator_counter
    _creator_counter += 1
    return f"authtest{_creator_counter}@example.com"


async def test_resolve_or_provision_user_creates_new_user():
    email = _unique_email()
    async with AsyncSessionLocal() as session:
        user = await resolve_or_provision_user(session, supabase_auth_id="auth_new_1", email=email)
    assert user.email == email
    assert user.supabase_auth_id == "auth_new_1"


async def test_resolve_or_provision_user_returns_existing_user_by_auth_id():
    email = _unique_email()
    async with AsyncSessionLocal() as session:
        first = await resolve_or_provision_user(session, supabase_auth_id="auth_existing_1", email=email)

    async with AsyncSessionLocal() as session:
        second = await resolve_or_provision_user(session, supabase_auth_id="auth_existing_1", email=email)
    assert second.id == first.id


async def test_resolve_or_provision_user_links_existing_email_bootstrapped_user():
    """A user created via the dev-mode email bootstrap (no supabase_auth_id
    yet) should link up with their real identity on first real
    authentication, rather than getting a second, disconnected User row."""
    email = _unique_email()
    async with AsyncSessionLocal() as session:
        bootstrapped = await find_or_create_user_by_email(session, email=email)
        await session.commit()
        bootstrapped_id = bootstrapped.id
    assert bootstrapped.supabase_auth_id is None

    async with AsyncSessionLocal() as session:
        linked = await resolve_or_provision_user(session, supabase_auth_id="auth_link_1", email=email)
    assert linked.id == bootstrapped_id
    assert linked.supabase_auth_id == "auth_link_1"


async def test_find_or_create_user_by_email_is_idempotent():
    email = _unique_email()
    async with AsyncSessionLocal() as session:
        first = await find_or_create_user_by_email(session, email=email)
        await session.commit()

    async with AsyncSessionLocal() as session:
        second = await find_or_create_user_by_email(session, email=email)
    assert second.id == first.id
