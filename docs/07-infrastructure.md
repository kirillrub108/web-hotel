# 07. Инфраструктура

Всё описано в [docker-compose.yml](../docker-compose.yml). Сайт запускается без файла `.env`; для входа в админку нужен `ADMIN_PASSWORD`.

## Сервисы

| Сервис | Образ | Порт | Доступен из сети | Зависит от |
|---|---|---|---|---|
| `db` | `postgres:16-alpine` | 5432 | нет, только `127.0.0.1` | — |
| `backend` | сборка из [backend/Dockerfile](../backend/Dockerfile) | 8000 | нет, только `127.0.0.1` | `db` в состоянии healthy |
| `frontend` | сборка из [frontend/Dockerfile](../frontend/Dockerfile) | 3000 | да | `backend` |

Гостю нужен только порт 3000: API он получает через прокси Nuxt. Порты базы и backend привязаны к `127.0.0.1`. Разработчик на этой машине открывает Swagger и psql, а из сети база и API напрямую недоступны, и обратиться к API в обход прокси нельзя.

### db

Данные лежат в именованном томе `db-data` и переживают `docker compose down`, но не `down -v`.

Healthcheck вызывает `pg_isready -h 127.0.0.1` каждые пять секунд, до двенадцати попыток. Флаг `-h` включает проверку по TCP. Без него `pg_isready` идёт через unix-сокет и отвечает «готово» ещё во время первичной инициализации тома. В этот момент временный сервер не слушает TCP, и backend упал бы на первом подключении.

### backend

```yaml
command: sh -c "alembic upgrade head && python seed.py && uvicorn app.main:app --reload --host 0.0.0.0"
```

Миграции, затем наполнение пустой базы, затем сервер. Если миграция или сид упадут, uvicorn не запустится, и причина будет видна в логах.

`FORWARDED_ALLOW_IPS: "*"` разрешает uvicorn брать IP клиента из `X-Forwarded-For`. Порт 8000 из сети закрыт, поэтому напрямую этот заголовок backend никто не пришлёт. Но dev-сервер Nuxt пропускает заголовок, присланный клиентом, так что через прокси IP всё равно подделывается. Как с этим справляется ограничение частоты, описано в [04-backend.md](04-backend.md).

Каталог `./backend` смонтирован в `/app`, флаг `--reload` перезапускает сервер при правке кода.

### frontend

```yaml
volumes:
  - ./frontend:/app
  - /app/node_modules
```

Первое монтирование подключает исходники с хоста и заодно перекрывает `node_modules` из образа. Второе, анонимный том, возвращает содержимое образа поверх этого пути. Без него контейнер остался бы без зависимостей. Docker создаёт на хосте пустой каталог `frontend/node_modules` как точку монтирования, он в `.gitignore`.

`API_BASE=http://backend:8000` задаёт адрес для прокси, имя `backend` резолвит DNS сети Compose. `WATCH_POLLING` включает опрос файлов dev-сервером.

## Переменные окружения

| Переменная | По умолчанию | Назначение |
|---|---|---|
| `POSTGRES_USER` | `hotel` | Пользователь базы |
| `POSTGRES_PASSWORD` | `hotel` | Пароль базы |
| `POSTGRES_DB` | `hotel` | Имя базы |
| `ADMIN_USERNAME` | `admin` | Логин администратора |
| `ADMIN_PASSWORD` | пусто | Пароль администратора; пустой отключает вход |
| `SECRET_KEY` | генерируется при старте | Ключ подписи cookie сессии |
| `COOKIE_SECURE` | `false` | Отправлять cookie сессии только по HTTPS |
| `WATCH_POLLING` | `true` | Опрос файлов в dev-сервере Nuxt |
| `DATABASE_URL` | собирается в compose | Строка подключения SQLAlchemy |
| `API_BASE` | задаётся в compose | Адрес backend для прокси |

Синтаксис `${VAR:-default}` подставляет значение по умолчанию, если переменной нет. [.env.example](../.env.example) описывает все переменные с комментариями.

Без `SECRET_KEY` ключ генерируется случайно при каждом старте процесса. Это безопасно, но каждый перезапуск backend, в том числе автоматический после правки кода, разлогинивает администратора. Для постоянной работы ключ задаётся в `.env`.

## Образы

Оба Dockerfile одностадийные: это dev-сборка. Backend — `python:3.12-slim` и `pip install`, frontend — `node:24-alpine` и `npm ci`. Манифест зависимостей копируется отдельным слоем перед исходниками, поэтому правка кода не переустанавливает зависимости.

`npm ci` требует `package-lock.json`, поэтому lock-файл лежит в репозитории. Версия Node в образе совпадает по мажорной линейке с той, в которой lock-файл сгенерирован.

## Команды

```bash
docker compose up --build
```

```bash
docker compose logs -f backend
```

```bash
docker compose exec backend pytest
```

```bash
docker compose exec backend alembic check
```

```bash
docker compose exec db psql -U hotel -d hotel -c "select id, guest_name, status from bookings order by id desc limit 20;"
```

```bash
docker compose down -v
```

## Переход со старой схемы

Первая версия проекта создавала таблицы через `create_all`, без таблицы `alembic_version`. На таком томе `alembic upgrade head` упадёт с ошибкой «relation already exists». Том нужно пересоздать один раз: `docker compose down -v && docker compose up --build`. Если в старой базе есть заявки, которые нужно сохранить, выгрузите их до пересоздания тома: `docker compose exec db pg_dump -U hotel -t bookings --data-only hotel > bookings.sql`.

## Что это не покрывает

Контейнеры работают в режиме разработки, продакшен-сборки нет. Нет reverse proxy, TLS, политики перезапуска контейнеров, резервного копирования тома и мониторинга. Перечень с последствиями — в [09-tech-debt.md](09-tech-debt.md).

## Вопросы на понимание

1. Почему порт 8000 привязан к `127.0.0.1` и как это связано с `FORWARDED_ALLOW_IPS`?
2. Что случится при первом запуске этой версии на томе от предыдущей и как это исправить?
3. Почему администратора выкидывает из админки после каждой правки кода backend, и как это убрать?
