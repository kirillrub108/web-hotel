# 10. Онбординг

План рассчитан на разработчика, который знаком с Python и Vue, но не видел этот проект. Система выросла с трёх таблиц до одиннадцати, поэтому полный проход занимает около трёх рабочих дней: запуск и обзор, backend, frontend и вёрстка. Если нужна быстрая правка, начните с [08-conventions.md](08-conventions.md).

## День 1. Запустить, потрогать, понять устройство (3–4 часа)

### 1.1. Запуск

```bash
docker compose up --build
```

Файл `.env` не обязателен: `docker-compose.yml` подставляет значения по умолчанию. Чтобы поменять настройки, скопируйте [.env.example](../.env.example) в `.env`. Backend при старте по очереди применяет миграции (`alembic upgrade head`), запускает [seed.py](../backend/seed.py) и поднимает `uvicorn`. Первый старт дольше следующих.

| Адрес | Что там |
|---|---|
| <http://localhost:3000> | Сайт |
| <http://localhost:3000/admin> | Админка (нужен вход под администратором) |
| <http://localhost:8000/docs> | Swagger, открыт только с этой машины |
| `127.0.0.1:5432` | PostgreSQL, пользователь, пароль и база — `kivana` |

Без Docker (так проверялась система в среде разработки): PostgreSQL 16 с базой `kivana`, затем в `backend/` — `pip install -r requirements.txt`, `alembic upgrade head`, `python seed.py`, `uvicorn app.main:app --reload`; во `frontend/` — `npm ci`, `npm run dev`. Backend по умолчанию ищет базу на `localhost:5432`, фронт — API на `http://localhost:8000` (`API_BASE`).

### 1.2. Демо-аккаунты (только для разработки)

Их создаёт сид при `SEED_DEMO=true` (по умолчанию). Пароли публичны: на боевом сервере ставьте `SEED_DEMO=false` и свой `ADMIN_PASSWORD`, см. [09-tech-debt.md](09-tech-debt.md).

| Роль | Email | Пароль |
|---|---|---|
| Администратор | `admin@kivana.ru` (`ADMIN_EMAIL`) | `tidy copper lantern orbit` (`ADMIN_PASSWORD`) |
| Гость, обычный | `anna@demo.kivana.ru` | `silver harbor morning tea` (`DEMO_PASSWORD`) |
| Гость, VIP | `viktor@demo.kivana.ru` | то же |
| Гость, заблокирован | `igor@demo.kivana.ru` | то же |
| Гость, чистый | `maria@demo.kivana.ru` | то же |

У Анны и Виктора есть брони, заказы услуг, уборки и персональные акции.

### 1.3. Что потрогать

1. **Как гость без входа.** Откройте главную, каталог, карточку номера. На карточке вместо формы будет кнопка «Войдите, чтобы забронировать».
2. **Регистрация.** Зарегистрируйте новый аккаунт. Без `RESEND_API_KEY` письма печатаются в лог: ссылку подтверждения возьмите из `docker compose logs backend`. До подтверждения почты форма брони закрыта.
3. **Бронь.** Войдите, выберите даты: форма покажет котировку и скажет, свободен ли номер. Короткая бронь на свободные даты подтвердится сразу; бронь с комментарием или длиннее 7 ночей уйдёт на ручной разбор (VIP — нет).
4. **Как администратор.** Войдите как `admin@kivana.ru`, на «Заявках» вкладка «На разборе» покажет причины. Подтвердите заявку, откройте «Историю». Вернитесь на тот же номер и отправьте заявку на пересекающиеся даты: получите отказ.
5. **Разделы админки.** Клиенты (сегмент, VIP, блокировка, заметка), Акции, Услуги, Заказы услуг, Уборка.
6. **Телефон.** Откройте сайт в режиме устройства на 360 px: бургер-меню, таблицы-карточки в админке, шторки вместо окон, липкая кнопка «Забронировать» на карточке номера.
7. Загляните в Swagger.

Далее прочитайте [01-overview.md](01-overview.md), [02-architecture.md](02-architecture.md) и [03-runtime-flows.md](03-runtime-flows.md). Затем [07-infrastructure.md](07-infrastructure.md): [docker-compose.yml](../docker-compose.yml) целиком, оба Dockerfile и [.env.example](../.env.example). Особое внимание — команде backend, флагу `-h` в healthcheck и привязке портов к `127.0.0.1`.

