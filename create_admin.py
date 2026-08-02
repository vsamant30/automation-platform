from app.db.database import SessionLocal
from app.db.models import User
from app.core.security import hash_password

db = SessionLocal()

username = "admin"
email = "admin@localhost"
password = "Admin@123"

existing = db.query(User).filter(User.username == username).first()

if existing:
    print("Admin user already exists.")
else:
    admin = User(
        username=username,
        email=email,
        hashed_password=hash_password(password),
        role="admin",
        is_active=True,
    )

    db.add(admin)
    db.commit()

    print("Admin user created successfully!")

db.close()