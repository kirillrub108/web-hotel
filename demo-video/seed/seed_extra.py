"""Дополнительные демо-данные для видео: история гостей, чтобы в админке были видны пагинация и фильтры.

Запускается ПОСЛЕ backend/seed.py, из каталога backend (нужен пакет app):
    cd backend && PYTHONPATH=. python ../demo-video/seed/seed_extra.py

Код приложения не меняется: используется тот же submit_booking, что и в API и в основном сиде.
Детерминированно: имена, телефоны, даты (смещения от сегодняшнего дня гостиницы) и номера фиксированы.
Повторный запуск ничего не дублирует.
"""

from datetime import UTC, datetime, timedelta

from fastapi import BackgroundTasks
from sqlalchemy import func, select

from app import hotel_time
from app.booking_lifecycle import submit_booking
from app.database import SessionLocal
from app.models import Booking, BookingStatus, Room, User, UserRole
from app.passwords import hash_password

DOMAIN = "@guests.kivana.ru"
PASSWORD = "silver harbor morning tea"

# 24 прошлых гостя: вместе с четырьмя демо-клиентами и новой гостьей из видео список клиентов
# занимает две страницы (по 20), а вкладка «Все» в заявках — тоже больше одной страницы.
NAMES = [
    "Алексей Воронин", "Ирина Белова", "Дмитрий Кузнецов", "Елена Морозова", "Сергей Павлов", "Наталья Зайцева",
    "Андрей Голубев", "Ольга Виноградова", "Павел Богданов", "Татьяна Фёдорова", "Михаил Новиков", "Светлана Ковалёва",
    "Николай Егоров", "Юлия Лебедь", "Артём Соловьёв", "Ксения Медведева", "Роман Волков", "Вера Николаева",
    "Константин Алексеев", "Дарья Степанова", "Глеб Макаров", "Алина Захарова", "Тимур Ахметов", "Полина Романова",
]
ROOM_ORDER = ["econom", "standart", "studiya", "semeyny", "lyuks", "apartamenty"]


def main() -> None:
    with SessionLocal() as session:
        if session.scalar(select(func.count(User.id)).where(User.email.like(f"%{DOMAIN}"))):
            print("Доп. данные для видео уже есть, пропускаем")
            return

        today = hotel_time.hotel_today()
        rooms = {room.slug: room for room in session.scalars(select(Room))}
        password_hash = hash_password(PASSWORD)
        background = BackgroundTasks()  # письма не отправляются: задачи никто не запускает
        created = 0

        for index, full_name in enumerate(NAMES):
            # Регистрация и проживание — в прошлом, чтобы гости из сценария видео были наверху списка клиентов.
            days_ago = 400 - index * 12
            registered = datetime.now(UTC) - timedelta(days=days_ago)
            user = User(
                email=f"guest{index + 1:02d}{DOMAIN}",
                password_hash=password_hash,
                full_name=full_name,
                phone=f"+7 901 {100 + index:03d}-{10 + index:02d}-{20 + index:02d}",
                role=UserRole.GUEST,
                email_verified_at=registered,
                consent_at=registered,
                created_at=registered,
                last_login_at=registered,
            )
            session.add(user)
            session.flush()

            room = rooms[ROOM_ORDER[index % len(ROOM_ORDER)]]
            # Каждый гость — в своём окне дат: пересечений подтверждённых броней нет.
            check_in = today - timedelta(days=days_ago - 5)
            booking = submit_booking(
                session,
                background,
                user,
                room,
                guest_name=full_name,
                phone=user.phone or "",
                check_in=check_in,
                check_out=check_in + timedelta(days=2 + index % 3),
                guests=1,
                comment=None,
                promo=None,
            )
            if booking.status != BookingStatus.CONFIRMED:
                raise RuntimeError(f"Доп. бронь {full_name}: ожидалось confirmed, получено {booking.status}")
            booking.created_at = registered + timedelta(days=1)
            created += 1

        session.commit()
        total = session.scalar(select(func.count(Booking.id)))
        print(f"Доп. данные для видео: гостей {created}, всего броней {total}")


if __name__ == "__main__":
    main()