## День 2. Backend (5–6 часов)

Порядок чтения — по направлению зависимостей, снизу вверх:

| Файл | На что смотреть |
|---|---|
| [database.py](../backend/app/database.py) | Строка подключения, зависимость сессии `get_db` |
| [models.py](../backend/app/models.py) | Одиннадцать таблиц; `Booking`, `BookingEvent`, `User`, `UserSession` |
| [0001_initial.py](../backend/migrations/versions/0001_initial.py) | Ограничения, которых нет в моделях, особенно `bookings_no_overlap` |
| [0002_accounts.py](../backend/migrations/versions/0002_accounts.py) – [0005_services_housekeeping.py](../backend/migrations/versions/0005_services_housekeeping.py) | Как схема росла: аккаунты, жизненный цикл, CRM и акции, услуги и уборки |
| [passwords.py](../backend/app/passwords.py) | Argon2id, политика: от 15 символов и проверка zxcvbn без требований к составу |
| [security.py](../backend/app/security.py), [sessions.py](../backend/app/sessions.py) | Токен и его sha256, лимиты запросов, `require_user`, `require_verified_user`, `require_admin` |
| [hotel_time.py](../backend/app/hotel_time.py) | «Сегодня» только по часам отеля |
| [booking_rules.py](../backend/app/booking_rules.py) | Цена, авто-решения и их причины |
| [booking_lifecycle.py](../backend/app/booking_lifecycle.py) | Таблица переходов, `change_status`, `submit_booking`, ленивая просрочка |
| [routers/bookings.py](../backend/app/routers/bookings.py), [routers/account.py](../backend/app/routers/account.py), [routers/admin.py](../backend/app/routers/admin.py) | Порядок проверок и коды ответов; единственный путь смены статуса |
| [schemas.py](../backend/app/schemas.py) | Проверки входных данных и формы ответов |

Сопроводительный текст — [04-backend.md](04-backend.md) и [05-data-model.md](05-data-model.md).

Вторая половина дня: [promos.py](../backend/app/promos.py), [room_service.py](../backend/app/room_service.py), [housekeeping.py](../backend/app/housekeeping.py), [crm.py](../backend/app/crm.py), [mail.py](../backend/app/mail.py), [seed.py](../backend/seed.py) (идемпотентное наполнение) и [conftest.py](../backend/conftest.py): как тесты получают собственную базу и откатывают транзакцию. Запустите `docker compose exec backend pytest`: 346 тестов накатят все пять миграций на пустую базу `kivana_test`.

## День 3. Frontend и вёрстка (5–6 часов)

| Файл | На что смотреть |
|---|---|
| [nuxt.config.ts](../frontend/nuxt.config.ts) | Правило прокси `/api/**` — самая важная строка фронта; `viewport-fit=cover` |
| [app.vue](../frontend/app/app.vue), [error.vue](../frontend/app/error.vue) | Загрузка пользователя до отрисовки, липкий подвал, страница ошибки |
| [middleware/auth.global.ts](../frontend/app/middleware/auth.global.ts), [useCurrentUser.ts](../frontend/app/composables/useCurrentUser.ts) | Доступ по ролям и единственный источник состояния |
| [types.ts](../frontend/app/types.ts), [utils/](../frontend/app/utils/) | Контракт с API, словари статусов, форматирование дат и денег |
| [BookingForm.vue](../frontend/app/components/BookingForm.vue) | Живая котировка, промокод, защита от устаревшего ответа |
| [pages/rooms/[slug].vue](../frontend/app/pages/rooms/[slug].vue) | Четыре состояния блока брони, липкая кнопка с `IntersectionObserver` |
| [pages/account/bookings/[id].vue](../frontend/app/pages/account/bookings/[id].vue) | Отмена, история, заказ услуг, выбор времени уборки |
| [pages/admin/index.vue](../frontend/app/pages/admin/index.vue) | Таблица-карточка, вкладки, диалог решения, история |
| [main.css](../frontend/app/assets/css/main.css) | Раздел «Адаптивность»: брейкпоинты 640 и 1024, таблицы, диалоги, тач-цели |

