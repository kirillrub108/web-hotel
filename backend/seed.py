"""Начальные данные. Запускается после `alembic upgrade head`: схему сид не создаёт.

Порядок блоков: справочники (отель, номера, услуги) → первый администратор → демо-данные (если SEED_DEMO=true).
Каждый блок принимает Session и ничего не коммитит: транзакцией управляет вызывающий код (main или тест).
Повторный запуск ничего не дублирует.
"""

import os
from datetime import UTC, date, datetime, timedelta

from fastapi import BackgroundTasks
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import hotel_time
from app.booking_lifecycle import change_status, load_hotel, submit_booking
from app.database import SessionLocal
from app.housekeeping import set_task_status
from app.models import (
    Actor,
    Booking,
    BookingStatus,
    CrmStatus,
    Hotel,
    HousekeepingSlot,
    HousekeepingStatus,
    HousekeepingTask,
    OrderStatus,
    Promo,
    PromoKind,
    Room,
    Service,
    ServiceCategory,
    ServiceUnit,
    User,
    UserRole,
)
from app.passwords import check_password, hash_password
from app.promos import find_promo
from app.room_service import change_order_status, create_order

ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@kivana.ru").strip().lower()
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "tidy copper lantern orbit")
ADMIN_FULL_NAME = "Администратор"
SEED_DEMO = os.getenv("SEED_DEMO", "true").strip().lower() == "true"
DEMO_PASSWORD = os.getenv("DEMO_PASSWORD", "silver harbor morning tea")
DEMO_EMAIL_DOMAIN = "@demo.kivana.ru"

HOTEL = {
    "name": "Kivana",
    "tagline": "Kivana — небольшая городская гостиница у реки",
    "description": (
        "Kivana — гостиница на восемнадцать номеров в исторической части города. "
        "Мы занимаем отреставрированный особняк конца XIX века: толстые стены держат тишину, "
        "а окна выходят на набережную и внутренний двор с липами. Завтрак готовят на нашей кухне "
        "и подают до полудня, поэтому выспаться можно даже в будний день. "
        "Гостей встречает администратор, который живёт в этом городе всю жизнь и подскажет, "
        "куда сходить вечером и где действительно вкусно кормят."
    ),
    "address": "г. Ярославль, Волжская набережная, 14",
    "phone": "+7 (4852) 30-14-70",
    "email": "info@kivana.ru",
    "check_in_time": "14:00",
    "check_out_time": "12:00",
}

