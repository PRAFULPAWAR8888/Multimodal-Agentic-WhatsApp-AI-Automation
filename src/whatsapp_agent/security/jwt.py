"""
JWT token utilities for access and refresh tokens.
"""
from datetime import datetime, timedelta, timezone
from typing import Any, Tuple

from jose import JWTError, ExpiredSignatureError, jwt
from whatsapp_agent.config.settings import get_settings
from whatsapp_agent.core.exceptions import InvalidTokenError, TokenExpiredError

ALGORITHM = "HS256"

def create_access_token(subject: str, extra_claims: dict | None = None) -> str:
    """Create a new access token for a given subject."""
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    to_encode = {"sub": subject, "exp": expire, "type": "access"}
    if extra_claims:
        to_encode.update(extra_claims)
    return jwt.encode(to_encode, settings.secret_key, algorithm=ALGORITHM)

def create_refresh_token(subject: str) -> str:
    """Create a new refresh token for a given subject."""
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)
    to_encode = {"sub": subject, "exp": expire, "type": "refresh"}
    return jwt.encode(to_encode, settings.secret_key, algorithm=ALGORITHM)

def decode_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT token."""
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        return payload
    except ExpiredSignatureError as e:
        raise TokenExpiredError("Token has expired") from e
    except JWTError as e:
        raise InvalidTokenError("Invalid token") from e

def create_token_pair(user_id: str, workspace_id: str | None = None) -> Tuple[str, str]:
    """Create a pair of access and refresh tokens."""
    extra_claims = {"workspace_id": workspace_id} if workspace_id else {}
    access_token = create_access_token(subject=user_id, extra_claims=extra_claims)
    refresh_token = create_refresh_token(subject=user_id)
    return access_token, refresh_token
