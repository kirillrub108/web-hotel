"""Сессии входа: случайный токен в httpOnly-cookie, в таблице sessions — только его sha256."""
import os
from datetime import UTC, datetime, timedelta

from fastapi import Depends, HTTPException, Request, Response, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, UserRole, UserSession
from app.security import hash_token, new_token

SESSION_TTL_GUEST_DAYS = int(os.getenv("SESSION_TTL_GUEST_DAYS", "14"))
SESSION_TTL_ADMIN_HOURS = int(os.getenv("SESSION_TTL_ADMIN_HOURS", "12"))
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"

SESSION_COOKIE = "kivana_session"


def session_ttl(user: User) -> timedelta:
    if user.role == UserRole.ADMIN:
        return timedelta(hours=SESSION_TTL_ADMIN_HOURS)
    return timedelta(days=SESSION_TTL_GUEST_DAYS)


def start_session(db: Session, user: User, response: Response) -> None:
    """Создаёт новую сессию и ставит cookie. Сессии на других устройствах остаются."""
    now = datetime.now(UTC)
    # Планировщика нет, поэтому истёкшие сессии пользователя убираются при его следующем входе.
    db.execute(delete(UserSession).where(UserSession.user_id == user.id, UserSession.expires_at <= now))
    token, token_hash = new_token()
    ttl = session_ttl(user)
    db.add(UserSession(user_id=user.id, token_hash=token_hash, expires_at=now + ttl))
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=int(ttl.total_seconds()),
        httponly=True,
        samesite="lax",
        secure=COOKIE_SECURE,
    )


def end_session(db: Session, request: Request, response: Response) -> None:
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        db.execute(delete(UserSession).where(UserSession.token_hash == hash_token(token)))
    response.delete_cookie(SESSION_COOKIE, httponly=True, samesite="lax", secure=COOKIE_SECURE)


def delete_sessions(db: Session, user: User, keep_request: Request | None = None) -> None:
    """Удаляет все сессии пользователя; с keep_request — все, кроме сессии этого запроса."""
    query = delete(UserSession).where(UserSession.user_id == user.id)
    current = keep_request.cookies.get(SESSION_COOKIE) if keep_request else None
    if current:
        query = query.where(UserSession.token_hash != hash_token(current))
    db.execute(query)


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    return db.scalar(
        select(User)
        .join(UserSession, UserSession.user_id == User.id)
        .where(
            UserSession.token_hash == hash_token(token),
            UserSession.expires_at > datetime.now(UTC),
            User.is_active,
        )
    )


def require_user(user: User | None = Depends(get_current_user)) -> User:
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Требуется вход")
    return user


def require_admin(user: User = Depends(require_user)) -> User:
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Доступ только для администратора")
    return user