ROOMS = [
    {
        "slug": "econom",
        "name": "Эконом",
        "description": (
            "Компактный номер для одного гостя на верхнем этаже. Односпальная кровать, "
            "письменный стол у окна, душевая кабина. Подойдёт тем, кто приезжает по делам "
            "и возвращается в гостиницу только ночевать."
        ),
        "price_per_night": 2900,
        "capacity": 1,
        "area": 14,
        "amenities": ["Односпальная кровать", "Душ", "Письменный стол", "Wi-Fi", "Фен"],
        "image": "/images/rooms/econom.svg",
        "is_available": True,
    },
    {
        "slug": "standart",
        "name": "Стандарт",
        "description": (
            "Самый востребованный номер гостиницы. Двуспальная кровать, кресло с торшером "
            "для чтения, гардеробная ниша и ванная комната с ванной. Окна выходят "
            "во внутренний двор, поэтому здесь тихо даже в выходные."
        ),
        "price_per_night": 4500,
        "capacity": 2,
        "area": 22,
        "amenities": [
            "Двуспальная кровать",
            "Ванная комната",
            "Кондиционер",
            "Телевизор",
            "Wi-Fi",
            "Сейф",
        ],
        "image": "/images/rooms/standart.svg",
        "is_available": True,
    },
    {
        "slug": "studiya",
        "name": "Студия",
        "description": (
            "Просторный номер с зоной кухни: плита на две конфорки, холодильник, "
            "посуда и обеденный стол. Удобно для долгого проживания, когда хочется "
            "готовить самому и не зависеть от расписания завтраков."
        ),
        "price_per_night": 5600,
        "capacity": 2,
        "area": 28,
        "amenities": [
            "Двуспальная кровать",
            "Кухонная зона",
            "Холодильник",
            "Обеденный стол",
            "Кондиционер",
            "Wi-Fi",
        ],
        "image": "/images/rooms/studiya.svg",
        "is_available": True,
    },
    {
        "slug": "semeyny",
        "name": "Семейный",
        "description": (
            "Две смежные комнаты: спальня с двуспальной кроватью и детская с двумя "
            "отдельными кроватями. По просьбе ставим детскую кроватку и приносим "
            "стульчик для кормления. Ванная комната с ванной, что важно с маленькими детьми."
        ),
        "price_per_night": 6800,
        "capacity": 4,
        "area": 34,
        "amenities": [
            "Две комнаты",
            "Двуспальная и две односпальные кровати",
            "Ванна",
            "Детская кроватка по запросу",
            "Кондиционер",
            "Wi-Fi",
        ],
        "image": "/images/rooms/semeyny.svg",
        "is_available": True,
    },
    {
        "slug": "lyuks",
        "name": "Люкс",
        "description": (
            "Угловой номер с видом на Волгу и отдельной гостиной. Сохранились "
            "исторические окна в пол и лепнина на потолке. В спальне кровать "
            "king-size, в ванной — отдельная душевая и ванна на ножках."
        ),
        "price_per_night": 9900,
        "capacity": 2,
        "area": 42,
        "amenities": [
            "Гостиная и спальня",
            "Кровать king-size",
            "Вид на реку",
            "Ванна и душевая",
            "Халаты и тапочки",
            "Мини-бар",
            "Wi-Fi",
        ],
        "image": "/images/rooms/lyuks.svg",
        "is_available": True,
    },
    {
        "slug": "apartamenty",
        "name": "Апартаменты",
        "description": (
            "Двухуровневый номер под крышей: внизу гостиная с полноценной кухней "
            "и диваном, наверху две спальни. Есть стиральная машина и посудомоечная "
            "машина — можно приехать большой компанией или семьёй на неделю."
        ),
        "price_per_night": 12500,
        "capacity": 5,
        "area": 60,
        "amenities": [
            "Два уровня",
            "Две спальни",
            "Полноценная кухня",
            "Стиральная машина",
            "Посудомоечная машина",
            "Две ванные комнаты",
            "Wi-Fi",
        ],
        "image": "/images/rooms/apartamenty.svg",
        "is_available": True,
    },
]


FOOD, CLEANING, TRANSFER = ServiceCategory.FOOD, ServiceCategory.HOUSEKEEPING, ServiceCategory.TRANSFER
WELLNESS, OTHER = ServiceCategory.WELLNESS, ServiceCategory.OTHER
ITEM, STAY = ServiceUnit.PER_ITEM, ServiceUnit.PER_STAY

# Каталог услуг: (slug, название, описание, категория, цена в рублях, за что цена). Порядок строк — порядок показа.
SERVICES = [
    (
        "zavtrak-v-nomer",
        "Завтрак в номер",
        "Омлет или сырники, свежая выпечка, масло и джем, чай или кофе на выбор. Подадим в назначенное время.",
        FOOD,
        650,
        ITEM,
    ),
    (
        "syrniki",
        "Сырники со сметаной и ягодами",
        "Четыре сырника из домашнего творога, сметана и ягодный соус.",
        FOOD,
        420,
        ITEM,
    ),
    (
        "sudak",
        "Судак с овощами",
        "Филе судака на гриле, запечённый картофель и сезонные овощи.",
        FOOD,
        890,
        ITEM,
    ),
    (
        "pasta-s-gribami",
        "Паста с лесными грибами",
        "Тальятелле в сливочном соусе с белыми грибами и пармезаном.",
        FOOD,
        640,
        ITEM,
    ),
    (
        "tsezar",
        "Салат «Цезарь» с курицей",
        "Романо, куриное филе, пармезан, сухарики и фирменный соус.",
        FOOD,
        480,
        ITEM,
    ),
    (
        "chaynik-chaya",
        "Чайник чая или кофе",
        "Чёрный, зелёный или травяной чай, а также кофе на выбор. Чайник рассчитан на двоих.",
        FOOD,
        350,
        ITEM,
    ),
    (
        "igristoe",
        "Бутылка игристого вина",
        "Брют, 0,75 л. Подаётся охлаждённым, вместе с бокалами.",
        FOOD,
        2400,
        ITEM,
    ),
    (
        "dop-uborka",
        "Дополнительная уборка",
        "Внеплановая уборка номера: пылесос, влажная уборка, ванная комната и свежие полотенца.",
        CLEANING,
        900,
        ITEM,
    ),
    (
        "smena-belya",
        "Смена белья",
        "Заменим постельное бельё и полотенца на свежие вне графика.",
        CLEANING,
        500,
        ITEM,
    ),
    (
        "prachechnaya",
        "Прачечная",
        "Стирка и глажка за сутки: заберём вещи из номера и вернём к назначенному времени. Цена за комплект до 3 кг.",
        CLEANING,
        700,
        ITEM,
    ),
    (
        "transfer-aeroport",
        "Трансфер из аэропорта",
        "Встретим вас с табличкой в аэропорту Туношна и отвезём в гостиницу на легковом автомобиле. Цена за поездку.",
        TRANSFER,
        1800,
        STAY,
    ),
    (
        "spa",
        "SPA-программа",
        "Расслабляющий массаж 60 минут и час в парной. Запишем вас на удобное время.",
        WELLNESS,
        3200,
        ITEM,
    ),
    (
        "rannij-zaezd",
        "Ранний заезд",
        "Номер будет готов к вашему приезду с утра, раньше обычного времени заезда.",
        OTHER,
        1500,
        STAY,
    ),
    (
        "pozdnij-vyezd",
        "Поздний выезд",
        "Освободите номер на несколько часов позже обычного времени выезда.",
        OTHER,
        1500,
        STAY,
    ),
]


