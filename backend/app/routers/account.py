from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.schemas import ProfileUpdate, UserOut
from app.sessions import require_user

router = APIRouter(prefix="/api/account", tags=["account"])


@router.get("/profile", response_model=UserOut)
def get_profile(user: User = Depends(require_user)) -> User:
    return user


@router.patch("/profile", response_model=UserOut)
def update_profile(payload: ProfileUpdate, user: User = Depends(require_user), db: Session = Depends(get_db)) -> User:
    user.full_name = payload.full_name
    user.phone = payload.phone
    db.commit()
    return user
