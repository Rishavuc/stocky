"""Session tokens: signed JWTs, and the FastAPI dependencies that read them.

Every login path (password, register, Google) calls issue_session_token.
Every protected route depends on current_user_id. Nothing else should
parse tokens.
"""
import time
from typing import Optional

import jwt
from fastapi import Header, HTTPException

from app.config import settings

# Only HMAC algorithms: a signed token must need our secret. Pinning the list
# also blocks the classic "alg: none" forgery.
_ALLOWED_ALGORITHMS = {"HS256", "HS384", "HS512"}

# Secrets that have shipped in this repo; never acceptable in production.
_KNOWN_DEFAULT_SECRETS = {
    "investors_eye_super_secret_jwt_key_2026",
    "dev_secret_key_change_in_production_investors_eye_2026",
}


def check_jwt_config() -> None:
    """Called at startup. Refuses to run production with a weak secret."""
    if settings.JWT_ALGORITHM not in _ALLOWED_ALGORITHMS:
        raise RuntimeError(f"JWT_ALGORITHM must be one of {sorted(_ALLOWED_ALGORITHMS)}")
    if not 0 < settings.ACCESS_TOKEN_EXPIRE_MINUTES <= 7 * 24 * 60:
        raise RuntimeError("ACCESS_TOKEN_EXPIRE_MINUTES must be between 1 and 10080 (7 days)")
    weak = settings.JWT_SECRET_KEY in _KNOWN_DEFAULT_SECRETS or len(settings.JWT_SECRET_KEY) < 32
    if weak and settings.is_production:
        raise RuntimeError(
            "JWT_SECRET_KEY is a default or too short. Set a random value of 32+ characters, "
            'e.g. python -c "import secrets; print(secrets.token_urlsafe(48))"'
        )
    if weak:
        print("WARNING: JWT_SECRET_KEY is a default/weak value. Fine for local dev, never for launch.")


def issue_session_token(user_id: str) -> str:
    now = int(time.time())
    payload = {
        "sub": user_id,
        "iat": now,
        "exp": now + settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "typ": "session",
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_session_token(token: str) -> Optional[str]:
    """Returns the user id if the token is ours, unexpired and untampered."""
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            options={"require": ["sub", "exp", "iat"]},
        )
    except jwt.PyJWTError:
        return None
    if payload.get("typ") != "session":
        return None
    return payload.get("sub")


def _bearer(authorization: Optional[str]) -> Optional[str]:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    return token.strip() if scheme.lower() == "bearer" and token.strip() else None


async def optional_user_id(authorization: Optional[str] = Header(None)) -> Optional[str]:
    token = _bearer(authorization)
    return decode_session_token(token) if token else None


async def current_user_id(authorization: Optional[str] = Header(None)) -> str:
    user_id = await optional_user_id(authorization)
    if not user_id:
        raise HTTPException(
            status_code=401,
            detail="Please sign in to continue.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user_id
