"""Authentication and authorisation dependencies for FastAPI."""

import uuid
from typing import Optional
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.core.database import get_db, run_sync
from app.core.security import decode_token
from app.models.user import User

security_scheme = HTTPBearer(auto_error=False)


async def get_current_user_optional(
    creds: Optional[HTTPAuthorizationCredentials] = Security(security_scheme),
    db: Session = Depends(get_db)
) -> Optional[User]:
    if not creds:
        return None
    payload = decode_token(creds.credentials)
    if not payload or payload.get("token_type") != "access":
        return None
    try:
        user_uuid = uuid.UUID(payload.get("sub"))
    except (ValueError, TypeError):
        return None
    return await run_sync(db.get, User, user_uuid)


async def get_current_user(
    user: Optional[User] = Depends(get_current_user_optional)
) -> User:
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided or are invalid",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


FEEDBACK_ALLOWED_EMAIL = "pdave57@gmail.com"


async def require_feedback_access(
    current_user: User = Depends(get_current_user),
) -> User:
    """Restrict feedback viewing and management strictly to pdave57@gmail.com."""
    if (
        current_user.deleted_at is not None
        or current_user.email.strip().lower() != FEEDBACK_ALLOWED_EMAIL
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Feedback access is restricted to authorized reviewers.",
        )
    return current_user
