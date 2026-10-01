"""CRM в админке: клиенты и акции. Права — те же, что у остальных /api/admin/*: только администратор."""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session, joinedload

from app.booking_lifecycle import expire_stale_pending
from app.crm import client_dict, client_select, search_condition
from app.database import get_db
from app.models import Booking, Promo, Room, User, UserRole
from app.promos import promo_dict, promo_select
from app.schemas import AdminPromoOut, ClientDetail, ClientOut, ClientPage, ClientUpdate, PromoIn
from app.sessions import require_admin

router = APIRouter(prefix="/api/admin", tags=["admin-crm"], dependencies=[Depends(require_admin)])


def get_client_row(db: Session, client_id: int) -> dict[str, object]:
    row = db.execute(client_select().where(User.id == client_id)).one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Клиент не найден")
    return client_dict(row)


@router.get("/clients", response_model=ClientPage)
def list_clients(
    search: str | None = Query(default=None, max_length=100, description="Имя, email или телефон"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    query = client_select()
    count_query = select(func.count(User.id)).where(User.role == UserRole.GUEST)
    if search and search.strip():
        condition = search_condition(search)
        query = query.where(condition)
        count_query = count_query.where(condition)
    # Недавно активные сверху; id делает порядок стабильным между страницами.
    rows = db.execute(query.order_by(desc("last_activity_at"), User.id.desc()).limit(limit).offset(offset))
    return {"items": [client_dict(row) for row in rows], "total": db.scalar(count_query)}


@router.get("/clients/{client_id}", response_model=ClientDetail)
def get_client(client_id: int, background: BackgroundTasks, db: Session = Depends(get_db)) -> dict[str, object]:
    # Как в админке заявок: статусы в карточке не должны отставать от просрочки.
    expire_stale_pending(db, background)
    db.commit()
    bookings = db.scalars(
        select(Booking)
        .options(joinedload(Booking.room), joinedload(Booking.user), joinedload(Booking.promo))
        .where(Booking.user_id == client_id)
        .order_by(Booking.check_in.desc(), Booking.id.desc())
    )
    promos = db.execute(promo_select().where(Promo.user_id == client_id).order_by(Promo.id.desc()))
    return {
        "client": get_client_row(db, client_id),
        "bookings": list(bookings),
        "promos": [promo_dict(row) for row in promos],
    }


@router.patch("/clients/{client_id}", response_model=ClientOut)
def update_client(client_id: int, payload: ClientUpdate, db: Session = Depends(get_db)) -> dict[str, object]:
    client = db.scalar(select(User).where(User.id == client_id, User.role == UserRole.GUEST))
    if client is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Клиент не найден")
    # Блокировка не трогает существующие брони: их судьбу решает администратор. Влияет только на новые заявки.
    if "crm_status" in payload.model_fields_set and payload.crm_status is not None:
        client.crm_status = payload.crm_status
    if "crm_note" in payload.model_fields_set:
        client.crm_note = payload.crm_note
    db.commit()
    return get_client_row(db, client_id)


@router.get("/promos", response_model=list[AdminPromoOut])
def list_promos(
    personal: bool | None = Query(default=None, description="true — персональные, false — общие"),
    db: Session = Depends(get_db),
) -> list[dict[str, object]]:
    query = promo_select().order_by(Promo.id.desc())
    if personal is not None:
        query = query.where(Promo.user_id.is_not(None) if personal else Promo.user_id.is_(None))
    return [promo_dict(row) for row in db.execute(query)]


def get_promo_row(db: Session, promo_id: int) -> dict[str, object]:
    row = db.execute(promo_select().where(Promo.id == promo_id)).one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Акция не найдена")
    return promo_dict(row)


def check_promo_links(db: Session, payload: PromoIn, promo_id: int | None) -> None:
    """Код уникален, номер и клиент существуют. promo_id — редактируемая акция: сама с собой код не конфликтует."""
    taken = db.scalar(select(Promo.id).where(Promo.code == payload.code))
    if taken is not None and taken != promo_id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Промокод с таким кодом уже есть")
    if payload.room_id is not None and db.get(Room, payload.room_id) is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Номер не найден")
    if payload.user_id is not None and not db.scalar(
        select(User.id).where(User.id == payload.user_id, User.role == UserRole.GUEST)
    ):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Клиент не найден")


@router.post("/promos", response_model=AdminPromoOut, status_code=status.HTTP_201_CREATED)
def create_promo(payload: PromoIn, db: Session = Depends(get_db)) -> dict[str, object]:
    check_promo_links(db, payload, None)
    promo = Promo(**payload.model_dump())
    db.add(promo)
    db.commit()
    return get_promo_row(db, promo.id)


@router.patch("/promos/{promo_id}", response_model=AdminPromoOut)
def update_promo(promo_id: int, payload: PromoIn, db: Session = Depends(get_db)) -> dict[str, object]:
    promo = db.get(Promo, promo_id)
    if promo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Акция не найдена")
    check_promo_links(db, payload, promo_id)
    # Брони хранят скидку снимком, поэтому изменение условий уже созданные брони не меняет.
    for field, value in payload.model_dump().items():
        setattr(promo, field, value)
    db.commit()
    return get_promo_row(db, promo_id)


@router.delete("/promos/{promo_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_promo(promo_id: int, db: Session = Depends(get_db)) -> None:
    promo = db.get(Promo, promo_id)
    if promo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Акция не найдена")
    if db.scalar(select(func.count(Booking.id)).where(Booking.promo_id == promo_id)):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Акция применена в бронях — её нельзя удалить, только деактивировать",
        )
    db.delete(promo)
    db.commit()
