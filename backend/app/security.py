import hashlib
import hmac
import os
import secrets
import time
from collections import defaultdict

from fastapi import HTTPException, Request, status

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")
# Без заданного ключа он генерируется при старте: безопасно, но сессии администратора сбрасываются при перезапуске.
SECRET_KEY = (os.getenv("SECRET_KEY") or secrets.token_hex(32)).encode()
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"

SESSION_COOKIE = "admin_session"
SESSION_TTL_SECONDS = 12 * 60 * 60


def credentials_match(username: str, password: str) -> bool:
    if not ADMIN_PASSWORD:
        return False
    # `&` вместо `and`: оба сравнения выполняются всегда, и время ответа не выдаёт, угадан ли логин.
    return hmac.compare_digest(username, ADMIN_USERNAME) & hmac.compare_digest(password, ADMIN_PASSWORD)


def _sign(payload: str) -> str:
    return hmac.new(SECRET_KEY, payload.encode(), hashlib.sha256).hexdigest()


def make_session_token() -> str:
    payload = f"{ADMIN_USERNAME}:{int(time.time()) + SESSION_TTL_SECONDS}"
    return f"{payload}:{_sign(payload)}"


def session_is_valid(token: str) -> bool:
    payload, _, signature = token.rpartition(":")
    if not payload or not hmac.compare_digest(signature, _sign(payload)):
        return False
    _, _, expires_at = payload.rpartition(":")
    return expires_at.isdigit() and int(expires_at) > time.time()


def require_admin(request: Request) -> None:
    token = request.cookies.get(SESSION_COOKIE, "")
    if not session_is_valid(token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Требуется вход администратора")


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
