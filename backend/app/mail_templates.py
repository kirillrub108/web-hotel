"""Шаблоны писем: каждая функция возвращает готовое письмо с HTML- и текстовой версией.

Новое письмо добавляется так же: функция с f-строками и вызов send_mail через BackgroundTasks.
Письма о бронях получают объект брони: связи room и user должны быть доступны в открытой сессии.
"""
import os
from html import escape

from app.booking_rules import reason_texts, rubles
from app.mail import Mail
from app.models import Actor, Booking

APP_BASE_URL = os.getenv("APP_BASE_URL", "http://localhost:3000").rstrip("/")


def _html(title: str, paragraphs: list[str], link: str, button: str) -> str:
    body = "".join(f"<p>{escape(paragraph)}</p>" for paragraph in paragraphs)
    return (
        f'<div style="font-family: Arial, sans-serif; font-size: 15px; color: #222; max-width: 520px">'
        f"<h2>{escape(title)}</h2>{body}"
        f'<p><a href="{escape(link)}" style="display: inline-block; padding: 10px 18px; background: #c1663a; '
        f'color: #fff; text-decoration: none; border-radius: 6px">{escape(button)}</a></p>'
        f'<p style="color: #777; font-size: 13px">Если кнопка не работает, откройте ссылку: {escape(link)}</p>'
        f"</div>"
    )


def verify_email_mail(to: str, full_name: str, token: str) -> Mail:
    link = f"{APP_BASE_URL}/verify-email?token={token}"
    paragraphs = [
        f"Здравствуйте, {full_name}!",
        "Подтвердите email, чтобы мы могли присылать вам письма о бронированиях. Ссылка действует 24 часа.",
    ]
    return Mail(
        to=to,
        subject="Подтвердите email — Kivana",
        html=_html("Подтверждение email", paragraphs, link, "Подтвердить email"),
        text="\n\n".join([*paragraphs, f"Подтвердить email: {link}"]),
    )


def reset_password_mail(to: str, full_name: str, token: str) -> Mail:
    link = f"{APP_BASE_URL}/reset-password?token={token}"
    paragraphs = [
        f"Здравствуйте, {full_name}!",
        "Мы получили запрос на сброс пароля. Ссылка действует 1 час.",
        "Если вы не запрашивали сброс, просто проигнорируйте письмо: пароль останется прежним.",
    ]
    return Mail(
        to=to,
        subject="Сброс пароля — Kivana",
        html=_html("Сброс пароля", paragraphs, link, "Задать новый пароль"),
        text="\n\n".join([*paragraphs, f"Задать новый пароль: {link}"]),
    )


def account_exists_mail(to: str, full_name: str) -> Mail:
    link = f"{APP_BASE_URL}/login"
    paragraphs = [
        f"Здравствуйте, {full_name}!",
        "Кто-то пытался зарегистрироваться на сайте Kivana с вашим email, но аккаунт уже существует.",
        "Если это были вы — войдите или восстановите пароль на странице входа. Если нет — ничего делать не нужно.",
    ]
    return Mail(
        to=to,
        subject="Аккаунт уже существует — Kivana",
        html=_html("Аккаунт уже существует", paragraphs, link, "Войти"),
        text="\n\n".join([*paragraphs, f"Войти: {link}"]),
    )


def _booking_summary(booking: Booking) -> str:
    return (
        f"{booking.room.name}, {booking.check_in:%d.%m.%Y} — {booking.check_out:%d.%m.%Y}, "
        f"ночей: {booking.nights}, гостей: {booking.guests}, сумма: {rubles(booking.total_price)}"
    )


def _booking_mail(booking: Booking, subject: str, title: str, paragraphs: list[str]) -> Mail:
    link = f"{APP_BASE_URL}/account/bookings/{booking.id}"
    paragraphs = [f"Здравствуйте, {booking.guest_name}!", *paragraphs]
    return Mail(
        to=booking.user.email,
        subject=f"{subject} — Kivana",
        html=_html(title, paragraphs, link, "Открыть бронь"),
        text="\n\n".join([*paragraphs, f"Открыть бронь: {link}"]),
    )


def _reason_lines(booking: Booking) -> list[str]:
    return [f"• {reason}" for reason in reason_texts(booking.reason_codes, booking.reason_text)]


def booking_review_mail(booking: Booking) -> Mail:
    paragraphs = [
        f"Мы получили заявку: {_booking_summary(booking)}.",
        "Администратор проверит её вручную и ответит письмом. Почему понадобилась проверка:",
        *_reason_lines(booking),
    ]
    return _booking_mail(booking, "Заявка на рассмотрении", "Заявка на рассмотрении", paragraphs)


def booking_confirmed_mail(booking: Booking) -> Mail:
    paragraphs = [
        f"Ваша бронь подтверждена: {_booking_summary(booking)}.",
        "Ждём вас! Отменить бронь можно в личном кабинете.",
    ]
    return _booking_mail(booking, "Бронь подтверждена", "Бронь подтверждена", paragraphs)


def booking_declined_mail(booking: Booking) -> Mail:
    paragraphs = [
        f"К сожалению, мы не можем подтвердить бронь: {_booking_summary(booking)}.",
        "Причина:",
        *_reason_lines(booking),
        "Выберите другие даты или номер на сайте либо позвоните нам — поможем подобрать вариант.",
    ]
    return _booking_mail(booking, "Бронь не подтверждена", "Бронь не подтверждена", paragraphs)


def booking_cancelled_mail(booking: Booking) -> Mail:
    if booking.cancelled_by == Actor.GUEST:
        who = ["Вы отменили бронь в личном кабинете."]
    else:
        who = ["Бронь отменил администратор отеля. Причина:", *_reason_lines(booking)]
    paragraphs = [f"Бронь отменена: {_booking_summary(booking)}.", *who]
    return _booking_mail(booking, "Бронь отменена", "Бронь отменена", paragraphs)


def admin_review_mail(to: str, booking: Booking) -> Mail:
    link = f"{APP_BASE_URL}/admin"
    paragraphs = [
        f"Заявка №{booking.id} ждёт решения: {_booking_summary(booking)}.",
        f"Гость: {booking.guest_name}, {booking.phone}, {booking.user.email}.",
        "Причины ручного разбора:",
        *_reason_lines(booking),
    ]
    return Mail(
        to=to,
        subject=f"Заявка №{booking.id} на разборе — Kivana",
        html=_html("Заявка на разборе", paragraphs, link, "Открыть заявки"),
        text="\n\n".join([*paragraphs, f"Открыть заявки: {link}"]),
    )
