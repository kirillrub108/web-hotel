"""Услуги, заказы услуг и расписание уборок в админке. Права — те же, что у остальных /api/admin/*."""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import ScalarSelect, Select, func, select
from sqlalchemy.orm import Session

from app import hotel_time
from app.database import get_db
from app.housekeeping import day_board, set_task_status
from app.models import Actor, HousekeepingTask, OrderStatus, Service, ServiceOrder
from app.room_service import change_order_status, orders_select
from app.schemas import (
    AdminServiceOrderOut,
    AdminServiceOut,
    HousekeepingBoard,
    HousekeepingStatusIn,
    OrderStatusIn,
    ServiceIn,
)
from app.sessions import require_admin

router = APIRouter(prefix="/api/admin", tags=["admin-services"], dependencies=[Depends(require_admin)])

MAX_ORDERS = 200


def orders_count() -> ScalarSelect[int]:
    return select(func.count(ServiceOrder.id)).where(ServiceOrder.service_id == Service.id).scalar_subquery()


def service_select() -> Select[tuple[Service, int]]:
    return select(Service, orders_count().label("orders_count"))


def service_dict(service: Service, count: int) -> dict[str, object]:
    return {
        "id": service.id,
        "slug": service.slug,
        "title": service.title,
        "description": service.description,
        "category": service.category,
        "price": service.price,
        "unit": service.unit,
        "is_active": service.is_active,
        "sort_order": service.sort_order,
        "orders_count": count,
    }


def get_service_row(db: Session, service_id: int) -> dict[str, object]:
    row = db.execute(service_select().where(Service.id == service_id)).one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Услуга не найдена")
    service, count = row
    return service_dict(service, count)


def check_slug_free(db: Session, slug: str, service_id: int | None) -> None:
    taken = db.scalar(select(Service.id).where(Service.slug == slug))
    if taken is not None and taken != service_id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Услуга с таким кодом уже есть")


@router.get("/services", response_model=list[AdminServiceOut])
def list_services(db: Session = Depends(get_db)) -> list[dict[str, object]]:
    rows = db.execute(service_select().order_by(Service.sort_order, Service.id))
    return [service_dict(service, count) for service, count in rows]


@router.post("/services", response_model=AdminServiceOut, status_code=status.HTTP_201_CREATED)
def create_service(payload: ServiceIn, db: Session = Depends(get_db)) -> dict[str, object]:
    check_slug_free(db, payload.slug, None)
    service = Service(**payload.model_dump())
    db.add(service)
    db.commit()
    return get_service_row(db, service.id)


@router.patch("/services/{service_id}", response_model=AdminServiceOut)
def update_service(service_id: int, payload: ServiceIn, db: Session = Depends(get_db)) -> dict[str, object]:
    service = db.get(Service, service_id)
    if service is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Услуга не найдена")
    check_slug_free(db, payload.slug, service_id)
    # Заказы хранят цену снимком, поэтому изменение цены уже сделанные заказы не меняет.
    for field, value in payload.model_dump().items():
        setattr(service, field, value)
    db.commit()
    return get_service_row(db, service_id)


@router.delete("/services/{service_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_service(service_id: int, db: Session = Depends(get_db)) -> None:
    service = db.get(Service, service_id)
    if service is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Услуга не найдена")
    if db.scalar(select(func.count(ServiceOrder.id)).where(ServiceOrder.service_id == service_id)):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="По услуге есть заказы — её нельзя удалить, только деактивировать",
        )
    db.delete(service)
    db.commit()


@router.get("/service-orders", response_model=list[AdminServiceOrderOut])
def list_service_orders(
    status_filter: OrderStatus | None = Query(default=None, alias="status"),
    day: date | None = Query(default=None, alias="date", description="День, на который назначен заказ"),
    db: Session = Depends(get_db),
) -> list[ServiceOrder]:
    return list(db.scalars(orders_select(day, status_filter).limit(MAX_ORDERS)))


@router.patch("/service-orders/{order_id}", response_model=AdminServiceOrderOut)
def update_service_order(order_id: int, payload: OrderStatusIn, db: Session = Depends(get_db)) -> ServiceOrder:
    order = db.get(ServiceOrder, order_id, with_for_update=True)
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Заказ не найден")
    change_order_status(order, payload.status, Actor.ADMIN)
    db.commit()
    return order


@router.get("/housekeeping", response_model=HousekeepingBoard)
def get_housekeeping(
    day: date | None = Query(default=None, alias="date", description="День расписания, по умолчанию сегодня"),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    return day_board(db, day or hotel_time.hotel_today())


@router.patch("/housekeeping/{task_id}", response_model=HousekeepingBoard)
def update_housekeeping_task(
    task_id: int, payload: HousekeepingStatusIn, db: Session = Depends(get_db)
) -> dict[str, object]:
    """Отмечает уборку и возвращает обновлённое расписание её дня."""
    task = db.get(HousekeepingTask, task_id, with_for_update=True)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Уборка не найдена")
    set_task_status(task, payload.status)
    db.commit()
    return day_board(db, task.date)
