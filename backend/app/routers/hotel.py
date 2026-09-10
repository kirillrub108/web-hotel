from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Hotel
from app.schemas import HotelOut

router = APIRouter(prefix="/api/hotel", tags=["hotel"])


@router.get("", response_model=HotelOut)
def get_hotel(db: Session = Depends(get_db)) -> Hotel:
    hotel = db.scalar(select(Hotel).order_by(Hotel.id).limit(1))
    if hotel is None:
        raise HTTPException(status_code=404, detail="Данные гостиницы не найдены")
    return hotel
