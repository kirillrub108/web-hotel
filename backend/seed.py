import os
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Hotel, Room, Service, ServiceCategory, ServiceUnit, User, UserRole
from app.passwords import check_password, hash_password

ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@kivana.ru").strip().lower()
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "tidy copper lantern orbit")
ADMIN_FULL_NAME = "Администратор"

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
    if session.scalar(select(func.count(Room.id))):
        print("Гостиница и номера уже есть, пропускаем")
        return

    session.add(Hotel(**HOTEL))
    session.add_all(Room(**room) for room in ROOMS)
    session.commit()
    print(f"Добавлены данные гостиницы и {len(ROOMS)} номеров")


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
    session.commit()
    print(f"Добавлено услуг: {added}")


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
    session.commit()
    print(f"Создан администратор {email}")


def seed() -> None:
    """Наполняет базу данными. Таблицы к этому моменту уже созданы командой `alembic upgrade head`."""
    with SessionLocal() as session:
        seed_hotel(session)
        seed_services(session)
        create_admin(session, ADMIN_EMAIL, ADMIN_PASSWORD)


if __name__ == "__main__":
    seed()
