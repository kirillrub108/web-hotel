from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Service
from app.schemas import ServiceOut

router = APIRouter(prefix="/api/services", tags=["services"])


@router.get("", response_model=list[ServiceOut])
def list_services(db: Session = Depends(get_db)) -> list[Service]:
    """Каталог: только активные услуги, в порядке, который задал администратор."""
    return list(db.scalars(select(Service).where(Service.is_active).order_by(Service.sort_order, Service.id)))
