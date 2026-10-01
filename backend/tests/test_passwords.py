import re
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

import seed
from app.models import User
from app.passwords import check_password, hash_password, verify_password

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def problem(password: str, email: str = "ivan@example.com", full_name: str = "Иван Петров") -> str | None:
    return check_password(password, email=email, full_name=full_name)


def test_common_password_rejected() -> None:
    assert problem("qwertyqwerty12345") == "Слишком распространённый пароль"


def test_password_like_email_or_name_rejected() -> None:
    email = "ivan.petrov.1990@example.com"
    assert problem(email, email=email) == "Похож на ваш email или имя"
    assert problem("kivana kivana kivana") == "Похож на ваш email или имя"


def test_predictable_password_rejected() -> None:
    assert problem("aaaaaaaaaaaaaaaa") == "Слишком предсказуемый — добавьте ещё одно слово"


@pytest.mark.parametrize(
    "passphrase",
    [
        "lantern copper orbit meadow",
        "медный фонарь над тихой рекой",
        "  spaces around are fine too  ",
    ],
)
def test_passphrase_accepted_without_composition_rules(passphrase: str) -> None:
    assert problem(passphrase) is None


def test_length_limits() -> None:
    assert problem("copper lantern") == "Пароль должен быть не короче 15 символов"
    assert problem("x" * 129) == "Пароль должен быть не длиннее 128 символов"


def test_length_counts_characters_after_nfc() -> None:
    # 15 букв «й», каждая набрана двумя кодовыми точками: после NFC это ровно 15 символов.
    decomposed = "й" * 15
    assert problem(decomposed) != "Пароль должен быть не короче 15 символов"


def test_hash_verifies_nfc_equivalent_password() -> None:
    password_hash = hash_password("мой пароль с буквой й")
    assert verify_password(password_hash, "мой пароль с буквой й")
    assert not verify_password(password_hash, "совсем другой пароль")
    assert not verify_password("not-a-hash", "мой пароль с буквой й")


def default_admin_passwords() -> list[str]:
    """Пароль админа по умолчанию из seed.py, а также из docker-compose.yml и .env.example, если они рядом.

    В контейнере backend файлов из корня проекта нет, зато seed.ADMIN_PASSWORD там — значение из compose.
    """
    passwords = [seed.ADMIN_PASSWORD]
    sources = {
        "docker-compose.yml": r"ADMIN_PASSWORD: \$\{ADMIN_PASSWORD:-(.+)\}",
        ".env.example": r'^ADMIN_PASSWORD="?(.*?)"?$',
    }
    for name, pattern in sources.items():
        path = PROJECT_ROOT / name
        if path.exists():
            found = re.search(pattern, path.read_text(encoding="utf-8"), re.MULTILINE)
            assert found, f"В {name} нет ADMIN_PASSWORD"
            passwords.append(found.group(1))
    return passwords


@pytest.mark.parametrize("password", default_admin_passwords())
def test_default_admin_password_passes_policy(password: str) -> None:
    assert check_password(password, email=seed.ADMIN_EMAIL, full_name=seed.ADMIN_FULL_NAME) is None


def test_seed_refuses_weak_admin_password(db: Session) -> None:
    with pytest.raises(SystemExit, match="ADMIN_PASSWORD не проходит политику паролей"):
        seed.create_admin(db, "weak-admin@example.com", "qwertyqwerty12345")


def test_seed_never_overwrites_existing_admin_password(db: Session) -> None:
    admin = db.scalars(select(User).where(User.email == seed.ADMIN_EMAIL)).one()
    password_hash = admin.password_hash

    seed.create_admin(db, seed.ADMIN_EMAIL, "совершенно другой длинный пароль")

    db.refresh(admin)
    assert admin.password_hash == password_hash
