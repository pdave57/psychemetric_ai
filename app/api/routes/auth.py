"""Authentication routes: registration, login, and token refresh."""

import uuid
import re
from typing import Optional
from pydantic import BaseModel, Field, field_validator
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from app.models.user import User
from app.models.enums import UserRole

router = APIRouter()

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class RegisterRequest(BaseModel):
    email: str
    password: str = Field(min_length=8)
    is_adult_confirmed: bool = Field(
        ...,
        description="Must be true to certify the user is 18 years or older."
    )

    @field_validator("email")
    def validate_email(cls, v):
        if not EMAIL_REGEX.match(v):
            raise ValueError("Invalid email format")
        return v.lower()


class LoginRequest(BaseModel):
    email: str
    password: str

    @field_validator("email")
    def validate_email(cls, v):
        if not EMAIL_REGEX.match(v):
            raise ValueError("Invalid email format")
        return v.lower()


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user_id: str


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    if not payload.is_adult_confirmed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="PsychemetreAI is restricted to adults aged 18 and older. Confirmation required.",
        )

    existing = db.scalar(select(User).where(User.email == payload.email.lower()))
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email address already exists.",
        )

    user = User(
        email=payload.email.lower(),
        password_hash=hash_password(payload.password),
        role=UserRole.user,
        is_adult_confirmed=payload.is_adult_confirmed,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    user_id_str = str(user.id)
    return TokenResponse(
        access_token=create_access_token(user_id_str, user.role.value),
        refresh_token=create_refresh_token(user_id_str),
        user_id=user_id_str,
    )


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    user_id_str = str(user.id)
    return TokenResponse(
        access_token=create_access_token(user_id_str, user.role.value),
        refresh_token=create_refresh_token(user_id_str),
        user_id=user_id_str,
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)):
    token_data = decode_token(payload.refresh_token)
    if not token_data or token_data.get("token_type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token.",
        )

    user_uuid = uuid.UUID(token_data.get("sub"))
    user = db.get(User, user_uuid)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found.",
        )

    user_id_str = str(user.id)
    return TokenResponse(
        access_token=create_access_token(user_id_str, user.role.value),
        refresh_token=create_refresh_token(user_id_str),
        user_id=user_id_str,
    )


@router.get("/status")
def auth_status():
    return {"status": "active", "auth_scheme": "bearer_jwt"}
