"""Шаблоны писем: каждая функция возвращает готовое письмо с HTML- и текстовой версией.

Новое письмо добавляется так же: функция с f-строками и вызов send_mail через BackgroundTasks.
"""
import os
from html import escape

from app.mail import Mail

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
