"""Скриншоты для отчёта: собственный сайт Kivana и сайты-аналоги.

    python report/build/capture.py              # --site и --analogs
    python report/build/capture.py --up --site  # сначала docker compose up -d --build и ожидание

PNG -> report/assets/screens/, видимый текст каждой страницы -> report/build/screens_text/ (для описаний).
Каждый кадр проверяется до сохранения: страница загрузилась, нужный текст виден, это не страница ошибки Nuxt,
списки не пустые, картинка не однотонная. Любое расхождение — исключение и ненулевой код выхода.

Сценарий меняет данные: регистрирует гостью Елену Смирнову (только при первом запуске), создаёт заявку Анны (с комментарием -> на разборе),
которую затем подтверждает администратор. Поэтому повторный запуск каждый раз берёт новые свободные даты.
"""

import argparse
import re
import secrets
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from PIL import Image, ImageStat
from playwright.sync_api import Browser, Page, expect, sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
from seed_demo import API, ROOT, creds, free_window  # noqa: E402

SITE = "http://localhost:3000"
OUT = ROOT / "report" / "assets" / "screens"
TEXT = ROOT / "report" / "build" / "screens_text"
VIEWPORT = {"width": 1366, "height": 768}
MSK = timezone(timedelta(hours=3))
ANNA_COMMENT = "Приедем поздно, около 23:00. Пожалуйста, поставьте детскую кроватку."
NEW_GUEST = ("Елена Смирнова", "elena.smirnova@demo.kivana.ru")  # гость, который регистрируется на сайте
ANALOGS = [
    "https://azimuthotels.com/ru",
    "https://cosmosgroup.ru",
    "https://ostrovok.ru",
    "https://sutochno.ru",
    "https://www.purnavolok.ru",
]
BLOCK_MARKERS = re.compile(
    r"captcha|капч|не робот|not a robot|access denied|доступ (ограничен|запрещ)|forbidden|"
    r"checking your browser|подозрительн|security check|ddos-guard|just a moment",
    re.I,
)


class ShotError(SystemExit):
    pass


def wait_ready(timeout: int = 600) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if requests.get(SITE, timeout=10).ok and requests.get(f"{API}/api/rooms", timeout=10).ok:
                return
        except requests.RequestException:
            pass
        time.sleep(3)
    raise ShotError(f"{SITE} или {API}/api/rooms не отвечают {timeout} с")


def check_image(path: Path) -> None:
    if ImageStat.Stat(Image.open(path).convert("L")).stddev[0] < 8:
        raise ShotError(f"{path.name}: картинка почти однотонная (пустая страница?)")


def scroll_to(page: Page, selector: str) -> None:
    """Мгновенная прокрутка (в CSS сайта smooth): элемент ниже липкой шапки."""
    page.locator(selector).first.evaluate(
        "e => window.scrollTo({top: e.getBoundingClientRect().top + window.scrollY - 90, behavior: 'instant'})"
    )


def save(page: Page, name: str, full: bool) -> None:
    path = OUT / f"{name}.png"
    page.mouse.move(0, 0)  # без hover-подсветки кнопки, по которой только что кликнули
    # Широкие таблицы админки прокручиваются по горизонтали; после клика по кнопке справа — вернуть в начало.
    page.evaluate("document.querySelectorAll('.table-wrap').forEach(e => { e.scrollLeft = 0 })")
    if full:
        page.evaluate("window.scrollTo({top: 0, behavior: 'instant'})")
    page.screenshot(path=path, full_page=full)
    check_image(path)
    url = re.sub(r"token=[\w-]+", "token=<скрыт>", page.url)  # одноразовые токены из писем в файлы не пишем
    (TEXT / f"{name}.txt").write_text(url + "\n\n" + page.inner_text("body"), encoding="utf-8")
    print(f"ok  {name:32} {url}")


def shot(page: Page, name: str, text: str, *, full: bool = False, rows: str | None = None) -> None:
    """text — что обязано быть видно; rows — селектор элементов списка, которых должно быть хотя бы два."""
    page.wait_for_load_state("networkidle")
    expect(page.get_by_text(text).first).to_be_visible()
    if page.locator(".error__code").count():
        raise ShotError(f"{name}: открылась страница ошибки Nuxt ({page.url})")
    if rows and page.locator(rows).count() < 2:
        raise ShotError(f"{name}: список пуст или почти пуст ({rows}: {page.locator(rows).count()})")
    save(page, name, full)


