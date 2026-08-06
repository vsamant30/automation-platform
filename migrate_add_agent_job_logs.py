from sqlalchemy import inspect

from app.db.database import engine
from app.db.models import AgentJobLog


def main() -> None:
    inspector = inspect(engine)

    if "agent_job_logs" in inspector.get_table_names():
        print("agent_job_logs table already exists.")
        return

    AgentJobLog.__table__.create(
        bind=engine,
        checkfirst=True,
    )

    print("agent_job_logs table created successfully.")


if __name__ == "__main__":
    main()