Сопроводительный текст — [06-frontend.md](06-frontend.md), особенно раздел 5 «Адаптивная вёрстка». Откройте админку на 360, 768 и 1280 px и посмотрите, как одна и та же таблица меняет вид.

## Сквозная задача (2 часа)

Добавить номеру этаж и показать его на странице номера.

1. Колонка `floor` в модели `Room`.
2. Миграция: `alembic revision --autogenerate --rev-id 0006 -m "room floor"`. Идентификаторы ревизий в проекте — номера `0001`–`0005`, продолжаем счёт. Колонка обязательная, а номера уже есть, поэтому задайте `server_default`.
3. Поле в `RoomOut`, в сиде и в интерфейсе `Room` ([types.ts](../frontend/app/types.ts)).
4. Вывод на [странице номера](../frontend/app/pages/rooms/[slug].vue) тегом `.tag` рядом с площадью.
5. `docker compose restart backend` и проверка: номера, брони и заказы на месте, этаж отображается.
6. `docker compose exec backend pytest`: тесты накатят все миграции на пустую базу.

Если в пункте 5 данные пропали, значит база пересоздавалась вместо миграции: перечитайте [05-data-model.md](05-data-model.md).

Дополнительно, для вёрстки: добавьте колонку в таблицу [admin/rooms/index.vue](../frontend/app/pages/admin/rooms/index.vue) (не забудьте `data-label`) и проверьте результат на 360, 768 и 1280 px.

## Что можно временно игнорировать

| Что | Почему |
|---|---|
| `frontend/.nuxt/`, `.output/`, `node_modules/`, `backend/**/__pycache__/` | Генерируемое и кэш, в git не входит |
| [mail_templates.py](../backend/app/mail_templates.py) | Тексты писем; смотрите, когда правите письма |
| Формы-диалоги акций, услуг и номеров | Повторяют один шаблон `AdminActionDialog` |
| Разделы 3–9 и 11 [00-specification.md](00-specification.md) | Сохранили текст версии 1.0 и частично расходятся с кодом, см. [09-tech-debt.md](09-tech-debt.md) |
| `public/images/rooms/*.svg` | Плейсхолдеры вместо фотографий |

## Топ-10 файлов проекта

1. [docker-compose.yml](../docker-compose.yml) — как всё запускается и какие переменные читает backend
2. [nuxt.config.ts](../frontend/nuxt.config.ts) — как фронт находит backend, `viewport-fit=cover`
3. [0001_initial.py](../backend/migrations/versions/0001_initial.py) — схема и ограничение `bookings_no_overlap`
4. [booking_lifecycle.py](../backend/app/booking_lifecycle.py) — единственный путь смены статуса брони
5. [booking_rules.py](../backend/app/booking_rules.py) — цена и авто-решения
6. [sessions.py](../backend/app/sessions.py) и [security.py](../backend/app/security.py) — вход, роли, лимиты
7. [seed.py](../backend/seed.py) — справочники, администратор, демо-данные
8. [auth.global.ts](../frontend/app/middleware/auth.global.ts) — доступ к кабинету и админке
9. [BookingForm.vue](../frontend/app/components/BookingForm.vue) — самый сложный компонент публичной части
10. [main.css](../frontend/app/assets/css/main.css) — переменные, адаптивность, общие классы

## Самопроверка

Вы освоились, если можете ответить не подглядывая:

1. Почему в FastAPI нет CORS-middleware, хотя сайт работает с cookie?
2. Что гарантирует, что две подтверждённые брони не пересекутся, и почему проверки в коде для этого мало?
3. Почему заявка на рассмотрении не закрывает даты?
4. Что происходит при старте backend и в каком порядке? Что будет с паролем администратора при втором запуске?
5. Где хранится токен сессии и что лежит в таблице `sessions`? Почему перезапуск backend гостей не разлогинивает?
6. Какое решение принимает система сама, а какое остаётся администратору, и где это написано в коде?
7. Почему лимит по IP обходится, и что тогда ограничивает поток спама?
8. Как тесты получают собственную базу и почему это проверяет ещё и миграции?
9. Что произойдёт на телефоне со строкой таблицы, если у `td` нет `data-label`, и почему `td.actions` на десктопе не flex?
10. Какие три пункта из [09-tech-debt.md](09-tech-debt.md) нужно закрыть первыми перед приёмом реальных гостей?
