# Тихая гавань — сайт гостиницы

> Учебный проект: витрина отеля, каталог номеров и заявки на бронирование. Backend отдаёт JSON API, Nuxt рендерит SSR-страницы, всё поднимается одной командой.

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
- [Конфигурация](#конфигурация)
- [API](#api)
- [Структура проекта](#структура-проекта)
- [Тесты](#тесты)
- [Разработка](#разработка)
- [Contributing](#contributing)
- [Лицензия](#лицензия)

## О проекте

Сайт небольшой городской гостиницы: главная страница, каталог номеров с фильтрами, карточка номера с формой заявки и страница контактов. Заявка — это именно заявка: оплаты, статусов и личного кабинета нет, администратор перезванивает гостю сам.

Проект написан как показательный: три сущности в базе, плоская структура без лишних слоёв, минимум зависимостей. Его удобно читать вслух и объяснять по файлам.

## Стек технологий

| Слой | Технология |
|---|---|
| Backend | Python 3.12, FastAPI 0.115, SQLAlchemy 2.0 (sync), Pydantic v2 |
| Frontend | Nuxt 4 (SSR), Vue 3, TypeScript |
| База данных | PostgreSQL 16 |
| Инфраструктура | Docker Compose, три сервиса |

## Возможности

- Каталог из шести категорий номеров с фильтрами по вместимости и максимальной цене; фильтрация выполняется запросом на сервер, а не в браузере.
- Карточка номера с описанием, площадью, списком удобств и формой заявки: валидация на клиенте и повторная проверка на сервере.
- SSR: страницы приходят из Nuxt уже с данными, поэтому работают без JavaScript и индексируются поисковиками.
- Идемпотентный сид: повторный запуск не дублирует данные, `docker compose down -v` даёт чистый старт.
- Swagger из коробки на `/docs`.
- Изображения — локальные SVG-плейсхолдеры, внешние CDN не используются, проект работает офлайн.

## Быстрый старт

### Требования

- Docker с плагином Compose

Ставить Python и Node.js на хост не нужно: оба сервиса собираются в контейнерах.

### Запуск

```bash
git clone https://github.com/kirillrub108/web-hotel.git
```

```bash
cd web-hotel && docker compose up --build
```

Через минуту доступны:

| Адрес | Что там |
|---|---|
| <http://localhost:3000> | сайт гостиницы |
| <http://localhost:8000/docs> | Swagger |
| <http://localhost:8000/api/rooms> | JSON API |
| `localhost:5432` | PostgreSQL |

Файл `.env` создавать не нужно: `docker-compose.yml` подставляет значения по умолчанию через `${VAR:-default}`.

Остановить и удалить данные:

```bash
docker compose down -v
```

## Конфигурация

`.env.example` нужен только как справка. Скопируйте его в `.env`, если хотите поменять учётные данные базы.

| Переменная | Где задаётся | По умолчанию | Описание |
|---|---|---|---|
| `POSTGRES_USER` | `.env` или окружение | `hotel` | Пользователь PostgreSQL |
| `POSTGRES_PASSWORD` | `.env` или окружение | `hotel` | Пароль PostgreSQL |
| `POSTGRES_DB` | `.env` или окружение | `hotel` | Имя базы |
| `DATABASE_URL` | `docker-compose.yml` | собирается из трёх переменных выше | Строка подключения SQLAlchemy |
| `API_BASE` | `docker-compose.yml` | `http://localhost:8000` | Адрес backend для nitro-прокси |

## API

Все маршруты живут под префиксом `/api`.

| Метод | Маршрут | Описание |
|---|---|---|
| `GET` | `/api/health` | Проверка живости |
| `GET` | `/api/hotel` | Данные гостиницы |
| `GET` | `/api/rooms` | Список номеров, query-фильтры `capacity` и `max_price` |
| `GET` | `/api/rooms/{slug}` | Один номер, `404` если такого нет |
| `POST` | `/api/bookings` | Создание заявки, `201` при успехе |

Примеры:

```bash
curl http://localhost:8000/api/rooms
```

```bash
curl "http://localhost:8000/api/rooms?capacity=4&max_price=13000"
```

```bash
curl -X POST http://localhost:8000/api/bookings -H "Content-Type: application/json" -d '{"room_id":1,"guest_name":"Ivan Petrov","phone":"+79001234567","email":"ivan@example.com","check_in":"2026-10-10","check_out":"2026-10-14","guests":1,"comment":null}'
```

Ошибки заявки: `422` на некорректном теле (дата выезда не позже заезда, пустое имя, неверная почта), `404` на несуществующем номере, `400` на недоступном номере или превышении вместимости.

## Структура проекта

```
web-hotel/
├── backend/
│   ├── app/
│   │   ├── main.py             # приложение FastAPI, подключение роутеров, /api/health
│   │   ├── database.py         # engine, сессия, декларативная база
│   │   ├── models.py           # Hotel, Room, Booking
│   │   ├── schemas.py          # схемы Pydantic и валидация заявки
│   │   └── routers/            # hotel.py, rooms.py, bookings.py
│   ├── tests/test_api.py       # тесты API через TestClient
│   ├── conftest.py             # кладёт корень backend в sys.path для pytest
│   ├── seed.py                 # создание таблиц и наполнение базы
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── app/
│   │   ├── app.vue             # шапка, страница, подвал
│   │   ├── types.ts            # типы Hotel и Room
│   │   ├── assets/css/main.css # палитра, отступы, базовые компоненты
│   │   ├── components/         # AppHeader, AppFooter, RoomCard, BookingForm
│   │   └── pages/              # index, contacts, rooms/index, rooms/[slug]
│   ├── public/images/rooms/    # SVG-плейсхолдеры номеров
│   ├── nuxt.config.ts          # прокси /api/** на backend, подключение стилей
│   └── Dockerfile
├── docker-compose.yml
└── .env.example
```

## Тесты

```bash
docker compose exec backend pytest
```

Семь тестов на `TestClient`: живость, список номеров, фильтр по цене, пустая выдача фильтра, номер по slug, `404` на несуществующем slug, `422` на некорректной заявке. Отдельная тестовая база не поднимается, тесты работают с тем же PostgreSQL и ничего в нём не создают.

## Разработка

Оба сервиса запускаются в dev-режиме, исходники смонтированы в контейнеры: uvicorn перезапускается по `--reload`, Nuxt пересобирает страницы на лету.

Bind-mount на Windows не отдаёт события inotify, поэтому в `nuxt.config.ts` включён опрос файлов (`usePolling`). На Linux и macOS его можно выключить — там работает обычное отслеживание, и опрос только тратит процессорное время.

Наполнить базу вручную, если это понадобилось отдельно от старта:

```bash
docker compose exec backend python seed.py
```

## Contributing

1. Форкните репозиторий
2. Создайте ветку: `git checkout -b feature/<название>`
3. Закоммитьте изменения и откройте Pull Request

Перед PR убедитесь, что тесты проходят локально.

## Лицензия

<!-- TODO(code-readme): в репозитории нет файла LICENSE — добавьте его и укажите здесь лицензию -->