def mail_link(email: str, kind: str) -> str:
    """Ссылка из последнего письма пользователю: console-бэкенд почты печатает письма в лог backend."""
    pattern = re.compile(rf"/{kind}\?token=[\w-]+")
    for _ in range(30):
        logs = subprocess.run(
            ["docker", "compose", "logs", "--no-log-prefix", "--since", "30m", "backend"],
            cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace",
        ).stdout
        start = logs.rfind(f"Письмо для {email}")
        if start != -1 and (match := pattern.search(logs, start)):
            return SITE + match.group(0)
        time.sleep(1)
    raise ShotError(f"В логах backend нет письма {kind} для {email}")


def go(page: Page, path: str) -> None:
    """Открыть страницу и дождаться гидратации: до неё v-model не видит ввод в поля."""
    page.goto(path if path.startswith("http") else SITE + path)
    page.wait_for_load_state("networkidle")
    page.wait_for_function("() => Boolean(document.querySelector('#__nuxt')?.__vue_app__)")


def login(page: Page, email: str, password: str, landing: str) -> None:
    go(page, "/login")
    page.fill("#email", email)
    page.fill("#password", password)
    page.locator("form button[type=submit]").click()
    try:
        page.wait_for_url(f"**{landing}", timeout=20_000)
    except Exception:
        notice = page.locator(".notice--error")
        raise ShotError(f"Вход {email} не удался: {notice.inner_text() if notice.count() else page.url}") from None


def open_tab(page: Page, name: str) -> None:
    """Вкладка статуса в «Заявках»: дождаться ответа API, иначе в таблице ещё строки прежней вкладки."""
    with page.expect_response(lambda r: "/api/admin/bookings?" in r.url):
        page.get_by_role("tab", name=name).click()
    page.wait_for_load_state("networkidle")


