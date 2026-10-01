"""Отправка писем. Бэкенд выбирается переменной MAIL_BACKEND:

- resend — через HTTP API Resend;
- console — письмо и ссылки печатаются в лог backend (весь сценарий работает без ключа);
- memory — письма копятся в списке outbox, его читают тесты.
"""
import logging
import os
from dataclasses import dataclass

import httpx

RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
MAIL_BACKEND = os.getenv("MAIL_BACKEND") or ("resend" if RESEND_API_KEY else "console")
MAIL_FROM = os.getenv("MAIL_FROM", "Kivana <no-reply@kivana.ru>")
RESEND_URL = "https://api.resend.com/emails"

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Mail:
    to: str
    subject: str
    html: str
    text: str


outbox: list[Mail] = []


def send_mail(mail: Mail) -> None:
    """Вызывается из BackgroundTasks: ошибка доставки попадает в лог и не ломает уже отправленный ответ."""
    try:
        if MAIL_BACKEND == "resend":
            response = httpx.post(
                RESEND_URL,
                headers={"Authorization": f"Bearer {RESEND_API_KEY}"},
                json={
                    "from": MAIL_FROM,
                    "to": [mail.to],
                    "subject": mail.subject,
                    "html": mail.html,
                    "text": mail.text,
                },
                timeout=10,
            )
            response.raise_for_status()
        elif MAIL_BACKEND == "memory":
            outbox.append(mail)
        else:
            logger.info("Письмо для %s: %s\n%s", mail.to, mail.subject, mail.text)
    except Exception:
        logger.exception("Не удалось отправить письмо «%s» на %s", mail.subject, mail.to)
