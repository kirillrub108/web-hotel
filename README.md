# Kivana — сайт гостиницы

> Сайт гостиницы: каталог номеров, аккаунты гостей, бронирование с авто-решениями, личный кабинет, услуги и уборки, админка с CRM. Backend отдаёт JSON API, Nuxt рендерит SSR-страницы, всё поднимается одной командой в Docker.

![Python](https://img.shields.io/badge/python-3.12-3776AB)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688)
![Nuxt](https://img.shields.io/badge/Nuxt-4-00DC82)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1)
![Docker Compose](https://img.shields.io/badge/Docker%20Compose-3%20сервиса-2496ED)

## Содержание

- [О проекте](#о-проекте)
- [Стек технологий](#стек-технологий)
- [Возможности](#возможности)
- [Быстрый старт](#быстрый-старт)
- [Демо-аккаунты](#демо-аккаунты)
- [Конфигурация](#конфигурация)
- [Почта](#почта)
- [Миграции](#миграции)
- [API](#api)
- [Структура проекта](#структура-проекта)
- [Тесты](#тесты)
- [Разработка](#разработка)
- [Contributing](#contributing)
- [Лицензия](#лицензия)

## О проекте

Учебный проект: сайт небольшой городской гостиницы. Гость смотрит номера, регистрируется, подтверждает почту и бронирует. Правила авто-решений либо подтверждают бронь сразу, либо оставляют заявку на ручную проверку; администратор разбирает такие заявки, ведёт клиентов (CRM), акции, услуги и расписание уборок. Оплаты на сайте нет: услуги оплачиваются на ресепшене.

Решения и их обоснование собраны в [спецификации](docs/00-specification.md) (раздел 14), устройство — в [docs/](docs/README.md).

## Стек технологий

| Слой | Технология |
|---|---|
| Backend | Python 3.12, FastAPI 0.115, SQLAlchemy 2.0 (sync), Pydantic v2, Alembic 1.20, Argon2id, zxcvbn |
| Frontend | Nuxt 4 (SSR), Vue 3, TypeScript, обычный CSS с переменными, без UI-китов |
| База данных | PostgreSQL 16 |
| Почта | Resend (HTTP API) или вывод в лог |
| Инфраструктура | Docker Compose, три сервиса |

## Возможности

- Каталог из шести категорий номеров с фильтрами по вместимости и цене; расчёт стоимости с промокодом.
- Аккаунты гостей: регистрация, подтверждение почты, сброс пароля, профиль. Бронь доступна только с подтверждённой почтой.
- Политика паролей по NIST SP 800-63B-4: минимум 15 символов и проверка по словарю, без требований к составу.
- Бронь со строгой машиной статусов (`pending → confirmed / declined / cancelled`, `confirmed → cancelled`), история событий и письма на каждый переход.
- Авто-решения: типовая бронь подтверждается сразу, спорная уходит администратору с перечнем причин. Заявки без решения до даты заезда отклоняются автоматически.
- Защита от двойного бронирования: пересечение подтверждённых броней запрещено ограничением PostgreSQL.
- Личный кабинет: брони, отмена, заказы услуг и еды в номер, выбор времени уборки, персональные предложения.
- Админка: заявки, клиенты (сегменты, VIP, блокировка, заметки), акции и промокоды, каталог услуг, заказы услуг, расписание уборок, редактирование цены, описания и доступности номеров.
- Адаптивная вёрстка: телефон (от 360 px), планшет, компьютер. Бургер-меню, таблицы админки на экранах уже 1024 px превращаются в карточки, модалки на телефоне — шторки на всю ширину, липкая кнопка «Забронировать» на карточке номера, поля не меньше 16 px, тач-цели не меньше 44 px.
- Ограничение частоты заявок, входа и регистрации: по IP и общий потолок на весь сайт.
- Сессии хранятся в БД (в таблице только sha256 токена), Swagger на `/docs`, изображения локальные.

## Быстрый старт

### Требования

- Docker с плагином Compose

Python и Node.js на хост ставить не нужно.

### Запуск

```bash
git clone <url-репозитория>
```

```bash
cd web-hotel && docker compose up --build
```

Сайт работает без файла `.env`: все значения по умолчанию подставляет `docker-compose.yml`. Чтобы поменять настройки, скопируйте пример:

```bash
cp .env.example .env
```

| Адрес | Что там |
|---|---|
| <http://localhost:3000> | сайт гостиницы |
| <http://localhost:3000/admin> | админка (под учётной записью администратора) |
| <http://localhost:8000/docs> | Swagger, открыт только с этой машины |
| `127.0.0.1:5432` | PostgreSQL, открыт только с этой машины |

При старте backend по очереди применяет миграции (`alembic upgrade head`), запускает сид и поднимает сервер. Сид наполняет только пустую базу: повторный запуск данные не дублирует и пароль существующего пользователя не меняет.

<!-- code-readme:keep -->
### Сброс демо-данных

Остановить сервисы и удалить том с базой (данные пропадут, при следующем запуске сид создаст их заново):

```bash
docker compose down -v
```

Если проект запускался раньше под именем `web-hotel`, старый том останется осиротевшим и займёт место. Посмотреть и удалить его:

```bash
docker volume ls | grep web-hotel_
```

```bash
docker volume rm web-hotel_db-data
```

Проект теперь называется `kivana` (`name:` в `docker-compose.yml`), том нового запуска — `kivana_db-data`.
<!-- /code-readme:keep -->

## Демо-аккаунты

<!-- code-readme:keep -->
> **Только для разработки.** Демо-данные создаёт сид при `SEED_DEMO=true` (по умолчанию). На боевом сервере поставьте `SEED_DEMO=false` и смените `ADMIN_PASSWORD`: пароли ниже публичны.

| Роль | Email | Пароль | Что умеет |
|---|---|---|---|
| Администратор | `admin@kivana.ru` (`ADMIN_EMAIL`) | `tidy copper lantern orbit` (`ADMIN_PASSWORD`) | Вся админка |
| Гость, обычный | `anna@demo.kivana.ru` | `silver harbor morning tea` (`DEMO_PASSWORD`) | Кабинет, брони, заказы услуг, уборки |
| Гость, VIP | `viktor@demo.kivana.ru` | то же | Авто-подтверждение длинных и дорогих броней |
| Гость, заблокирован | `igor@demo.kivana.ru` | то же | Новые заявки отклоняются автоматически |
| Гость, обычный | `maria@demo.kivana.ru` | то же | Чистый аккаунт |

Все демо-гости с подтверждённой почтой; у Анны и Виктора есть брони, заказы услуг, уборки и персональные акции. Пароли должны проходить политику паролей, иначе backend не запустится.
<!-- /code-readme:keep -->

## Конфигурация

Все переменные необязательны. Комментарии — в `.env.example`.

| Переменная | По умолчанию | Описание |
|---|---|---|
| `POSTGRES_USER` | `kivana` | Пользователь PostgreSQL |
| `POSTGRES_PASSWORD` | `kivana` | Пароль PostgreSQL |
| `POSTGRES_DB` | `kivana` | Имя базы |
| `APP_BASE_URL` | `http://localhost:3000` | Адрес сайта для ссылок в письмах |
| `MAIL_BACKEND` | пусто | `resend`, `console` или `memory` (тесты); пусто — `resend` при заданном `RESEND_API_KEY`, иначе `console` |
| `RESEND_API_KEY` | пусто | Ключ API Resend |
| `MAIL_FROM` | `Kivana <no-reply@kivana.ru>` | Отправитель; домен должен быть подтверждён в Resend |
| `ADMIN_EMAIL` | `admin@kivana.ru` | Email администратора, которого создаёт сид |
| `ADMIN_PASSWORD` | `tidy copper lantern orbit` | Пароль администратора; должен проходить политику паролей |
| `SEED_DEMO` | `true` | Создавать демо-клиентов, брони, заказы, уборки и акции; на боевом сервере `false` |
| `DEMO_PASSWORD` | `silver harbor morning tea` | Общий пароль демо-гостей |
| `PASSWORD_MIN_LENGTH` | `15` | Минимальная длина пароля (backend и подсказка на сайте) |
| `SESSION_TTL_GUEST_DAYS` | `14` | Срок сессии гостя, дней |
| `SESSION_TTL_ADMIN_HOURS` | `12` | Срок сессии администратора, часов |
| `COOKIE_SECURE` | `false` | `true`, когда сайт открывается по HTTPS |
| `HOTEL_TZ` | `Europe/Moscow` | Часовой пояс отеля: «сегодня», просрочка заявок, дедлайн отмены |
| `FREE_CANCEL_HOURS` | `48` | За сколько часов до заезда гость может отменить бронь онлайн |
| `AUTO_CONFIRM_MAX_NIGHTS` | `7` | Дольше — ручная проверка (не для VIP) |
| `AUTO_CONFIRM_MAX_TOTAL` | `60000` | Сумма выше при отсутствии проживаний — ручная проверка (не для VIP), ₽ |
| `AUTO_CONFIRM_MAX_LEAD_DAYS` | `180` | Заезд дальше — ручная проверка (не для VIP), дней |
| `MAX_STAY_NIGHTS` | `30` | Максимальная длина брони, ночей |
| `MAX_LEAD_DAYS` | `365` | На сколько дней вперёд можно бронировать |
| `MAX_PENDING_PER_CLIENT` | `3` | Заявок на рассмотрении у одного клиента одновременно |
| `ADMIN_NOTIFY_EMAIL` | пусто | Куда писать о заявках на ручной проверке; пусто — не писать |
| `ROOM_SERVICE_HOURS` | `08:00-23:00` | Часы приёма заказов еды в номер (по `HOTEL_TZ`) |
| `WATCH_POLLING` | `true` | Опрос файлов dev-сервером Nuxt; нужен на Windows |

Прочее: `PROMO_MAX_PERCENT` (по умолчанию `50`) — максимальная процентная скидка; backend читает её из окружения, но `docker-compose.yml` её не передаёт, поэтому для смены значения добавьте переменную в секцию `backend.environment`. `NUXT_PUBLIC_PASSWORD_MIN_LENGTH` во frontend compose берёт из `PASSWORD_MIN_LENGTH`.

## Почта

<!-- code-readme:keep -->
**В разработке** (по умолчанию, `MAIL_BACKEND=console` или пусто без ключа) письма не уходят: тема, текст и ссылки (подтверждение почты, сброс пароля) печатаются в лог backend:

```bash
docker compose logs -f backend
```

**Подключение Resend** (боевая отправка):

1. Зарегистрируйтесь на [resend.com](https://resend.com) и в разделе Domains добавьте домен `kivana.ru`.
2. Resend покажет DNS-записи: SPF и DKIM (TXT) и MX-записи для отправки. Внесите их у регистратора домена как есть и дождитесь статуса Verified.
3. Создайте ключ в разделе API Keys.
4. Задайте в `.env`: `RESEND_API_KEY=<ключ>` и `MAIL_FROM="Kivana <no-reply@kivana.ru>"` (адрес на подтверждённом домене). `MAIL_BACKEND` можно оставить пустым — при ключе выберется `resend`.
5. Перезапустите backend: `docker compose up -d backend`.

Без подтверждённого домена Resend доставляет письма только на адрес владельца аккаунта Resend. Для тестов используйте адрес `delivered@resend.dev` — тестовый адрес Resend, на который письмо всегда «доставляется» (зарегистрируйте на него гостя или задайте его в `ADMIN_NOTIFY_EMAIL`).

Ошибка отправки пишется в лог backend и не ломает ни регистрацию, ни смену статуса брони; повторных попыток нет.
<!-- /code-readme:keep -->

## Миграции

<!-- code-readme:keep -->
Схема БД ведётся миграциями Alembic (`backend/migrations/versions/`: `0001_initial` … `0005_services_housekeeping`). Они применяются автоматически при старте backend — командой `alembic upgrade head` перед сидом.

Создать новую миграцию после изменения моделей в `backend/app/models.py`:

```bash
docker compose exec backend alembic revision --autogenerate -m "описание изменения"
```

Проверьте сгенерированный файл в `backend/migrations/versions/` перед коммитом: autogenerate не видит CHECK-ограничения и `bookings_no_overlap`, их пишут в миграции вручную. Применить сразу (без перезапуска) — `docker compose exec backend alembic upgrade head`, сверить модели с базой — `docker compose exec backend alembic check`. Откат на одну версию — `alembic downgrade -1`.
<!-- /code-readme:keep -->

## API

Все маршруты — под префиксом `/api`. Полное описание со схемами — в Swagger (`/docs`).

| Группа | Маршруты |
|---|---|
| Публичные | `GET /api/health`, `GET /api/hotel`, `GET /api/rooms`, `GET /api/rooms/{slug}`, `GET /api/rooms/{slug}/quote`, `GET /api/services` |
| Аккаунт | `POST /api/auth/register`, `/login`, `/logout`, `/verify-email`, `/resend-verification`, `/forgot-password`, `/reset-password`, `/change-password`; `GET /api/auth/me` |
| Бронь | `POST /api/bookings` |
| Кабинет | `GET/PATCH /api/account/profile`, `GET /api/account/promos`, `GET /api/account/bookings[/{id}]`, `POST /api/account/bookings/{id}/cancel`, `POST /api/account/bookings/{id}/service-orders`, `POST /api/account/service-orders/{id}/cancel`, `PATCH /api/account/housekeeping/{id}` |
| Админка: заявки | `GET /api/admin/bookings[/{id}]`, `POST /api/admin/bookings/{id}/confirm`, `/decline`, `/cancel` |
| Админка: клиенты и акции | `GET /api/admin/clients[/{id}]`, `PATCH /api/admin/clients/{id}`, `GET/POST /api/admin/promos`, `PATCH/DELETE /api/admin/promos/{id}` |
| Админка: услуги и уборки | `GET/POST /api/admin/services`, `PATCH/DELETE /api/admin/services/{id}`, `GET /api/admin/service-orders`, `PATCH /api/admin/service-orders/{id}`, `GET /api/admin/housekeeping`, `PATCH /api/admin/housekeeping/{id}` |
| Админка: номера | `GET /api/admin/rooms`, `PATCH /api/admin/rooms/{id}` |

Недопустимый переход статуса брони — `409`, превышение частоты — `429`, ошибки данных — `422`.

```bash
curl "http://localhost:8000/api/rooms?capacity=4&max_price=13000"
```

## Структура проекта

```
web-hotel/
├── backend/
│   ├── app/
│   │   ├── main.py               # приложение FastAPI, роутеры, /api/health
│   │   ├── models.py             # пользователи, сессии, номера, брони, события, акции, услуги, уборки
│   │   ├── schemas.py            # схемы Pydantic и проверки данных
│   │   ├── booking_rules.py      # цена, правила авто-решений, коды причин
│   │   ├── booking_lifecycle.py  # машина статусов, создание брони, ленивая просрочка
│   │   ├── crm.py, promos.py     # сегменты клиентов, акции и промокоды
│   │   ├── room_service.py       # заказы услуг и еды в номер
│   │   ├── housekeeping.py       # расписание уборок
│   │   ├── passwords.py          # политика паролей и Argon2id
│   │   ├── sessions.py           # сессии в БД
│   │   ├── security.py           # ограничение частоты запросов
│   │   ├── mail.py, mail_templates.py  # отправка и шаблоны писем
│   │   ├── hotel_time.py         # время отеля (HOTEL_TZ)
│   │   └── routers/              # auth, account, hotel, rooms, services, bookings, admin*
│   ├── migrations/               # Alembic: env.py и версии схемы
│   ├── tests/                    # 10 файлов тестов
│   ├── conftest.py               # отдельная тестовая база и сброс данных между тестами
│   ├── seed.py                   # справочники, администратор, демо-данные
│   ├── alembic.ini, requirements.txt, Dockerfile
├── frontend/
│   ├── app/
│   │   ├── app.vue               # шапка, страница, подвал
│   │   ├── assets/css/main.css   # переменные, брейкпоинты 640/1024, общие классы
│   │   ├── components/           # шапка и подвал, навигации, формы, диалоги, таймлайн
│   │   ├── pages/                # публичные страницы, account/, admin/
│   │   ├── composables/, middleware/, utils/, types.ts
│   ├── public/                   # favicon и изображения номеров
│   ├── nuxt.config.ts            # прокси /api/** на backend, viewport
│   └── Dockerfile
├── docs/                         # спецификация и инженерная документация
├── docker-compose.yml
└── .env.example
```

## Тесты

```bash
docker compose exec backend pytest
```

346 тестов (десять файлов в `backend/tests/`) покрывают каталог, регистрацию и вход, политику паролей, машину статусов и авто-решения, CRM и акции, услуги и уборки, сид и админку номеров. Тесты работают в отдельной базе `kivana_test` на том же сервере: миграции накатываются один раз, изоляция между тестами — откат транзакции (savepoint); рабочая база не затрагивается. Письма в тестах копятся в памяти (`MAIL_BACKEND=memory`), сид идёт без демо-данных.

Вёрстку тесты не проверяют: адаптивность сверялась вручную по скриншотам на 360, 768 и 1280 px.

## Разработка

Оба сервиса работают в dev-режиме, исходники смонтированы в контейнеры. Uvicorn перезапускается по `--reload`, Nuxt пересобирает страницы на лету. Bind-mount на Windows не отдаёт события inotify, поэтому dev-сервер Nuxt опрашивает файлы; на Linux и macOS опрос можно выключить через `WATCH_POLLING=false`.

Данные гостиницы, номеров и услуг задаются в `backend/seed.py` и попадают только в пустую базу. Как менять схему — в разделе [Миграции](#миграции).

Вёрстка: мобильные стили — основа, раскрываются через `@media (min-width: 640px)` и `(min-width: 1024px)`; таблицы-карточки и размеры тач-целей — переопределения `max-width: 1023.98px`. Цвета, отступы и радиусы — переменные в `main.css`.

## Contributing

1. Форкните репозиторий
2. Создайте ветку: `git checkout -b feature/<название>`
3. Закоммитьте изменения и откройте Pull Request

Перед PR убедитесь, что тесты проходят локально.

## Лицензия

<!-- TODO(code-readme): в репозитории нет файла LICENSE — добавьте его и укажите здесь лицензию -->
