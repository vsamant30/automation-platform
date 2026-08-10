from getpass import getpass

from app.core.security import hash_password
from app.db.database import SessionLocal
from app.db.models import User


def create_user() -> None:
    username = input(
        "Username: "
    ).strip()

    email = input(
        "Email address: "
    ).strip()

    if not username:
        raise ValueError(
            "Username is required."
        )

    if not email:
        raise ValueError(
            "Email address is required."
        )

    db = SessionLocal()

    try:
        existing_user = (
            db.query(User)
            .filter(User.username == username)
            .first()
        )

        if existing_user:
            print(
                f"User '{username}' already exists. "
                "No changes were made."
            )
            return

        password = getpass(
            "Password: "
        )

        password_confirmation = getpass(
            "Confirm password: "
        )

        if len(password) < 12:
            raise ValueError(
                "Password must contain at least "
                "12 characters."
            )

        if password != password_confirmation:
            raise ValueError(
                "Password confirmation does not match."
            )

        user = User(
            username=username,
            email=email,
            hashed_password=hash_password(password),
            role="user",
            is_active=True,
        )

        db.add(user)
        db.commit()

        print(
            f"User '{username}' created successfully."
        )

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


if __name__ == "__main__":
    create_user()