import os
import time
from collections import OrderedDict
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.api_services.users import create_or_link_user
from api.type_models.user_claims import UserClaims
from db.get_db_session import get_async_db
from models.user import User

# auto_error=False so a missing header gets the same 401 as a bad token.
bearer_scheme = HTTPBearer(auto_error=False)

CLERK_FRONTEND_API: str = os.getenv("CLERK_FRONTEND_API", "").rstrip("/")
if not CLERK_FRONTEND_API:
    raise RuntimeError("CLERK_FRONTEND_API environment variable not set")

JWKS_URL = f"{CLERK_FRONTEND_API}/.well-known/jwks.json"
jwks_client = jwt.PyJWKClient(JWKS_URL, cache_keys=True)

# Entries expire on their own: evict_user_cache only reaches the calling
# worker, so the TTL is what bounds how long a sibling serves a stale mapping.
_CACHE_TTL = int(os.getenv("CLERK_CACHE_TTL_SECONDS", "300"))
# Hard ceiling so a burst of distinct subjects can't grow the dict without
# bound. Oldest write is dropped first.
_CACHE_MAX_ENTRIES = int(os.getenv("CLERK_CACHE_MAX_ENTRIES", "10000"))

# Process-local cache so warm requests skip the database.
# Value is (user_id, expires_at_monotonic).
user_map: "OrderedDict[str, tuple[int, float]]" = OrderedDict()


def _read_cache(clerk_user_id: str) -> Optional[int]:
    """Return a live cache entry, dropping it instead if it has expired."""
    entry = user_map.get(clerk_user_id)
    if entry is None:
        return None
    user_id, expires_at = entry
    if time.monotonic() >= expires_at:
        user_map.pop(clerk_user_id, None)
        return None
    return user_id


def _write_cache(clerk_user_id: str, user_id: int) -> None:
    """Store an entry with a fresh TTL, evicting the oldest ones past the cap."""
    user_map[clerk_user_id] = (user_id, time.monotonic() + _CACHE_TTL)
    user_map.move_to_end(clerk_user_id)
    while len(user_map) > _CACHE_MAX_ENTRIES:
        user_map.popitem(last=False)


def evict_user_cache(clerk_user_id: str) -> None:
    """Forget a cached Clerk id → user id mapping.

    Call after deleting a user row or moving a Clerk id to another row. Other
    workers keep their entry until it expires.
    """
    user_map.pop(clerk_user_id, None)


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user_claims(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_async_db),
) -> UserClaims:
    if credentials is None:
        raise _unauthorized("Not authenticated")
    token = credentials.credentials

    # ------------------------------------------------------------------
    # 1. Verify Clerk JWT: signature (JWKS), issuer and expiry
    # ------------------------------------------------------------------
    try:
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            issuer=CLERK_FRONTEND_API,
            # Clerk stamps iat with its own clock, so a machine clock even a
            # second behind would reject fresh tokens. Clerk's SDKs allow 5 s too.
            leeway=5,
        )
    except jwt.exceptions.PyJWTError as exc:
        raise _unauthorized(f"Invalid authentication credentials: {exc}")

    clerk_user_id: str = payload.get("sub", "")
    user_email: str = (payload.get("email") or "").strip().lower()

    if not clerk_user_id:
        raise _unauthorized("User ID not found in token")
    if not user_email:
        raise _unauthorized(
            "Email not found in token; request it with the 'fastapi-backend' JWT template"
        )

    user_id = await resolve_user_from_clerk_id(clerk_user_id, user_email, db)
    return UserClaims(user_id=user_id, user_email=user_email)


async def resolve_user_from_clerk_id(
    clerk_user_id: str,
    user_email: str,
    db: AsyncSession,
) -> int:
    """Map a verified Clerk subject to this app's user id, creating it on first login.

    The caller is responsible for having verified the JWT the subject came from.
    """

    # ------------------------------------------------------------------
    # 2. Process-local cache (no network, TTL'd)
    # ------------------------------------------------------------------
    user_id = _read_cache(clerk_user_id)
    if user_id is not None:
        return user_id

    # ------------------------------------------------------------------
    # 3. DB lookup — known user
    # ------------------------------------------------------------------
    user_id = (
        await db.execute(select(User.id).where(User.clerk_user_id == clerk_user_id))
    ).scalar_one_or_none()

    # ------------------------------------------------------------------
    # 4. First login — create the row, or link the one with this email
    # ------------------------------------------------------------------
    if user_id is None:
        user_id = await create_or_link_user(db, clerk_user_id, user_email)

    _write_cache(clerk_user_id, user_id)
    return user_id
