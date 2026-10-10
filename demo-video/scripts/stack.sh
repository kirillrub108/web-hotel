#!/usr/bin/env bash
# Управление приложением для записи видео: запуск, сброс БД сидом, снимки БД для перезаписи сцен.
#
#   stack.sh up        — поднять Postgres, backend и frontend (если ещё не подняты)
#   stack.sh reset     — пересоздать БД: миграции → backend/seed.py → demo-video/seed/seed_extra.py
#   stack.sh snapshot NAME / restore NAME — снимок БД перед сценой и откат к нему при перезаписи
#   stack.sh logs      — обновить work/backend.log (письма console-режима со ссылками)
#   stack.sh down      — остановить то, что запустил этот скрипт
#
# Режим STACK_MODE: native (локальные Postgres/uvicorn/node, по docs/10-onboarding.md),
# docker (docker compose проекта) или auto (docker, если демон доступен, иначе native).
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEMO="$(dirname "$HERE")"
ROOT="$(dirname "$DEMO")"
WORK="$DEMO/work"
mkdir -p "$WORK/snap"

DB_USER=kivana DB_PASS=kivana DB_NAME=kivana DB_HOST=127.0.0.1 DB_PORT=5432
export PGPASSWORD="$DB_PASS"
APP_URL="${APP_URL:-http://localhost:3000}"
API_URL="http://127.0.0.1:8000"

MODE="${STACK_MODE:-auto}"
if [[ "$MODE" == auto ]]; then
  if docker info >/dev/null 2>&1; then MODE=docker; else MODE=native; fi
fi

log() { echo "[stack:$MODE] $*" >&2; }

wait_http() { # url, секунд
  local url="$1" limit="${2:-120}" i
  for ((i = 0; i < limit; i++)); do
    if curl -sf -o /dev/null --max-time 5 "$url"; then return 0; fi
    sleep 1
  done
  log "не дождались $url"; return 1
}

# ---------------------------------------------------------------- native
# Переменные backend — те же значения по умолчанию, что в docker-compose.yml; почта — штатный console-режим.
backend_env() {
  export DATABASE_URL="postgresql+psycopg://$DB_USER:$DB_PASS@$DB_HOST:$DB_PORT/$DB_NAME"
  export APP_BASE_URL="$APP_URL" MAIL_BACKEND=console SEED_DEMO=true
  export ADMIN_EMAIL=admin@kivana.ru ADMIN_PASSWORD="tidy copper lantern orbit" DEMO_PASSWORD="silver harbor morning tea"
  export HOTEL_TZ=Europe/Moscow COOKIE_SECURE=false
}

pg_super() { # SQL от суперпользователя postgres
  if [[ $(id -u) == 0 ]]; then su postgres -c "psql -v ON_ERROR_STOP=1 -qAt -c \"$1\""; else sudo -u postgres psql -v ON_ERROR_STOP=1 -qAt -c "$1"; fi
}

native_pg_up() {
  if ! pg_isready -q -h "$DB_HOST" -p "$DB_PORT"; then
    log "запускаю PostgreSQL"
    local cluster; cluster=$(pg_lsclusters -h | awk 'NR==1 {print $1" "$2}')
    # shellcheck disable=SC2086
    pg_ctlcluster $cluster start
    for _ in $(seq 30); do pg_isready -q -h "$DB_HOST" -p "$DB_PORT" && break; sleep 1; done
  fi
  if [[ -z $(pg_super "SELECT 1 FROM pg_roles WHERE rolname='$DB_USER'") ]]; then
    pg_super "CREATE USER $DB_USER WITH PASSWORD '$DB_PASS' CREATEDB"
  fi
}

native_backend_stop() {
  if [[ -f "$WORK/backend.pid" ]]; then kill "$(cat "$WORK/backend.pid")" 2>/dev/null || true; rm -f "$WORK/backend.pid"; fi
  # uvicorn, запущенный не этим скриптом, тоже держит порт
  pkill -f "uvicorn app.main:app" 2>/dev/null || true
  for _ in $(seq 20); do curl -s -o /dev/null --max-time 1 "$API_URL/api/hotel" || return 0; sleep 0.5; done
}

native_backend_start() {
  backend_env
  log "запускаю backend (лог: work/backend.log)"
  (cd "$ROOT/backend" || exit 1
   nohup uvicorn app.main:app --host 127.0.0.1 --port 8000 --proxy-headers </dev/null >>"$WORK/backend.log" 2>&1 &
   echo $! >"$WORK/backend.pid")
  wait_http "$API_URL/api/hotel" 60
}