def seed_hotel(session: Session) -> None:
    """Данные гостиницы: добавляются один раз, правки администратора не перезаписываются."""
    if session.scalar(select(func.count(Hotel.id))):
        print("Данные гостиницы уже есть, пропускаем")
        return
    session.add(Hotel(**HOTEL))
    session.flush()
    print("Добавлены данные гостиницы")


def seed_rooms(session: Session) -> None:
    """Добавляет номера, которых ещё нет по slug. Существующие не трогает: цену и описание правит администратор."""
    known = set(session.scalars(select(Room.slug)))
    new_rooms = [Room(**room) for room in ROOMS if room["slug"] not in known]
    session.add_all(new_rooms)
    session.flush()
    print(f"Добавлено номеров: {len(new_rooms)}")


def seed_services(session: Session) -> None:
    """Добавляет услуги, которых ещё нет по slug. Существующие не трогает: правки администратора важнее сида."""
    known = set(session.scalars(select(Service.slug)))
    added = 0
    for sort_order, (slug, title, description, category, price, unit) in enumerate(SERVICES, start=1):
        if slug in known:
            continue
        session.add(
            Service(
                slug=slug,
                title=title,
                description=description,
                category=category,
                price=price,
                unit=unit,
                sort_order=sort_order * 10,
            )
        )
        added += 1
    session.flush()
    print(f"Добавлено услуг: {added}")


def seed_reference_data(session: Session) -> None:
    seed_hotel(session)
    seed_rooms(session)
    seed_services(session)


def create_admin(session: Session, email: str, password: str) -> None:
    """Создаёт администратора, если его ещё нет. Пароль существующего пользователя не меняется никогда."""
    if session.scalar(select(User.id).where(User.email == email)) is not None:
        print(f"Администратор {email} уже есть, пропускаем")
        return

    problem = check_password(password, email=email, full_name=ADMIN_FULL_NAME)
    if problem:
        raise SystemExit(f"ADMIN_PASSWORD не проходит политику паролей: {problem}. Задайте другой пароль в .env")

    now = datetime.now(UTC)
    session.add(
        User(
            email=email,
            password_hash=hash_password(password),
            full_name=ADMIN_FULL_NAME,
            role=UserRole.ADMIN,
            email_verified_at=now,
            consent_at=now,
        )
    )
    session.flush()
    print(f"Создан администратор {email}")


# Демо-клиенты: (email, имя, телефон, отметка CRM, заметка администратора).
DEMO_CLIENTS = [
    ("anna", "Анна Лебедева", "+7 900 111-22-33", CrmStatus.REGULAR, "Просила тихий номер во двор и подушку пожёстче."),
    (
        "viktor",
        "Виктор Соколов",
        "+7 900 222-33-44",
        CrmStatus.VIP,
        "Постоянный гость. Всегда просит Люкс, встречаем чаем.",
    ),
    (
        "igor",
        "Игорь Кротов",
        "+7 900 333-44-55",
        CrmStatus.BLOCKED,
        "Дважды не приехал и не предупредил. Бронь — только после звонка.",
    ),
    ("maria", "Мария Орлова", "+7 900 444-55-66", CrmStatus.REGULAR, None),
]


