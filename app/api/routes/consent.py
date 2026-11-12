"""Consent routes: manage user consent records."""

import uuid
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.dependencies import get_current_user
from app.models.user import User, ConsentRecord
from app.models.enums import ConsentType

router = APIRouter()


class GrantConsentRequest(BaseModel):
    type: ConsentType
    version: str
    granted: bool


@router.post("/grant", status_code=status.HTTP_201_CREATED)
def grant_consent(
    payload: GrantConsentRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    record = ConsentRecord(
        user_id=current_user.id,
        type=payload.type,
        version=payload.version,
        granted=payload.granted,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return {
        "id": record.id,
        "type": record.type.value,
        "version": record.version,
        "granted": record.granted,
        "created_at": record.created_at,
    }


@router.get("/status")
def get_user_consent_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    records = db.scalars(
        select(ConsentRecord)
        .where(ConsentRecord.user_id == current_user.id)
        .order_by(ConsentRecord.created_at.desc())
    ).all()

    latest_by_type = {}
    for r in records:
        if r.type.value not in latest_by_type:
            latest_by_type[r.type.value] = {
                "granted": r.granted,
                "version": r.version,
                "created_at": r.created_at,
            }
    return {"user_id": current_user.id, "consents": latest_by_type}
