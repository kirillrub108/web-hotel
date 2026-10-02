#!/usr/bin/env bash
# Полная цепочка одной командой: приложение → сброс БД сидом → запись всех сцен → монтаж.
#
#   ./demo-video/run.sh
#
# Результат: demo-video/out/client.mp4, admin.mp4, full.mp4 и таймкоды в demo-video/SCENARIO.md.
# STACK_MODE=docker|native|auto (по умолчанию auto: docker compose, если демон доступен, иначе локальные сервисы).
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

for tool in node npm ffmpeg ffprobe curl; do
  command -v "$tool" >/dev/null || { echo "Нужен $tool" >&2; exit 1; }
done
[[ -d node_modules/playwright ]] || npm install --no-audit --no-fund

echo "== 1/4 Приложение"
scripts/stack.sh up

echo "== 2/4 Сброс БД: миграции, backend/seed.py, seed/seed_extra.py"
scripts/stack.sh reset
rm -rf raw work/state-*.json work/fail-*.png

echo "== 3/4 Запись сцен"
node scripts/record.mjs

echo "== 4/4 Монтаж"
node scripts/build.mjs

for f in out/client.mp4 out/admin.mp4 out/full.mp4; do
  ffprobe -v error -select_streams v:0 -show_entries stream=codec_name,width,height,r_frame_rate -show_entries format=duration \
    -of compact=p=0:nk=0 "$f" | tr '\n' ' ' | sed "s|^|$f: |"
  echo
done
