from sqlalchemy import inspect

from app.db.database import engine
from app.db.models import AgentJob


def migrate() -> None:
    inspector = inspect(engine)

    if AgentJob.__tablename__ in inspector.get_table_names():
        print("agent_jobs table already exists.")
        return

    AgentJob.__table__.create(
        bind=engine,
        checkfirst=True,
    )

    print("agent_jobs table created successfully.")


if __name__ == "__main__":
    migrate()