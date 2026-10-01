"""Проверка демо-данных для скриншотов (и дозаполнение через публичный API, если чего-то не хватает).

Встроенный сид backend (SEED_DEMO=true) уже создаёт номера, клиентов, брони во всех статусах, заказы услуг,
уборки и акции. Скрипт проверяет это через API и печатает сводку. Если нет ни одной заявки «на разборе»,
создаёт её от имени демо-клиента Марии Орловой (заявка с комментарием всегда уходит на ручную проверку).

Запуск: python report/build/seed_demo.py  (стек должен быть поднят: docker compose up -d)
"""

import os
import re
import sys
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
API = "http://localhost:8000"


def creds() -> dict[str, str]:
    """Значения по умолчанию из docker-compose.yml, поверх — корневой .env и переменные окружения (как у compose)."""
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    values = dict(re.findall(r"\$\{(\w+):-([^}]*)\}", compose))
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, _, value = line.partition("=")
                values[key.strip()] = value.strip().strip('"').strip("'")
    values.update({k: v for k, v in os.environ.items() if k in values})
    return values


def login(email: str, password: str) -> requests.Session:
    s = requests.Session()
    r = s.post(f"{API}/api/auth/login", json={"email": email, "password": password}, timeout=30)
    r.raise_for_status()
    return s


def free_window(slug: str, nights: int, guests: int, start_offset: int) -> tuple[date, date]:
    """Первые свободные даты (по котировке API) начиная с сегодня + start_offset дней."""
    for offset in range(start_offset, start_offset + 200):
        check_in = date.today() + timedelta(days=offset)
        check_out = check_in + timedelta(days=nights)
        q = requests.get(
            f"{API}/api/rooms/{slug}/quote",
            params={"check_in": check_in.isoformat(), "check_out": check_out.isoformat(), "guests": guests},
            timeout=30,
        ).json()
        if q.get("available"):
            return check_in, check_out
    raise SystemExit(f"Нет свободных дат для {slug}")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    c = creds()
    rooms = requests.get(f"{API}/api/rooms", timeout=30).json()
    admin = login(c["ADMIN_EMAIL"], c["ADMIN_PASSWORD"])
    bookings = admin.get(f"{API}/api/admin/bookings", params={"limit": 100}, timeout=30).json()["items"]

    added = []
    if not any(b["status"] == "pending" for b in bookings):
        maria = login("maria@demo.kivana.ru", c["DEMO_PASSWORD"])
        room = next(r for r in rooms if r["slug"] == "semeyny")
        check_in, check_out = free_window("semeyny", 5, 3, 35)
        r = maria.post(
            f"{API}/api/bookings",
            json={
                "room_id": room["id"],
                "guest_name": "Мария Орлова",
                "phone": "+7 900 444-55-66",
                "check_in": check_in.isoformat(),
                "check_out": check_out.isoformat(),
                "guests": 3,
                "comment": "Едем всей семьёй, просим номер подальше от лифта.",
            },
            timeout=30,
        )
        r.raise_for_status()
        added.append(f"заявка №{r.json()['id']} (Мария Орлова, Семейный, {check_in}–{check_out}, {r.json()['status']})")
        bookings = admin.get(f"{API}/api/admin/bookings", params={"limit": 100}, timeout=30).json()["items"]

    clients = admin.get(f"{API}/api/admin/clients", params={"limit": 100}, timeout=30).json()["items"]
    orders = admin.get(f"{API}/api/admin/service-orders", timeout=30).json()
    promos = admin.get(f"{API}/api/admin/promos", timeout=30).json()
    services = requests.get(f"{API}/api/services", timeout=30).json()
    board = admin.get(f"{API}/api/admin/housekeeping", timeout=30).json()

    print("Номера:")
    for r in rooms:
        print(f"  {r['name']}: {r['price_per_night']} ₽/ночь, до {r['capacity']} гостей, {r['area']} м²")
    print("Клиенты:", ", ".join(f"{x['full_name']} <{x['email']}>" for x in clients))
    print("Брони:")
    for b in sorted(bookings, key=lambda b: b["id"]):
        print(
            f"  №{b['id']} {b['guest_name']}, {b['room']['name']}, {b['check_in']}–{b['check_out']}, "
            f"{b['status']}/{b['display_status']}, {b['total_price']} ₽"
        )
    print("Статусы броней:", dict(Counter(b["status"] for b in bookings)))
    print("Заказы услуг:", dict(Counter(o["status"] for o in orders)))
    tasks = sum(len(v) for v in board["daily"].values()) + len(board["checkout"]) + len(board["dnd"])
    print(f"Услуг в каталоге: {len(services)} | акций: {len(promos)} | задач уборки на сегодня: {tasks}")
    print("Добавлено:", "; ".join(added) if added else "ничего — встроенный сид покрывает всё")

    missing = [s for s in ("pending", "confirmed", "declined", "cancelled") if s not in {b["status"] for b in bookings}]
    if missing or not orders or not promos or not services or len(rooms) < 6:
        sys.exit(f"Не хватает демо-данных: статусы {missing}, заказов {len(orders)}, акций {len(promos)}")


if __name__ == "__main__":
    main()