def create_demo_clients(session: Session) -> dict[str, User]:
    """Подтверждённые гости с одним паролем на всех. Ключ словаря — локальная часть email."""
    problem = check_password(DEMO_PASSWORD, email=f"anna{DEMO_EMAIL_DOMAIN}", full_name="Анна Лебедева")
    if problem:
        raise SystemExit(f"DEMO_PASSWORD не проходит политику паролей: {problem}. Задайте другой пароль в .env")

    now = datetime.now(UTC)
    password_hash = hash_password(DEMO_PASSWORD)
    clients: dict[str, User] = {}
    for name, full_name, phone, crm_status, note in DEMO_CLIENTS:
        clients[name] = User(
            email=f"{name}{DEMO_EMAIL_DOMAIN}",
            password_hash=password_hash,
            full_name=full_name,
            phone=phone,
            role=UserRole.GUEST,
            crm_status=crm_status,
            crm_note=note,
            email_verified_at=now,
            consent_at=now,
        )
    session.add_all(clients.values())
    session.flush()
    return clients


def create_demo_promos(
    session: Session, clients: dict[str, User], rooms: dict[str, Room], today: date
) -> dict[str, Promo]:
    """Три персональные акции и одна общая. Дата начала — месяц назад, окончания — в будущем: акции всегда действуют."""
    start, end = today - timedelta(days=30), today + timedelta(days=90)
    promos = {
        "anna": Promo(
            code="ANNA-10",
            title="Скидка 10% для Анны",
            description="Спасибо, что возвращаетесь к нам.",
            kind=PromoKind.PERCENT,
            value=10,
            valid_from=start,
            valid_to=end,
            min_nights=2,
            user=clients["anna"],
        ),
        "maria": Promo(
            code="MARIA-500",
            title="500 ₽ на следующее проживание",
            description="Подарок за ожидание ответа.",
            kind=PromoKind.FIXED,
            value=500,
            valid_from=start,
            valid_to=end,
            user=clients["maria"],
        ),
        "viktor": Promo(
            code="VIKTOR-LUX",
            title="3000 ₽ на Люкс",
            description="Для постоянных гостей.",
            kind=PromoKind.FIXED,
            value=3000,
            valid_from=start,
            valid_to=end,
            room=rooms["lyuks"],
            user=clients["viktor"],
        ),
        "general": Promo(
            code="KIVANA-10",
            title="Скидка 10% от трёх ночей",
            description="Для всех гостей.",
            kind=PromoKind.PERCENT,
            value=10,
            valid_from=start,
            valid_to=end,
            min_nights=3,
        ),
    }
    session.add_all(promos.values())
    session.flush()
    return promos


