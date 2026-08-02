from sqlalchemy import inspect

from app.db.database import engine
from app.db.models import AuditLog


def create_audit_logs_table() -> None:
    """Create the audit_logs table safely if it does not already exist."""

    inspector = inspect(engine)

    if inspector.has_table(AuditLog.__tablename__):
        print("audit_logs table already exists. No changes required.")
        return

    AuditLog.__table__.create(
        bind=engine,
        checkfirst=True,
    )

    print("audit_logs table created successfully.")


if __name__ == "__main__":
    create_audit_logs_table()