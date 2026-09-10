# 04. Backend

## Раскладка

```
backend/
├── app/
│   ├── main.py       # объект FastAPI, подключение роутеров, /api/health
│   ├── database.py   # DATABASE_URL, engine, SessionLocal, Base, get_db
│   ├── models.py     # Hotel, Room, Booking
│   ├── schemas.py    # HotelOut, RoomOut, BookingCreate, BookingOut
│   └── routers/
│       ├── hotel.py
│       ├── rooms.py
│       └── bookings.py
├── tests/test_api.py
├── conftest.py       # пустой, нужен pytest — см. ниже
├── seed.py
├── requirements.txt
└── Dockerfile
```

Файлов `__init__.py` нет: с Python 3.3 работают namespace-пакеты, и `from app.routers import rooms` разрешается без них.

Пустой [conftest.py](../backend/conftest.py) в корне `backend/` — не заготовка на будущее, а рабочая необходимость. В режиме импорта `prepend` pytest добавляет в путь поиска модулей каталог самого верхнего `conftest.py`. Без него туда попал бы только `tests/`, и импорт приложения упал бы с `ModuleNotFoundError`. Альтернатива — всегда запускать `python -m pytest`, который сам кладёт текущий каталог в путь.

## Подключение к базе

[database.py](../backend/app/database.py) держит четыре вещи и ничего больше:

```python
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg://hotel:hotel@localhost:5432/hotel")
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False)
```

Параметр `pool_pre_ping` проверяет соединение перед выдачей из пула. Без него первый запрос после долгой паузы, когда база успела разорвать простаивающее соединение, падал бы с ошибкой уровня драйвера.

Дефолт указывает на `localhost` — это адрес для запуска backend на хосте. В контейнере переменную задаёт Compose, и там хост называется `db`.

Зависимость `get_db` — обычный генератор с `try/finally`, отдающий сессию и всегда её закрывающий. FastAPI подставляет её в каждый роутер через `Depends`.

## Роутеры и эндпоинты

| Метод | Путь | Файл | Успех | Ошибки |
|---|---|---|---|---|
| GET | `/api/health` | [main.py](../backend/app/main.py) | 200 | — |
| GET | `/api/hotel` | [hotel.py](../backend/app/routers/hotel.py) | 200 | 404, если база пуста |
| GET | `/api/rooms` | [rooms.py](../backend/app/routers/rooms.py) | 200, возможен пустой список | 422 на нулевой вместимости |
| GET | `/api/rooms/{slug}` | [rooms.py](../backend/app/routers/rooms.py) | 200 | 404 |
| POST | `/api/bookings` | [bookings.py](../backend/app/routers/bookings.py) | 201 | 400, 404, 422 |

Префикс задаётся у каждого роутера, а не глобально при подключении. Так путь виден в том же файле, где написан обработчик.

Данные гостиницы возвращаются первой записью по идентификатору, потому что гостиница в системе одна. Отдельного идентификатора в URL нет намеренно — он был бы ложным обещанием мультитенантности.

Список номеров всегда сортируется по цене, поэтому порядок карточек в каталоге стабилен между запросами.

## Схемы

[schemas.py](../backend/app/schemas.py) содержит четыре класса. Схемы ответов включают `from_attributes=True` — это позволяет FastAPI сериализовать объект SQLAlchemy напрямую, без ручного преобразования в словарь.

Класс `BookingCreate` — единственное место с настоящей валидацией:

```python
guest_name: str = Field(min_length=2, max_length=120)
email: str = Field(pattern=EMAIL_PATTERN, max_length=120)
guests: int = Field(ge=1)

@model_validator(mode="after")
def check_dates(self) -> "BookingCreate":
    if self.check_out <= self.check_in:
        raise ValueError("Дата выезда должна быть позже даты заезда")
    return self
```

Почта проверяется регулярным выражением, а не типом `EmailStr`, чтобы не тянуть пакет `email-validator` ради одной строки. Точность формально ниже, но для формы заявки достаточно.

Сравнение дат делает валидатор уровня модели, а не поля: правило связывает два поля, и одиночный `field_validator` их обоих не видит.

## Создание заявки

Тело обработчика в [bookings.py](../backend/app/routers/bookings.py) читается сверху вниз как список условий: номер существует, номер доступен, гостей не больше вместимости, запись. Конструкция `Booking(**payload.model_dump())` работает потому, что имена полей схемы и модели совпадают один в один.

Статус ответа задан явно как 201. По умолчанию FastAPI вернул бы 200, что для создания ресурса неверно.

## Зависимости

[requirements.txt](../backend/requirements.txt), семь строк с точными версиями:

| Пакет | Версия | Зачем |
|---|---|---|
| `fastapi` | 0.115.6 | Веб-фреймворк |
| `uvicorn[standard]` | 0.34.0 | ASGI-сервер; extras дают watchfiles для автоперезапуска |
| `sqlalchemy` | 2.0.36 | ORM |
| `psycopg[binary]` | 3.2.3 | Драйвер PostgreSQL; extras избавляют от компиляции при сборке образа |
| `pydantic` | 2.10.4 | Схемы |
| `pytest` | 8.3.4 | Тесты |
| `httpx` | 0.28.1 | Транспорт для TestClient |

## Вопросы на понимание

1. Что произойдёт, если удалить пустой conftest и запустить `pytest` из каталога backend?
2. Почему проверка вместимости не сделана в Pydantic вместе с остальными?
3. Зачем схемам ответов нужен режим чтения из атрибутов?
