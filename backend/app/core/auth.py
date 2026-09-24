"""Clerk JWT verification.

Every request that needs a user identity carries a Clerk session token as a
Bearer token. We verify it against Clerk's JWKS (fetched once, cached) rather
than trusting any client-supplied user/org id. The active Clerk Organization
id (`org_id` claim, present when the frontend has an active org selected)
becomes the tenant boundary end to end - see app/api/deps.py.
"""

import time
from typing import Any

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import jwt
from jose.exceptions import JOSEError

from app.config import get_settings

settings = get_settings()
bearer_scheme = HTTPBearer(auto_error=False)

_JWKS_TTL_SECONDS = 3600
_jwks_cache: dict[str, Any] = {"keys": None, "fetched_at": 0.0}


async def _get_jwks() -> dict[str, Any]:
    now = time.time()
    if _jwks_cache["keys"] is None or now - _jwks_cache["fetched_at"] > _JWKS_TTL_SECONDS:
        if not settings.clerk_jwks_url:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="CLERK_JWKS_URL is not configured on the backend.",
            )
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(settings.clerk_jwks_url)
            response.raise_for_status()
        _jwks_cache["keys"] = response.json()
        _jwks_cache["fetched_at"] = now
    return _jwks_cache["keys"]


class AuthenticatedUser:
    def __init__(
        self,
        clerk_user_id: str,
        clerk_org_id: str | None,
        org_role: str | None,
        claims: dict[str, Any],
    ) -> None:
        self.clerk_user_id = clerk_user_id
        self.clerk_org_id = clerk_org_id
        self.org_role = org_role
        self.claims = claims


async def get_current_claims(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict[str, Any]:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token.")

    jwks = await _get_jwks()
    try:
        unverified_header = jwt.get_unverified_header(credentials.credentials)
        key = next((k for k in jwks["keys"] if k["kid"] == unverified_header.get("kid")), None)
        if key is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unknown signing key.")
        claims = jwt.decode(
            credentials.credentials,
            key,
            algorithms=["RS256"],
            options={"verify_aud": False},
        )
    except JOSEError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid or expired token: {exc}"
        ) from exc

    return claims


def _extract_org_claims(claims: dict[str, Any]) -> tuple[str | None, str | None]:
    """Return (org_id, org_role) from a Clerk session token.

    Default (v2) Clerk session tokens nest the active organization under a
    shortened "o" claim: {"id": ..., "rol": ..., "slg": ...} - confirmed
    against a real token from our Clerk instance while testing sign-in.
    Custom JWT templates can still emit the older flat "org_id"/"org_role"
    claims, so that shape is kept as a fallback.
    """
    org = claims.get("o")
    if isinstance(org, dict):
        return org.get("id"), org.get("rol")
    return claims.get("org_id"), claims.get("org_role")


async def get_current_user(claims: dict[str, Any] = Depends(get_current_claims)) -> AuthenticatedUser:
    clerk_user_id = claims.get("sub")
    if not clerk_user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token missing subject claim.")
    org_id, org_role = _extract_org_claims(claims)
    return AuthenticatedUser(
        clerk_user_id=clerk_user_id,
        clerk_org_id=org_id,
        org_role=org_role,
        claims=claims,
    )
