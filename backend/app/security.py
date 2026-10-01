import hashlib
import secrets
import time
from collections import defaultdict

from fastapi import HTTPException, Request, status


def new_token() -> tuple[str, str]:
    """Случайный токен для cookie или ссылки из письма и его sha256: в БД хранится только хэш."""
    token = secrets.token_urlsafe(32)
    return token, hash_token(token)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class RateLimiter:
    """Не больше `limit` запросов за `window_seconds` с одного IP или, при per_client=False, со всего сайта.

    IP приходит из X-Forwarded-For, а dev-сервер Nuxt пропускает присланный клиентом заголовок как есть.
    Поэтому лимит по IP честного гостя защищает, но подделкой заголовка обходится;
    общий лимит на весь сайт обойти нельзя, он и ограничивает поток спама.

    ponytail: счётчики в памяти одного процесса и обнуляются при перезапуске;
    при нескольких воркерах uvicorn понадобится общее хранилище (Redis).
    """

    def __init__(self, limit: int, window_seconds: int, per_client: bool = True) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self.per_client = per_client
        self.hits: dict[str, list[float]] = defaultdict(list)

    def __call__(self, request: Request) -> None:
        now = time.monotonic()
        if not self.per_client:
            key = "*"
        else:
            key = request.client.host if request.client else "unknown"
        recent = [hit for hit in self.hits[key] if now - hit < self.window_seconds]
        if len(recent) >= self.limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Слишком много запросов. Попробуйте через несколько минут",
            )
        recent.append(now)
        self.hits[key] = recent
        if len(self.hits) > 10_000:
            self.hits = defaultdict(
                list, {ip: times for ip, times in self.hits.items() if now - times[-1] < self.window_seconds}
            )


TEN_MINUTES = 10 * 60
booking_limiters = [
    RateLimiter(limit=5, window_seconds=TEN_MINUTES),
    RateLimiter(limit=30, window_seconds=TEN_MINUTES, per_client=False),
]
login_limiters = [
    RateLimiter(limit=10, window_seconds=TEN_MINUTES),
    RateLimiter(limit=30, window_seconds=TEN_MINUTES, per_client=False),
]
# Регистрация, повторная отправка письма, «забыли пароль» и сброс пароля делят один счётчик:
# все они отправляют письма или проверяют токены из писем.
account_limiters = [
    RateLimiter(limit=10, window_seconds=TEN_MINUTES),
    RateLimiter(limit=30, window_seconds=TEN_MINUTES, per_client=False),
]
