# 07. Инфраструктура

Всё описано в [docker-compose.yml](../docker-compose.yml), проект называется `kivana` (`name:` в начале файла). Сайт запускается без файла `.env`: все значения по умолчанию подставляет compose, а входить можно демо-аккаунтами из сида (список — в [README.md](../README.md#демо-аккаунты)).

## Сервисы

| Сервис | Образ | Порт | Доступен из сети | Зависит от |
|---|---|---|---|---|
| `db` | `postgres:16-alpine` | 5432 | нет, только `127.0.0.1` | — |
| `backend` | сборка из [backend/Dockerfile](../backend/Dockerfile) | 8000 | нет, только `127.0.0.1` | `db` в состоянии healthy |
| `frontend` | сборка из [frontend/Dockerfile](../frontend/Dockerfile) | 3000 | да | `backend` (только факт запуска, без healthcheck) |

Гостю нужен только порт 3000: API он получает через прокси Nuxt, см. [02-architecture.md](02-architecture.md). Порты базы и backend привязаны к `127.0.0.1`. Разработчик на этой машине открывает Swagger и psql, а из сети база и API напрямую недоступны, и обратиться к API в обход прокси нельзя.

| Адрес | Что открывается |
|---|---|
| http://localhost:3000 | Сайт |
| http://localhost:8000/docs | Swagger backend (только с этой машины) |
| http://localhost:8000/api/health | `{"status":"ok"}` |
| `localhost:5432` | PostgreSQL, пользователь и база `kivana` (только с этой машины) |

### db

Данные лежат в именованном томе `db-data`. Compose добавляет к имени проекта, поэтому на диске том называется **`kivana_db-data`**. Он переживает `docker compose down`, но не `down -v`.

Healthcheck вызывает `pg_isready -h 127.0.0.1` каждые пять секунд, до двенадцати попыток. Флаг `-h` включает проверку по TCP. Без него `pg_isready` идёт через unix-сокет и отвечает «готово» ещё во время первичной инициализации тома. В этот момент временный сервер не слушает TCP, и backend упал бы на первом подключении.

`POSTGRES_USER`, `POSTGRES_PASSWORD` и `POSTGRES_DB` применяются только при **первой** инициализации пустого тома. Поменяв их позже, вы получите backend, который не может войти в старую базу: нужен `down -v` или правка роли в самой базе.

### backend

```yaml
command: sh -c "alembic upgrade head && python seed.py && uvicorn app.main:app --reload --host 0.0.0.0"
```

Compose переопределяет `CMD` из Dockerfile, который запускает один uvicorn. Порядок старта:

1. `db` проходит healthcheck.
2. `alembic upgrade head` создаёт и обновляет схему. Первая миграция ставит расширение `btree_gist`, оно входит в образ `postgres`.
3. `python seed.py` добавляет данные в порядке: справочники (отель, номера, услуги) → администратор (`ADMIN_EMAIL`/`ADMIN_PASSWORD`) → демо-данные, если `SEED_DEMO=true`. Каждый блок идемпотентен: номера и услуги добавляются по `slug` и существующие не перезаписываются (правки администратора важнее сида), пароль существующего администратора не меняется никогда, демо пропускается, если клиенты `@demo.kivana.ru` уже есть. Если пароль администратора или демо-клиентов не проходит политику паролей, сид завершается ошибкой.
4. `uvicorn` стартует и пишет логи в stdout.

Цепочка из `&&`: если миграция или сид упадут, uvicorn не запустится, и причина будет видна в `docker compose logs backend`. Сид идёт после миграций, потому что таблиц до них нет.

`FORWARDED_ALLOW_IPS: "*"` разрешает uvicorn брать IP клиента из `X-Forwarded-For`. Порт 8000 из сети закрыт, поэтому напрямую этот заголовок backend никто не пришлёт. Но dev-сервер Nuxt пропускает заголовок, присланный клиентом, так что через прокси IP всё равно подделывается. Как с этим справляется ограничение частоты, описано в [04-backend.md](04-backend.md).

Каталог `./backend` смонтирован в `/app`, флаг `--reload` перезапускает сервер при правке кода. Переменные окружения `--reload` не перечитывает: читаются они при импорте модулей, поэтому после смены значения в `.env` контейнер нужно пересоздать (`docker compose up -d backend`).

Файл `.env` читает сам compose, и в контейнер он **целиком не попадает**: backend получает только те переменные, что перечислены в блоке `environment` compose. Переменная, которой там нет (например `PROMO_MAX_PERCENT`), из `.env` не подхватится: её нужно добавить в compose.

### frontend

```yaml
volumes:
  - ./frontend:/app
  - /app/node_modules
```

Первое монтирование подключает исходники с хоста и заодно перекрывает `node_modules` из образа. Второе, анонимный том, возвращает содержимое образа поверх этого пути. Без него контейнер остался бы без зависимостей. Docker создаёт на хосте пустой каталог `frontend/node_modules` как точку монтирования, он в `.gitignore`.

Переменные frontend: `API_BASE=http://backend:8000` — адрес для прокси (имя `backend` резолвит DNS сети Compose), `WATCH_POLLING` — опрос файлов dev-сервером, `NUXT_PUBLIC_PASSWORD_MIN_LENGTH` — длина пароля для подсказки в поле (Nuxt сам превращает её в `runtimeConfig.public.passwordMinLength`). Compose берёт её из `PASSWORD_MIN_LENGTH`: правило и подсказка не расходятся. Правило прокси — `routeRules['/api/**']` в [nuxt.config.ts](../frontend/nuxt.config.ts).

## Переменные окружения

Все переменные необязательны. «Где читается» — файл, который берёт значение; все backend-модули читают его **при импорте**. [.env.example](../.env.example) описывает те же переменные с комментариями. Синтаксис compose `${VAR:-default}` подставляет значение по умолчанию, если переменной нет или она пуста.

### База данных и адреса

| Переменная | По умолчанию | Где читается | Назначение |
|---|---|---|---|
| `POSTGRES_USER` | `kivana` | compose: `db`, healthcheck, `DATABASE_URL` | Пользователь базы |
| `POSTGRES_PASSWORD` | `kivana` | compose: `db`, `DATABASE_URL` | Пароль базы |
| `POSTGRES_DB` | `kivana` | compose: `db`, healthcheck, `DATABASE_URL` | Имя базы |
| `DATABASE_URL` | собирается в compose из трёх выше; без compose `postgresql+psycopg://kivana:kivana@localhost:5432/kivana` | [database.py](../backend/app/database.py), [env.py](../backend/migrations/env.py), [conftest.py](../backend/conftest.py) | Строка подключения SQLAlchemy. Тесты берут из неё сервер и подменяют имя базы на `kivana_test` |
| `APP_BASE_URL` | `http://localhost:3000` | [mail_templates.py](../backend/app/mail_templates.py) | Адрес сайта: от него строятся ссылки в письмах |

### Почта

| Переменная | По умолчанию | Где читается | Назначение |
|---|---|---|---|
| `MAIL_BACKEND` | пусто | [mail.py](../backend/app/mail.py) | `resend`, `console` или `memory` (тесты). Пусто: `resend` при заданном `RESEND_API_KEY`, иначе `console` |
| `RESEND_API_KEY` | пусто | mail.py | Ключ API Resend |
| `MAIL_FROM` | `Kivana <no-reply@kivana.ru>` | mail.py | Отправитель; домен должен быть подтверждён в Resend |
| `ADMIN_NOTIFY_EMAIL` | пусто | [bookings.py](../backend/app/routers/bookings.py) | Кому писать о заявках на ручном разборе; пусто — не писать |

### Администратор и сид

| Переменная | По умолчанию | Где читается | Назначение |
|---|---|---|---|
| `ADMIN_EMAIL` | `admin@kivana.ru` | [seed.py](../backend/seed.py) | Логин администратора, которого сид создаёт при первом запуске |
| `ADMIN_PASSWORD` | `tidy copper lantern orbit` | seed.py | Пароль администратора. Должен проходить политику паролей, иначе backend не запустится. Пароль уже существующего пользователя сид не меняет: чтобы сменить, используйте «забыли пароль» или `down -v` |
| `SEED_DEMO` | `true` | seed.py; conftest ставит `false` | Демо-клиенты `@demo.kivana.ru`, их брони, заказы, уборки и акции. На боевом сервере `false` |
| `DEMO_PASSWORD` | `silver harbor morning tea` | seed.py | Один пароль на всех демо-клиентов; тоже проверяется политикой |

### Пароли и сессии

| Переменная | По умолчанию | Где читается | Назначение |
|---|---|---|---|
| `PASSWORD_MIN_LENGTH` | `15` | [passwords.py](../backend/app/passwords.py); во frontend как `NUXT_PUBLIC_PASSWORD_MIN_LENGTH` | Минимальная длина пароля (NIST SP 800-63B: от 15 символов, если пароль — единственный фактор) |
| `SESSION_TTL_GUEST_DAYS` | `14` | [sessions.py](../backend/app/sessions.py) | Срок сессии гостя, дней |
| `SESSION_TTL_ADMIN_HOURS` | `12` | sessions.py | Срок сессии администратора, часов |
| `COOKIE_SECURE` | `false` | sessions.py | `true` при работе по HTTPS: cookie уйдёт только по защищённому соединению |

### Бронирование и услуги

| Переменная | По умолчанию | Где читается | Назначение |
|---|---|---|---|
| `HOTEL_TZ` | `Europe/Moscow` | [hotel_time.py](../backend/app/hotel_time.py) | Часовой пояс отеля: «сегодня», просрочка заявок, дедлайн отмены, время заказов |
| `FREE_CANCEL_HOURS` | `48` | [booking_lifecycle.py](../backend/app/booking_lifecycle.py) | За сколько часов до заезда (дата + время заезда отеля) гость ещё отменяет подтверждённую бронь сам |
| `AUTO_CONFIRM_MAX_NIGHTS` | `7` | [booking_rules.py](../backend/app/booking_rules.py) | Дольше — ручной разбор (VIP не касается) |
| `AUTO_CONFIRM_MAX_TOTAL` | `60000` | booking_rules.py | Сумма больше, а завершённых проживаний нет — ручной разбор (VIP не касается), ₽ |
| `AUTO_CONFIRM_MAX_LEAD_DAYS` | `180` | booking_rules.py | Заезд дальше — ручной разбор (VIP не касается), дней |
| `PROMO_MAX_PERCENT` | `50` | booking_rules.py | Потолок процентной скидки. **Нет в compose и `.env.example`**: чтобы изменить, добавьте переменную в `environment` сервиса `backend` |
| `MAX_STAY_NIGHTS` | `30` | [schemas.py](../backend/app/schemas.py) | Самая длинная бронь, ночей |
| `MAX_LEAD_DAYS` | `365` | schemas.py | На сколько дней вперёд можно бронировать |
| `MAX_PENDING_PER_CLIENT` | `3` | bookings.py | Заявок на рассмотрении у одного клиента одновременно |
| `ROOM_SERVICE_HOURS` | `08:00-23:00` | [room_service.py](../backend/app/room_service.py) | Часы приёма заказов еды в номер, `ЧЧ:ММ-ЧЧ:ММ` по `HOTEL_TZ`; конец не включается |

### Frontend и прокси

| Переменная | По умолчанию | Где читается | Назначение |
|---|---|---|---|
| `API_BASE` | `http://backend:8000` в compose; `http://localhost:8000` без него | [nuxt.config.ts](../frontend/nuxt.config.ts) | Адрес backend для прокси `/api/**` |
| `WATCH_POLLING` | `true` | nuxt.config.ts | Опрос файлов dev-сервером. Нужен на Windows (bind-mount не отдаёт события inotify); на Linux и macOS можно выключить |
| `NUXT_PUBLIC_PASSWORD_MIN_LENGTH` | из `PASSWORD_MIN_LENGTH` | Nuxt `runtimeConfig` | Минимальная длина для подсказки в поле пароля |
| `FORWARDED_ALLOW_IPS` | `*` (зашито в compose) | uvicorn | Доверие к `X-Forwarded-For`, см. выше |

В тестах [conftest.py](../backend/conftest.py) принудительно задаёт `DATABASE_URL` (база `kivana_test`), `MAIL_BACKEND=memory` и `SEED_DEMO=false`. Переменных `ADMIN_USERNAME` и `SECRET_KEY` версии 1.0 больше нет: администратор — пользователь в базе, сессии хранятся в таблице `sessions`, подписывать нечего.

## Образы

Оба Dockerfile одностадийные: это dev-сборка. Backend — `python:3.12-slim` и `pip install --no-cache-dir`, frontend — `node:24-alpine` и `npm ci`. Манифест зависимостей копируется отдельным слоем перед исходниками, поэтому правка кода не переустанавливает зависимости.

`npm ci` требует `package-lock.json`, поэтому lock-файл лежит в репозитории. Версия Node в образе совпадает по мажорной линейке с той, в которой lock-файл сгенерирован. Зависимости backend (в том числе `argon2-cffi` и `zxcvbn`) ставятся при сборке: после правки [requirements.txt](../backend/requirements.txt) нужен `docker compose up --build`.

## Тома и данные

| Что | Где | Переживает `down` | Переживает `down -v` |
|---|---|---|---|
| База | том `kivana_db-data` | да | нет |
| Исходники backend | bind-mount `./backend` → `/app` | да, лежат на хосте | да |
| Исходники frontend | bind-mount `./frontend` → `/app` | да | да |
| `node_modules` frontend | анонимный том `/app/node_modules` | пересоздаётся | пересоздаётся |

**Старый том.** Если проект запускался раньше под именем `web-hotel`, его том `web-hotel_db-data` останется осиротевшим: новый запуск создаёт пустой `kivana_db-data` и со старым не связан. Удалять нужно вручную:

```bash
docker volume ls | grep web-hotel_
```

```bash
docker volume rm web-hotel_db-data
```

Данные версии 1.0 не переносятся: заявки без аккаунта (у них был `email` вместо привязки к пользователю) миграция 0003 удаляет. Если под старым именем нужны именно они, выгрузите их до перехода: `docker compose exec db pg_dump -U hotel -t bookings --data-only hotel > bookings.sql`.

## Подключение Resend

Без ключа почта работает в режиме `console`: тема, текст и ссылки (подтверждение почты, сброс пароля) печатаются в лог backend, и весь сценарий проходится без внешнего сервиса:

```bash
docker compose logs -f backend
```

Боевая отправка:

1. Зарегистрируйтесь на [resend.com](https://resend.com) и в разделе Domains добавьте домен `kivana.ru`.
2. Resend покажет DNS-записи: SPF и DKIM (TXT) и MX для отправки. Внесите их у регистратора домена как есть и дождитесь статуса Verified. Свои значения придумывать не нужно: берутся из панели.
3. Создайте ключ в разделе API Keys.
4. Задайте в `.env`: `RESEND_API_KEY=<ключ>` и `MAIL_FROM="Kivana <no-reply@kivana.ru>"` (адрес на подтверждённом домене). `MAIL_BACKEND` можно оставить пустым: при ключе выберется `resend`.
5. Пересоздайте контейнер: `docker compose up -d backend`.

Без подтверждённого домена Resend доставляет письма только на адрес владельца аккаунта Resend, остальным они не дойдут, а в логе backend появится ошибка отправки. Для проверки без своего ящика используйте тестовый адрес `delivered@resend.dev`: на него письмо всегда «доставляется». Зарегистрируйте на него гостя или задайте его в `ADMIN_NOTIFY_EMAIL`.

Ошибка отправки пишется в лог и не ломает ни регистрацию, ни смену статуса брони; повторных попыток нет. Как письма ставятся в фон, описано в [04-backend.md](04-backend.md).

## Миграции

Применяются автоматически при старте backend. Создать новую после правки [models.py](../backend/app/models.py):

```bash
docker compose exec backend alembic revision --autogenerate -m "описание изменения"
```

Autogenerate не видит `CHECK`-ограничения и `bookings_no_overlap`: их пишут в миграции вручную. Сгенерированный файл нужно прочитать до применения. Применить без перезапуска — `docker compose exec backend alembic upgrade head`, откатить одну версию — `alembic downgrade -1`, сверить модели с базой — `alembic check`. Рецепт и подводные камни — в [08-conventions.md](08-conventions.md).

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
docker compose exec db psql -U kivana -d kivana -c "select id, user_id, status, check_in from bookings order by id desc limit 20;"
```

## Сброс данных

Полный сброс: удалить контейнеры и том, затем поднять заново. Миграции и сид отработают с нуля, демо-данные вернутся.

```bash
docker compose down -v && docker compose up --build
```

Сбросить только тестовую базу (миграции прогонятся с нуля при следующем `pytest`):

```bash
docker compose exec db psql -U kivana -d kivana -c "DROP DATABASE kivana_test"
```

Демо-данные отдельно не пересоздаются: сид пропускает блок, если демо-клиенты есть. Чтобы вернуть демо после ручных правок, нужен `down -v`.

## Ограничения dev-режима

Контейнеры работают в режиме разработки, продакшен-сборки нет. Перечень с последствиями — в [09-tech-debt.md](09-tech-debt.md); здесь то, что относится к запуску:

| Проблема | Что сделать на боевом сервере |
|---|---|
| Админ из `ADMIN_PASSWORD` по умолчанию публичный (он в compose, `.env.example` и README) | Задать свой пароль в `.env` до первого запуска; после создания администратора смена переменной пароль **не** меняет |
| `SEED_DEMO=true` по умолчанию: публичные демо-аккаунты | `SEED_DEMO=false`; уже созданных демо-клиентов удалить вручную |
| Нет TLS и reverse proxy | Поставить прокси с сертификатом и `COOKIE_SECURE=true` |
| Dev-серверы (`--reload`, `nuxt dev`), bind-mount | Собрать production-образы без монтирования и без `--reload` |
| Письма уходят фоновой задачей без очереди и повторов | Очередь или внешний воркер; мониторинг ошибок отправки |
| Ограничитель частоты в памяти одного процесса, IP подделывается через заголовок | Redis и прокси, который перезаписывает `X-Forwarded-For` |
| Просрочка заявок ленивая, без планировщика | Периодическая задача, если нужны письма и статусы без заходов в систему |
| Нет healthcheck у `backend` и `frontend`, нет `restart` | Добавить healthcheck и политику перезапуска |
| Нет резервного копирования тома и мониторинга | Регулярный `pg_dump`, алерты |
| Дефолтные `POSTGRES_*` слабые | Свой пароль до первой инициализации тома |

## Вопросы на понимание

1. Почему порт 8000 привязан к `127.0.0.1` и как это связано с `FORWARDED_ALLOW_IPS`?
2. Вы поменяли `PROMO_MAX_PERCENT` в `.env`, а скидка осталась прежней. Почему и что исправить?
3. Что остаётся на диске после `docker compose down`, после `down -v` и после переименования проекта из `web-hotel` в `kivana`?
4. Backend не стартует, в логах «ADMIN_PASSWORD не проходит политику паролей». На каком шаге цепочки запуска он остановился и почему uvicorn не поднялся?
5. Ключ Resend задан, а домен `kivana.ru` не подтверждён. Кому письма дойдут и где увидеть ошибку для остальных?
