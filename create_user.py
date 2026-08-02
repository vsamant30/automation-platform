from app.core.security import hash_password
from app.db.database import SessionLocal
from app.db.models import User


def create_user():
    db = SessionLocal()

    try:
        existing_user = (
            db.query(User)
            .filter(User.username == "testuser")
            .first()
        )

        if existing_user:
            print("User already exists.")
            return

        user = User(
            username="testuser",
            email="testuser@localhost",
            hashed_password=hash_password("User@123"),
            role="user",
            is_active=True,
        )

        db.add(user)
        db.commit()

        print("Normal user created successfully!")

    finally:
        db.close()


if __name__ == "__main__":
    create_user()