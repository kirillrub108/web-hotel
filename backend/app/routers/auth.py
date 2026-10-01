from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response, status
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.mail import send_mail
from app.mail_templates import account_exists_mail, reset_password_mail, verify_email_mail
from app.models import EmailToken, TokenPurpose, User
from app.passwords import check_password, hash_password, needs_rehash, verify_password
from app.schemas import ChangePasswordIn, EmailIn, LoginIn, RegisterIn, ResetPasswordIn, TokenIn, UserOut
from app.security import account_limiters, hash_token, login_limiters, new_token
from app.sessions import delete_sessions, end_session, require_user, start_session

router = APIRouter(prefix="/api/auth", tags=["auth"])

TOKEN_TTL = {
    TokenPurpose.VERIFY_EMAIL: timedelta(hours=24),
    TokenPurpose.RESET_PASSWORD: timedelta(hours=1),
}
MAIL_COOLDOWN = timedelta(seconds=60)
MAIL_HOURLY_LIMIT = 5

LOGIN_FAILED = "Неверный email или пароль"
# Вход на незарегистрированный email тоже проверяет пароль Argon2 — против этого хэша.
# Иначе такой ответ приходил бы заметно быстрее и выдавал, есть ли аккаунт.
DUMMY_PASSWORD_HASH = hash_password("пароль для выравнивания времени ответа")


def field_error(field: str, message: str) -> HTTPException:
    # Формат ошибок валидации FastAPI: фронт разбирает их одной функцией и показывает текст под полем.
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=[{"loc": ["body", field], "msg": message, "type": "value_error"}],
    )


def ensure_strong_password(password: str, field: str, email: str, full_name: str) -> None:
    problem = check_password(password, email=email, full_name=full_name)
    if problem:
        raise field_error(field, problem)


def mail_quota_left(db: Session, user: User, purpose: TokenPurpose) -> bool:
    """Не чаще одного письма в минуту и не больше пяти в час — по токенам, уже выпущенным в БД."""
    now = datetime.now(UTC)
    issued = db.scalars(
        select(EmailToken.created_at).where(
            EmailToken.user_id == user.id,
            EmailToken.purpose == purpose,
            EmailToken.created_at > now - timedelta(hours=1),
        )
    ).all()
    return len(issued) < MAIL_HOURLY_LIMIT and all(created < now - MAIL_COOLDOWN for created in issued)


def issue_email_token(db: Session, user: User, purpose: TokenPurpose) -> str:
    """Выпускает токен для ссылки из письма; прежние токены той же цели перестают работать."""
    now = datetime.now(UTC)
    db.execute(
        update(EmailToken)
        .where(EmailToken.user_id == user.id, EmailToken.purpose == purpose, EmailToken.used_at.is_(None))
        .values(used_at=now)
    )
    token, token_hash = new_token()
    db.add(
        EmailToken(
            user_id=user.id,
            purpose=purpose,
            token_hash=token_hash,
            created_at=now,
            expires_at=now + TOKEN_TTL[purpose],
        )
    )
    return token


def take_email_token(db: Session, token: str, purpose: TokenPurpose) -> EmailToken:
    # FOR UPDATE: при двойном клике второй запрос ждёт первый и затем видит токен уже использованным.
    email_token = db.scalar(
        select(EmailToken)
        .where(EmailToken.token_hash == hash_token(token), EmailToken.purpose == purpose)
        .with_for_update()
    )
    if email_token is None or not email_token.user.is_active:
        raise HTTPException(status_code=400, detail="Ссылка недействительна. Запросите новое письмо")
    if email_token.used_at is not None:
        raise HTTPException(
            status_code=400,
            detail="Ссылка уже использована или заменена более новой. Запросите новое письмо",
        )
    if email_token.expires_at <= datetime.now(UTC):
        raise HTTPException(status_code=400, detail="Срок действия ссылки истёк. Запросите новое письмо")
    return email_token


@router.post(
    "/register",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(limiter) for limiter in account_limiters],
)
def register(payload: RegisterIn, background: BackgroundTasks, db: Session = Depends(get_db)) -> None:
    # Пароль проверяется и хэшируется до поиска email: ответ и время ответа не зависят от того, занят ли адрес.
    ensure_strong_password(payload.password, "password", payload.email, payload.full_name)
    password_hash = hash_password(payload.password)

    existing = db.scalar(select(User).where(User.email == payload.email))
    if existing is not None:
        if existing.is_active:
            background.add_task(send_mail, account_exists_mail(existing.email, existing.full_name))
        return

    user = User(
        email=payload.email,
        password_hash=password_hash,
        full_name=payload.full_name,
        consent_at=datetime.now(UTC),
    )
    db.add(user)
    try:
        db.flush()
    except IntegrityError:
        # Тот же email зарегистрировали параллельным запросом — отвечаем так же, как для занятого адреса.
        db.rollback()
        return
    token = issue_email_token(db, user, TokenPurpose.VERIFY_EMAIL)
    db.commit()
    background.add_task(send_mail, verify_email_mail(user.email, user.full_name, token))