def seed_demo(session: Session) -> None:
    """Демо-данные для показа всех возможностей. Все даты считаются от сегодняшнего дня гостиницы.

    Брони создаются тем же кодом, что и из API (submit_booking и change_status), поэтому журнал событий,
    уборки и статусы согласованы. Письма не отправляются: фоновые задачи складываются в BackgroundTasks,
    который никто не запускает. Блок пропускается целиком, если демо-клиенты уже есть.
    """
    if session.scalar(select(func.count(User.id)).where(User.email.like(f"%{DEMO_EMAIL_DOMAIN}"))):
        print("Демо-данные уже есть, пропускаем")
        return

    today = hotel_time.hotel_today()
    rooms = {room.slug: room for room in session.scalars(select(Room))}
    services = {service.slug: service for service in session.scalars(select(Service))}
    clients = create_demo_clients(session)
    promos = create_demo_promos(session, clients, rooms, today)
    background = BackgroundTasks()

    def day(offset: int) -> date:
        return today + timedelta(days=offset)

    def book(
        name: str,
        room_slug: str,
        start: int,
        end: int,
        expected: BookingStatus,
        *,
        guests: int = 1,
        comment: str | None = None,
        promo: Promo | None = None,
    ) -> Booking:
        """Заявка клиента. Если правила решат иначе, чем задумано для демо, сид падает, а не пишет неверные данные."""
        user, room = clients[name], rooms[room_slug]
        if promo:
            find_promo(session, promo.code, user=user, room=room, check_in=day(start), check_out=day(end))
        booking = submit_booking(
            session,
            background,
            user,
            room,
            guest_name=user.full_name,
            phone=user.phone or "",
            check_in=day(start),
            check_out=day(end),
            guests=guests,
            comment=comment,
            promo=promo,
        )
        if booking.status != expected:
            raise RuntimeError(
                f"Демо-бронь {name} {day(start)}–{day(end)}: ожидался статус {expected}, получен {booking.status}"
            )
        return booking

    def mark_tasks_done(booking: Booking, only_until: date | None = None) -> None:
        for task in session.scalars(select(HousekeepingTask).where(HousekeepingTask.booking_id == booking.id)):
            if only_until is None or task.date <= only_until:
                set_task_status(task, HousekeepingStatus.DONE)

    # Завершённые проживания: уборки по ним уже выполнены.
    mark_tasks_done(book("anna", "standart", -20, -17, BookingStatus.CONFIRMED, guests=2))
    mark_tasks_done(book("viktor", "lyuks", -30, -26, BookingStatus.CONFIRMED, guests=2))

    # Текущее проживание: заезд вчера, выезд через два дня. Сегодняшняя уборка выполнена, завтрашняя — на вечер.
    current = book("anna", "studiya", -1, 2, BookingStatus.CONFIRMED, guests=2)
    mark_tasks_done(current, only_until=today)
    tomorrow_task = session.scalars(
        select(HousekeepingTask).where(HousekeepingTask.booking_id == current.id, HousekeepingTask.date == day(1))
    ).one()
    tomorrow_task.slot = HousekeepingSlot.EVENING

    hotel = load_hotel(session)
    # Заказы создаются на будущее время, как и у гостя; выполненному время сдвигается в прошлое вручную.
    create_order(
        session, current, hotel, services["zavtrak-v-nomer"], 2, hotel_time.hotel_datetime(day(1), "09:00"), "Без лука"
    )
    dinner = create_order(
        session, current, hotel, services["sudak"], 2, hotel_time.hotel_datetime(day(1), "19:30"), None
    )
    change_order_status(dinner, OrderStatus.ACCEPTED, Actor.ADMIN)
    laundry = create_order(
        session, current, hotel, services["prachechnaya"], 1, hotel_time.hotel_datetime(day(1), "10:00"), None
    )
    change_order_status(laundry, OrderStatus.ACCEPTED, Actor.ADMIN)
    change_order_status(laundry, OrderStatus.DONE, Actor.ADMIN)
    laundry.scheduled_at = hotel_time.hotel_datetime(day(-1), "18:00")

    # Будущие брони. У Анны применена персональная акция; бронь Виктора на 9 ночей дороже порога,
    # но для VIP правила ручного разбора не действуют.
    book("anna", "standart", 14, 17, BookingStatus.CONFIRMED, guests=2, promo=promos["anna"])
    book("viktor", "lyuks", 40, 49, BookingStatus.CONFIRMED, guests=2)

    # Заявка на рассмотрении: длинное проживание и комментарий.
    book(
        "maria",
        "standart",
        30,
        40,
        BookingStatus.PENDING,
        guests=2,
        comment="Приедем с ребёнком, нужна детская кроватка.",
    )

    # Бронь заблокированного клиента отклоняется сразу.
    book("igor", "standart", 10, 12, BookingStatus.DECLINED)

    # Бронь, которую гость отменил сам.
    cancelled = book("maria", "studiya", 25, 28, BookingStatus.CONFIRMED, guests=2)
    change_status(
        session, cancelled, BookingStatus.CANCELLED, Actor.GUEST, background, actor_user_id=clients["maria"].id
    )

    session.flush()
    print(f"Демо-данные добавлены: клиентов {len(clients)}, акций {len(promos)}")


def main() -> None:
    """Точка входа: открывает сессию, выполняет блоки по порядку и коммитит."""
    with SessionLocal() as session:
        seed_reference_data(session)
        create_admin(session, ADMIN_EMAIL, ADMIN_PASSWORD)
        if SEED_DEMO:
            seed_demo(session)
        session.commit()


if __name__ == "__main__":
    main()
