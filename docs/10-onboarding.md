# 10. Онбординг

План рассчитан на разработчика, который знаком с Python и Vue, но не видел этот проект. Полный проход занимает примерно рабочий день.

## Шаг 1. Запустить и потрогать (30 минут)

```bash
docker compose up --build
```

Откройте по очереди: главную, каталог, карточку номера, контакты. Примените фильтры так, чтобы получить пустую выдачу. Отправьте заявку с пустыми полями, затем корректную. Загляните в Swagger на `http://localhost:8000/docs` и вызовите оттуда `GET /api/rooms`.

Найдите свою заявку в базе:

```bash
docker compose exec db psql -U hotel -d hotel -c "select * from bookings;"
```

## Шаг 2. Прочитать backend (2 часа)

Порядок чтения — по направлению зависимостей, снизу вверх:

| Файл | На что смотреть |
|---|---|
| [database.py](../backend/app/database.py) | Откуда берётся строка подключения, как устроена зависимость сессии |
| [models.py](../backend/app/models.py) | Три таблицы, типы колонок, единственный внешний ключ |
| [schemas.py](../backend/app/schemas.py) | Чем схема ответа отличается от схемы запроса, где живёт сравнение дат |
| [rooms.py](../backend/app/routers/rooms.py) | Как собирается запрос с необязательными фильтрами |
| [bookings.py](../backend/app/routers/bookings.py) | Порядок проверок и какой статус соответствует какой ошибке |
| [main.py](../backend/app/main.py) | Как всё соединяется, где живёт health |
| [seed.py](../backend/seed.py) | Ожидание базы, создание таблиц, проверка идемпотентности |

Сопроводительный текст — [04-backend.md](04-backend.md) и [05-data-model.md](05-data-model.md).

## Шаг 3. Прочитать frontend (2 часа)

| Файл | На что смотреть |
|---|---|
| [nuxt.config.ts](../frontend/nuxt.config.ts) | Правило прокси — самая важная строка во всём фронте |
| [app.vue](../frontend/app/app.vue) | Из чего состоит каждая страница |
| [types.ts](../frontend/app/types.ts) | Контракт с API на стороне TypeScript |
| [pages/rooms/index.vue](../frontend/app/pages/rooms/index.vue) | Реактивные фильтры и повторный запрос |
| [BookingForm.vue](../frontend/app/components/BookingForm.vue) | Состояния формы, клиентская валидация, разбор ошибки сервера |
| [main.css](../frontend/app/assets/css/main.css) | Переменные и общие классы |

Сопроводительный текст — [06-frontend.md](06-frontend.md) и [02-architecture.md](02-architecture.md).

## Шаг 4. Прочитать инфраструктуру (30 минут)

[docker-compose.yml](../docker-compose.yml) целиком, оба Dockerfile, [07-infrastructure.md](07-infrastructure.md). Особое внимание — двум монтированиям у frontend и команде backend с `&&`.

## Шаг 5. Сделать сквозную правку (2 часа)

Задача для проверки понимания: добавить номеру этаж и показать его в карточке.

1. Колонка `floor` в модели.
2. Поле в схеме ответа.
3. Значения во всех шести номерах сида.
4. Поле в интерфейсе `Room`.
5. Вывод на странице карточки номера.
6. `docker compose down -v && docker compose up --build`.

Пункт шестой — главный: без пересоздания базы колонка не появится, и понимание почему означает, что раздел про модель данных прочитан не зря.

## Топ-7 файлов проекта

1. [docker-compose.yml](../docker-compose.yml) — как всё запускается
2. [nuxt.config.ts](../frontend/nuxt.config.ts) — как фронт находит backend
3. [models.py](../backend/app/models.py) — что хранится
4. [bookings.py](../backend/app/routers/bookings.py) — единственная бизнес-логика в проекте
5. [seed.py](../backend/seed.py) — откуда берутся данные
6. [BookingForm.vue](../frontend/app/components/BookingForm.vue) — самый сложный компонент
7. [main.css](../frontend/app/assets/css/main.css) — весь внешний вид

## Самопроверка

Вы освоились, если можете ответить не подглядывая:

1. Почему в FastAPI нет CORS-middleware и что случится, если убрать правило прокси?
2. Какие три проверки заявки делает роутер и почему они не могут жить в Pydantic?
3. Что произойдёт при втором `docker compose up` и какая строка кода это обеспечивает?
4. Зачем контейнеру frontend анонимный том?
5. Почему добавление колонки требует `down -v`?
6. Где заканчивается клиентская валидация формы и начинается серверная?
7. Назовите две вещи, которые нужно закрыть до публикации сайта в интернет. Сверьтесь с [09-tech-debt.md](09-tech-debt.md).
