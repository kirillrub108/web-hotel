"""Политика паролей по NIST SP 800-63B-4 и хэширование Argon2id.

NIST требует длину и проверку по словарям утёкших и предсказуемых паролей,
а правила состава («заглавная, цифра, спецсимвол») прямо запрещает: они не усиливают пароль,
а только подталкивают к шаблонам вроде «Password1!».
"""
import os
import unicodedata
from typing import Any

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from zxcvbn import zxcvbn

PASSWORD_MIN_LENGTH = int(os.getenv("PASSWORD_MIN_LENGTH", "15"))
PASSWORD_MAX_LENGTH = 128
MIN_ZXCVBN_SCORE = 3
# Название гостиницы совпадает с брендом, поэтому одного слова хватает на оба.
SITE_WORDS = ["kivana"]

hasher = PasswordHasher()


def check_password(password: str, *, email: str, full_name: str) -> str | None:
    """Возвращает причину отказа понятным текстом или None, если пароль подходит."""
    password = normalize_password(password)
    if len(password) < PASSWORD_MIN_LENGTH:
        return f"Пароль должен быть не короче {PASSWORD_MIN_LENGTH} символов"
    if len(password) > PASSWORD_MAX_LENGTH:
        return f"Пароль должен быть не длиннее {PASSWORD_MAX_LENGTH} символов"

    # Слова короче трёх букв не берём: иначе «aaaa…» засчитается как «похоже на email a@mail.ru».
    words = [email, email.partition("@")[0], full_name, *SITE_WORDS]
    user_inputs = [word for word in words if len(word) >= 3]
    result = zxcvbn(password, user_inputs=user_inputs, max_length=PASSWORD_MAX_LENGTH)
    if result["score"] >= MIN_ZXCVBN_SCORE:
        return None

    dictionaries = _dictionaries(result["sequence"])
    if "user_inputs" in dictionaries:
        return "Похож на ваш email или имя"
    if "passwords" in dictionaries:
        return "Слишком распространённый пароль"
    return "Слишком предсказуемый — добавьте ещё одно слово"


def _dictionaries(matches: list[dict[str, Any]]) -> set[str]:
    """Словари, в которых zxcvbn нашёл куски пароля; повтор («abcabc») хранит свои куски в base_matches."""
    found: set[str] = set()
    for match in matches:
        if match["pattern"] == "dictionary":
            found.add(match["dictionary_name"])
        found |= _dictionaries(match.get("base_matches", []))
    return found


def normalize_password(password: str) -> str:
    # NFC: «й», набранная одним символом и буквой с отдельным знаком, должна давать один и тот же хэш.
    return unicodedata.normalize("NFC", password)


def hash_password(password: str) -> str:
    return hasher.hash(normalize_password(password))


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return hasher.verify(password_hash, normalize_password(password))
    except (VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    return hasher.check_needs_rehash(password_hash)