def capture_site(browser: Browser) -> None:
    c = creds()

    def new_page() -> Page:
        context = browser.new_context(viewport=VIEWPORT, locale="ru-RU", timezone_id="Europe/Moscow")
        context.set_default_timeout(60_000)  # dev-сервер Nuxt компилирует страницу при первом открытии
        return context.new_page()

    # Администратор входит первым: через его API проверяем, зарегистрирована ли уже Елена (повторный запуск).
    m = new_page()
    login(m, c["ADMIN_EMAIL"], c["ADMIN_PASSWORD"], "/admin")
    full_name, new_email = NEW_GUEST
    found = m.request.get(f"{SITE}/api/admin/clients", params={"search": new_email}).json()["total"]

    # ---------- Гость ----------
    g = new_page()
    go(g, "/")
    shot(g, "01_home_guest", "Популярные номера", rows=".grid .room")
    go(g, "/login")
    shot(g, "02_login", "Забыли пароль?")

    go(g, "/register")
    g.fill("#full_name", full_name)
    g.fill("#email", new_email)
    g.fill("#password", f"amber {secrets.token_hex(3)} river {secrets.token_hex(3)}")
    g.locator("input[type=checkbox]").check()
    shot(g, "03_register_filled", "Длина подходит.")
    if found:
        # Дубликат не создаём: форму не отправляем, 04 и 05 остаются от первого запуска.
        print(f"skip 04_register_done, 05_verify_email: {new_email} уже зарегистрирована")
    else:
        g.get_by_role("button", name="Зарегистрироваться").click()
        shot(g, "04_register_done", "Проверьте почту")
        go(g, mail_link(new_email, "verify-email"))
        g.get_by_role("button", name="Подтвердить email").click()
        shot(g, "05_verify_email", "Email подтверждён")

    go(g, "/forgot-password")
    g.fill("#email", new_email)
    shot(g, "06_forgot_password", "Восстановление пароля")
    g.get_by_role("button", name="Отправить ссылку").click()
    shot(g, "31_forgot_password_sent", "Ссылка действует 1 час")
    go(g, mail_link(new_email, "reset-password"))
    g.fill("#password", f"maple {secrets.token_hex(3)} harbor {secrets.token_hex(3)}")  # не отправляем
    shot(g, "32_reset_password", "Сохранить пароль")

    go(g, "/services")
    shot(g, "17_services", "Завтрак в номер", full=True, rows=".card")
    go(g, "/contacts")
    shot(g, "18_contacts", "Контакты")
    go(g, "/privacy")
    shot(g, "30_privacy", "Обработка персональных данных")
    go(g, "/rooms/semeyny")
    shot(g, "33_room_card_guest", "Войдите, чтобы забронировать")
    go(g, "/no-such-page")
    expect(g.get_by_text("Такой страницы нет")).to_be_visible()
    save(g, "34_error_404", full=False)

    # ---------- Клиент: Анна Лебедева ----------
    a = new_page()
    login(a, "anna@demo.kivana.ru", c["DEMO_PASSWORD"], "/account")
    go(a, "/")
    shot(a, "07_home_client", "Кабинет")
    go(a, "/rooms")
    shot(a, "08_rooms_catalog", "Шесть категорий", full=True, rows=".grid .room")
    go(a, "/rooms/semeyny")
    shot(a, "09_room_card", "Выберите даты — покажем стоимость")

    # Заявки Анны, оставшиеся «на разборе» от прерванных запусков, отменяем — иначе упрёмся в лимит заявок.
    for old in a.request.get(f"{SITE}/api/account/bookings").json():
        if old["status"] == "pending" and old["comment"] == ANNA_COMMENT:
            a.request.post(f"{SITE}/api/account/bookings/{old['id']}/cancel")

    check_in, check_out = free_window("semeyny", 3, 3, 21)
    a.fill("#check_in", check_in.isoformat())
    a.fill("#check_out", check_out.isoformat())
    a.fill("#guests", "3")
    a.fill("#phone", "+7 900 111-22-33")
    a.fill("#comment", ANNA_COMMENT)
    if a.locator("#promo_offer option").count() > 1:
        a.select_option("#promo_offer", index=1)
    expect(a.locator(".booking__total")).to_be_visible()
    shot(a, "10_booking_form_filled", "Итого:", full=True)
    a.locator(".booking__submit").click()
    shot(a, "11_booking_submitted", "Заявка отправлена")

    go(a, "/account")
    shot(a, "12_account", "Здравствуйте")
    go(a, "/account/bookings")
    shot(a, "13_account_bookings", "Мои брони", full=True, rows="a[href^='/account/bookings/']")

    bookings = a.request.get(f"{SITE}/api/account/bookings").json()
    current = next((b for b in bookings if b["display_status"] == "in_stay"), None) or next(
        b for b in sorted(bookings, key=lambda b: b["check_in"]) if b["display_status"] == "confirmed"
    )
    go(a, f"/account/bookings/{current['id']}")
    shot(a, "14_account_booking_detail", "История", full=True)

    window = a.request.get(f"{SITE}/api/account/bookings/{current['id']}").json()["order_window"]
    if not window:
        raise ShotError(f"По брони №{current['id']} нельзя заказать услуги (нет order_window)")
    start = datetime.fromisoformat(window["start"]).astimezone(MSK)
    when = max((datetime.now(MSK) + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0), start)
    breakfast = a.locator("#order-service option", has_text="Завтрак в номер").first.evaluate("o => o.value")
    a.select_option("#order-service", value=breakfast)
    a.fill("#order-quantity", "2")
    a.fill("#order-time", when.strftime("%Y-%m-%dT%H:%M"))
    a.fill("#order-comment", "Один завтрак с сырниками, второй с омлетом. Кофе с молоком.")
    scroll_to(a, "h3:has-text('Новый заказ')")
    shot(a, "15_service_order_form", "Сумма:")
    go(a, "/account/profile")
    shot(a, "16_account_profile", "Смена пароля")

    # ---------- Администратор ----------
    go(m, "/admin")
    open_tab(m, "Все")
    shot(m, "19_admin_bookings", "Статус и причины", full=True, rows="table.data-table tbody tr")

    # Строка новой заявки Анны: по датам и имени (текст ячейки «№id» сливается с датой создания).
    dates = f"{check_in:%d.%m.%Y} — {check_out:%d.%m.%Y}"
    row = m.locator("table.data-table tbody tr", has_text=dates).filter(has_text="Анна Лебедева")
    open_tab(m, "На разборе")
    row.get_by_role("button", name="История").click()
    expect(m.locator("tr.history")).to_be_visible()
    shot(m, "20_admin_booking_detail", "Скрыть историю", full=True)

    row.get_by_role("button", name="Подтвердить").click()
    m.fill("#admin-reason", "Детскую кроватку поставим. Ночной администратор встретит вас и передаст ключи.")
    shot(m, "21_admin_status_dialog", "Подтвердить бронь")
    m.locator("dialog button[type=submit]").click()
    expect(m.locator("dialog")).to_have_count(0)
    open_tab(m, "Подтверждённые")
    expect(row).to_contain_text("Подтверждена")
    shot(m, "22_admin_status_changed", dates)

    go(m, "/admin/clients")
    shot(m, "23_admin_clients", "Поиск по имени, email или телефону", full=True, rows="tbody tr")
    m.get_by_role("link", name="Анна Лебедева").click()
    m.wait_for_url("**/admin/clients/*")
    shot(m, "24_admin_client_detail", "anna@demo.kivana.ru", full=True)
    go(m, "/admin/rooms")
    shot(m, "25_admin_rooms", "Апартаменты", full=True, rows="tbody tr")
    go(m, "/admin/services")
    shot(m, "26_admin_services", "Завтрак в номер", full=True, rows="tbody tr")
    go(m, "/admin/service-orders")
    m.select_option("#orders-status", value="")
    shot(m, "27_admin_service_orders", "Прачечная", full=True, rows="tbody tr")
    go(m, "/admin/housekeeping")
    shot(m, "28_admin_housekeeping", "Ежедневные уборки", full=True)
    go(m, "/admin/promos")
    shot(m, "29_admin_promos", "KIVANA-10", full=True, rows="tbody tr")