@router.post("/login", response_model=UserOut, dependencies=[Depends(limiter) for limiter in login_limiters])
def login(payload: LoginIn, response: Response, db: Session = Depends(get_db)) -> User:
    user = db.scalar(select(User).where(User.email == payload.email))
    password_ok = verify_password(user.password_hash if user else DUMMY_PASSWORD_HASH, payload.password)
    if user is None or not password_ok or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=LOGIN_FAILED)

    # Параметры Argon2 в библиотеке со временем усиливаются; пароль известен только сейчас, при входе.
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(payload.password)
    user.last_login_at = datetime.now(UTC)
    start_session(db, user, response)
    db.commit()
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response, db: Session = Depends(get_db)) -> None:
    end_session(db, request, response)
    db.commit()


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(require_user)) -> User:
    return user


# Подтверждение и сброс — только POST по кнопке на странице: почтовые сканеры заранее открывают
# ссылки из писем GET-запросом, и подтверждение по GET срабатывало бы без участия человека.
@router.post("/verify-email", status_code=status.HTTP_204_NO_CONTENT)
def verify_email(payload: TokenIn, db: Session = Depends(get_db)) -> None:
    email_token = take_email_token(db, payload.token, TokenPurpose.VERIFY_EMAIL)
    now = datetime.now(UTC)
    email_token.used_at = now
    if email_token.user.email_verified_at is None:
        email_token.user.email_verified_at = now
    db.commit()


@router.post(
    "/resend-verification",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(limiter) for limiter in account_limiters],
)
def resend_verification(
    background: BackgroundTasks,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> None:
    if user.email_verified_at is not None:
        raise HTTPException(status_code=400, detail="Email уже подтверждён")
    if not mail_quota_left(db, user, TokenPurpose.VERIFY_EMAIL):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Письмо можно отправлять не чаще раза в минуту и не больше пяти раз в час",
        )
    token = issue_email_token(db, user, TokenPurpose.VERIFY_EMAIL)
    db.commit()
    background.add_task(send_mail, verify_email_mail(user.email, user.full_name, token))


@router.post(
    "/forgot-password",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(limiter) for limiter in account_limiters],
)
def forgot_password(payload: EmailIn, background: BackgroundTasks, db: Session = Depends(get_db)) -> None:
    # Ответ всегда одинаковый: по нему нельзя узнать, зарегистрирован ли адрес.
    # Лимит по email, а не только по IP: иначе чужой ящик можно завалить письмами с разных адресов.
    user = db.scalar(select(User).where(User.email == payload.email))
    if user is None or not user.is_active or not mail_quota_left(db, user, TokenPurpose.RESET_PASSWORD):
        return
    token = issue_email_token(db, user, TokenPurpose.RESET_PASSWORD)
    db.commit()
    background.add_task(send_mail, reset_password_mail(user.email, user.full_name, token))


@router.post(
    "/reset-password",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(limiter) for limiter in account_limiters],
)
def reset_password(payload: ResetPasswordIn, db: Session = Depends(get_db)) -> None:
    email_token = take_email_token(db, payload.token, TokenPurpose.RESET_PASSWORD)
    user = email_token.user
    # Токен гасится только после проверки пароля: со слабым паролем можно исправить его и отправить снова.
    ensure_strong_password(payload.password, "password", user.email, user.full_name)

    now = datetime.now(UTC)
    email_token.used_at = now
    user.password_hash = hash_password(payload.password)
    # Ссылку открыл владелец ящика, значит, email заодно подтверждён.
    if user.email_verified_at is None:
        user.email_verified_at = now
    delete_sessions(db, user)
    db.commit()


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    payload: ChangePasswordIn,
    request: Request,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> None:
    if not verify_password(user.password_hash, payload.current_password):
        raise field_error("current_password", "Текущий пароль указан неверно")
    ensure_strong_password(payload.new_password, "new_password", user.email, user.full_name)

    user.password_hash = hash_password(payload.new_password)
    delete_sessions(db, user, keep_request=request)
    db.commit()
