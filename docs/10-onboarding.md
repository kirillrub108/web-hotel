# 10. Онбординг

План рассчитан на разработчика, который знаком с Python и Vue, но не видел этот проект. Полный проход занимает примерно рабочий день.

## Шаг 1. Запустить и потрогать (40 минут)

Создайте `.env` из примера и задайте в нём `ADMIN_PASSWORD` и `SECRET_KEY`, затем запустите проект:

```bash
docker compose up --build
```

Как гость: откройте главную, каталог, карточку номера и контакты. Получите пустую выдачу фильтрами. Отправьте заявку с пустыми полями, затем корректную.

Как администратор: откройте `/admin`, войдите, найдите свою заявку и подтвердите её. Вернитесь на карточку того же номера и попробуйте отправить заявку на пересекающиеся даты — получите 409.

Загляните в Swagger на `http://localhost:8000/docs`.

## Шаг 2. Прочитать backend (2,5 часа)

Порядок чтения — по направлению зависимостей, снизу вверх:

| Файл | На что смотреть |
|---|---|
| [database.py](../backend/app/database.py) | Откуда берётся строка подключения, как устроена зависимость сессии |
| [models.py](../backend/app/models.py) | Три таблицы, статусы заявки, связь заявки с номером |
| [0001_initial.py](../backend/migrations/versions/0001_initial.py) | Ограничения, которых нет в моделях, особенно `bookings_no_overlap` |
| [schemas.py](../backend/app/schemas.py) | Проверки заявки, схемы админки |
| [security.py](../backend/app/security.py) | Подпись сессии, сравнение пароля, два вида лимитов |
| [bookings.py](../backend/app/routers/bookings.py) | Порядок проверок и какой код ответа соответствует какой ошибке |
| [admin.py](../backend/app/routers/admin.py) | Вход, список с фильтром, смена статуса и обработка 409 |
| [seed.py](../backend/seed.py) | Идемпотентное наполнение |
| [conftest.py](../backend/conftest.py) | Как тесты получают собственную базу |

Сопроводительный текст — [04-backend.md](04-backend.md) и [05-data-model.md](05-data-model.md).

## Шаг 3. Прочитать frontend (2 часа)

| Файл | На что смотреть |
|---|---|
| [nuxt.config.ts](../frontend/nuxt.config.ts) | Правило прокси — самая важная строка фронта |
| [app.vue](../frontend/app/app.vue) и [error.vue](../frontend/app/error.vue) | Из чего состоит страница и что показывается при ошибке |
| [types.ts](../frontend/app/types.ts) | Контракт с API на стороне TypeScript |
| [pages/rooms/index.vue](../frontend/app/pages/rooms/index.vue) | Реактивные фильтры и обработка ошибки загрузки |
| [BookingForm.vue](../frontend/app/components/BookingForm.vue) | Состояния формы, клиентские проверки, разбор ответа сервера |
| [pages/admin/index.vue](../frontend/app/pages/admin/index.vue) | Редирект на вход, пагинация, смена статуса |

Сопроводительный текст — [06-frontend.md](06-frontend.md) и [02-architecture.md](02-architecture.md).

## Шаг 4. Прочитать инфраструктуру (30 минут)

[docker-compose.yml](../docker-compose.yml) целиком, оба Dockerfile, [.env.example](../.env.example), [07-infrastructure.md](07-infrastructure.md). Особое внимание — команде backend, флагу `-h` в healthcheck и привязке портов к `127.0.0.1`.

## Шаг 5. Сделать сквозную правку (2 часа)

Задача: добавить номеру этаж и показать его в карточке.

1. Колонка `floor` в модели `Room`.
2. Миграция через `alembic revision --autogenerate`. Колонка обязательная, а в таблице уже есть номера, поэтому задайте `server_default`.
3. Поле в `RoomOut`, в сиде и в интерфейсе `Room`.
4. Вывод на странице номера.
5. `docker compose restart backend` и проверка: номера на месте, заявки на месте, этаж отображается.
6. `docker compose exec backend pytest`: тесты накатят обе миграции на пустую базу.

Если в пункте пять заявки пропали, значит база пересоздавалась вместо миграции, и раздел про модель данных стоит перечитать.

## Топ-8 файлов проекта

1. [docker-compose.yml](../docker-compose.yml) — как всё запускается
2. [nuxt.config.ts](../frontend/nuxt.config.ts) — как фронт находит backend
3. [0001_initial.py](../backend/migrations/versions/0001_initial.py) — схема и её ограничения
4. [bookings.py](../backend/app/routers/bookings.py) — приём заявок
5. [admin.py](../backend/app/routers/admin.py) — обработка заявок
6. [security.py](../backend/app/security.py) — вход и лимиты
7. [BookingForm.vue](../frontend/app/components/BookingForm.vue) — самый сложный компонент публичной части
8. [pages/admin/index.vue](../frontend/app/pages/admin/index.vue) — рабочее место администратора

## Самопроверка

Вы освоились, если можете ответить не подглядывая:

1. Почему в FastAPI нет CORS-middleware, хотя админка работает с cookie?
2. Что гарантирует, что два администратора не подтвердят пересекающиеся заявки, и почему проверки в коде для этого мало?
3. Почему неподтверждённая заявка не закрывает даты?
4. Что происходит при старте backend и в каком порядке?
5. Почему лимит по IP обходится, и что тогда ограничивает поток спама?
6. Как тесты получают собственную базу и почему это проверяет ещё и миграции?
7. Какие два пункта из [09-tech-debt.md](09-tech-debt.md) нужно закрыть первыми при реальном трафике?