def capture_analogs(browser: Browser) -> None:
    ctx = browser.new_context(
        viewport=VIEWPORT,
        locale="ru-RU",
        timezone_id="Europe/Moscow",
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        ),
    )
    saved = 0
    for url in ANALOGS:
        page = ctx.new_page()
        try:
            response = page.goto(url, wait_until="load", timeout=60_000)
            # Снимаем через 2,5 с после load: картинки первого экрана уже есть, а рекламные окна
            # (у cosmosgroup.ru — через ~5 с) ещё не появились. Со страницей не взаимодействуем.
            page.wait_for_timeout(2_500)
            status = response.status if response else 0
            text = page.inner_text("body")
            problem = (
                f"HTTP {status}" if status >= 400
                else "мало текста" if len(text.strip()) < 200
                else f"признак блокировки «{m.group(0)}»" if (m := BLOCK_MARKERS.search(page.title() + " " + text[:3000]))
                else None
            )
            if problem:
                print(f"skip {url}: {problem}")
                continue
            name = f"analog_{saved + 1}"
            save(page, name, full=False)
            (TEXT / f"{name}.txt").write_text(url + " -> " + page.url + "\n\n" + text, encoding="utf-8")
            saved += 1
            if saved == 2:
                return
        except ShotError as error:
            print(f"skip {url}: {error}")
        except Exception as error:  # сеть, таймаут — сайт просто пропускается
            print(f"skip {url}: {type(error).__name__}: {str(error).splitlines()[0]}")
        finally:
            page.close()
    raise ShotError(f"Удалось снять только {saved} сайт(а)-аналога из двух")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--up", action="store_true", help="docker compose up -d --build и ожидание готовности")
    parser.add_argument("--site", action="store_true", help="скриншоты своего сайта")
    parser.add_argument("--analogs", action="store_true", help="скриншоты сайтов-аналогов")
    args = parser.parse_args()
    if not (args.site or args.analogs):
        args.site = args.analogs = True

    OUT.mkdir(parents=True, exist_ok=True)
    TEXT.mkdir(parents=True, exist_ok=True)
    expect.set_options(timeout=30_000)
    if args.up:
        subprocess.run(["docker", "compose", "up", "-d", "--build"], cwd=ROOT, check=True)
    if args.site:
        wait_ready()
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--lang=ru-RU"])  # формат дат в input type=date — русский
        if args.site:
            capture_site(browser)
        if args.analogs:
            capture_analogs(browser)
        browser.close()


if __name__ == "__main__":
    main()
