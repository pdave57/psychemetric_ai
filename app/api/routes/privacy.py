"""Privacy and data protection routes: user data export and deletion."""

import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.dependencies import get_current_user
from app.models.user import User
from app.services.privacy_service import export_user_data, purge_user_data

router = APIRouter()


@router.get("/export")
def export_my_data(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Export complete account, consent, and assessment history in standard JSON format."""
    data = export_user_data(db, current_user.id)
    return data


@router.delete("/delete-account", status_code=status.HTTP_200_OK)
def delete_my_account(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Permanently delete user profile, consents, responses, scores, and sessions."""
    success = purge_user_data(db, current_user.id)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to purge user account.")
    return {"message": "Account and associated assessment records have been permanently erased."}
