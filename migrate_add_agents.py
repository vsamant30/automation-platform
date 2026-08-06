from sqlalchemy import inspect

from app.db.database import engine
from app.db.models import Agent


def migrate() -> None:
    inspector = inspect(engine)
    table_names = inspector.get_table_names()

    if Agent.__tablename__ in table_names:
        print("agents table already exists.")
        return

    Agent.__table__.create(
        bind=engine,
        checkfirst=True,
    )

    print("agents table created successfully.")


if __name__ == "__main__":
    migrate()