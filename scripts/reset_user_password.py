import argparse
import getpass
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from database.repositories.user_repository import (  # noqa: E402
    get_user_by_email,
    get_user_by_username,
    set_user_active,
)
from services.auth_service import (  # noqa: E402
    authenticate_user,
    reset_user_password,
)


MIN_PASSWORD_LENGTH = 8


def _find_user(identifier: str):
    normalized_identifier = identifier.strip().lower()
    return (
        get_user_by_email(normalized_identifier)
        or get_user_by_username(normalized_identifier)
    )


def _read_new_password() -> str:
    password = getpass.getpass("Новий пароль: ")

    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(
            f"Пароль повинен містити щонайменше {MIN_PASSWORD_LENGTH} символів."
        )

    confirmation = getpass.getpass("Повторіть новий пароль: ")

    if password != confirmation:
        raise ValueError("Введені паролі не збігаються.")

    return password


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Безпечно змінює пароль існуючого користувача."
    )
    parser.add_argument(
        "--user",
        default="admin@example.com",
        help="Email або логін користувача (типово: admin@example.com).",
    )
    args = parser.parse_args()

    user = _find_user(args.user)

    if not user:
        print(f"Користувача '{args.user}' не знайдено.", file=sys.stderr)
        return 1

    try:
        new_password = _read_new_password()
    except (EOFError, KeyboardInterrupt):
        print("\nЗміну пароля скасовано.", file=sys.stderr)
        return 1
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 1

    updated_user = reset_user_password(user.id, new_password)

    if not updated_user:
        print("Не вдалося змінити пароль.", file=sys.stderr)
        return 1

    if not updated_user.is_active:
        updated_user = set_user_active(updated_user.id, True)

    verified_user = authenticate_user(updated_user.email, new_password)

    if not verified_user:
        print("Пароль збережено, але контрольна авторизація не пройшла.", file=sys.stderr)
        return 1

    print(
        "Пароль успішно змінено. "
        f"Користувач: {verified_user.email}; роль: {verified_user.role}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