native_frontend_up() {
  if curl -sf -o /dev/null --max-time 5 "$APP_URL/"; then return 0; fi
  if [[ ! -d "$ROOT/frontend/node_modules" ]]; then (cd "$ROOT/frontend" && npm ci --no-audit --no-fund); fi
  # Production-сборка: страницы открываются сразу, без компиляции на лету (меньше «мёртвых» пауз в кадре).
  if [[ ! -f "$ROOT/frontend/.output/server/index.mjs" || "${FORCE_BUILD:-0}" == 1 ]]; then
    log "собираю frontend (nuxt build)"
    (cd "$ROOT/frontend" && API_BASE="$API_URL" npx nuxt build >"$WORK/frontend-build.log" 2>&1)
  fi
  log "запускаю frontend"
  (cd "$ROOT/frontend" || exit 1
   PORT=3000 HOST=0.0.0.0 NUXT_PUBLIC_PASSWORD_MIN_LENGTH=15 nohup node .output/server/index.mjs </dev/null >"$WORK/frontend.log" 2>&1 &
   echo $! >"$WORK/frontend.pid")
  wait_http "$APP_URL/" 60
}

native_up() {
  python3 -c "import fastapi, alembic, psycopg" 2>/dev/null || pip install -q -r "$ROOT/backend/requirements.txt"
  native_pg_up
  if [[ -z $(pg_super "SELECT 1 FROM pg_database WHERE datname='$DB_NAME'") ]]; then native_reset; fi
  curl -sf -o /dev/null --max-time 3 "$API_URL/api/hotel" || native_backend_start
  native_frontend_up
}

native_reset() {
  native_pg_up
  native_backend_stop
  log "пересоздаю БД $DB_NAME"
  pg_super "DROP DATABASE IF EXISTS $DB_NAME WITH (FORCE)"
  pg_super "CREATE DATABASE $DB_NAME OWNER $DB_USER"
  backend_env
  (cd "$ROOT/backend" && alembic upgrade head >/dev/null 2>&1 && python3 seed.py && PYTHONPATH=. python3 "$DEMO/seed/seed_extra.py")
  : >"$WORK/backend.log"
  native_backend_start
}

native_snapshot() { pg_dump -Fc -h "$DB_HOST" -U "$DB_USER" "$DB_NAME" >"$WORK/snap/$1.dump"; }

native_restore() {
  native_backend_stop # заодно сбрасывает счётчики ограничения частоты запросов
  pg_super "DROP DATABASE IF EXISTS $DB_NAME WITH (FORCE)"
  pg_super "CREATE DATABASE $DB_NAME OWNER $DB_USER"
  pg_restore -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" --no-owner "$WORK/snap/$1.dump"
  native_backend_start
}

native_down() {
  native_backend_stop
  if [[ -f "$WORK/frontend.pid" ]]; then kill "$(cat "$WORK/frontend.pid")" 2>/dev/null || true; rm -f "$WORK/frontend.pid"; fi
}

# ---------------------------------------------------------------- docker
dc() { (cd "$ROOT" && docker compose "$@"); }

docker_up() {
  dc up -d --build
  wait_http "$APP_URL/" 300
  # dev-сервер Nuxt компилирует страницу при первом открытии: прогреваем ключевые маршруты
  for path in / /rooms /services /contacts /login /register /account /admin; do curl -s -o /dev/null --max-time 120 "$APP_URL$path" || true; done
}

docker_reset() {
  dc down -v
  dc up -d --build
  wait_http "$API_URL/api/hotel" 300
  dc exec -T backend sh -c 'PYTHONPATH=/app python -' <"$DEMO/seed/seed_extra.py"
  docker_up
}

docker_snapshot() { dc exec -T db pg_dump -U "$DB_USER" -Fc "$DB_NAME" >"$WORK/snap/$1.dump"; }

docker_restore() {
  dc stop backend
  dc exec -T db sh -c "dropdb -U $DB_USER --if-exists --force $DB_NAME && createdb -U $DB_USER $DB_NAME"
  dc exec -T db pg_restore -U "$DB_USER" -d "$DB_NAME" --no-owner <"$WORK/snap/$1.dump"
  dc start backend
  wait_http "$API_URL/api/hotel" 120
}

docker_logs() { dc logs --no-color backend >"$WORK/backend.log"; }
docker_down() { dc down; }

# ---------------------------------------------------------------- dispatch
cmd="${1:-}"; shift || true
case "$cmd" in
  up) "${MODE}_up" ;;
  reset) "${MODE}_reset" ;;
  snapshot) "${MODE}_snapshot" "$1" ;;
  restore) "${MODE}_restore" "$1" ;;
  logs) if [[ $MODE == docker ]]; then docker_logs; fi ;;
  down) "${MODE}_down" ;;
  mode) echo "$MODE" ;;
  *) echo "usage: stack.sh up|reset|snapshot NAME|restore NAME|logs|down|mode" >&2; exit 2 ;;
esac
