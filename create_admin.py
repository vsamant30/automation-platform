from getpass import getpass

from app.core.security import hash_password
from app.db.database import SessionLocal
from app.db.models import User


def create_admin() -> None:
    username = input(
        "Admin username [admin]: "
    ).strip() or "admin"

    email = input(
        "Admin email [admin@localhost]: "
    ).strip() or "admin@localhost"

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
            "Admin password: "
        )

        password_confirmation = getpass(
            "Confirm admin password: "
        )

        if len(password) < 12:
            raise ValueError(
                "Admin password must contain at least "
                "12 characters."
            )

        if password != password_confirmation:
            raise ValueError(
                "Password confirmation does not match."
            )

        admin = User(
            username=username,
            email=email,
            hashed_password=hash_password(password),
            role="admin",
            is_active=True,
        )

        db.add(admin)
        db.commit()

        print(
            f"Admin user '{username}' created successfully."
        )

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


if __name__ == "__main__":
    create_admin()