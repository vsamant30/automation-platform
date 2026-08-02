from datetime import datetime

from sqlalchemy.orm import Session

from app.db.models import AuditLog


def log_audit_event(
    db: Session,
    action: str,
    entity_type: str,
    entity_id: int | None = None,
    username: str | None = None,
    user_id: int | None = None,
    old_value: str | None = None,
    new_value: str | None = None,
    ip_address: str | None = None,
) -> AuditLog:
    """
    Create an audit log entry.
    """

    audit = AuditLog(
        user_id=user_id,
        username=username,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        old_value=old_value,
        new_value=new_value,
        ip_address=ip_address,
        created_at=datetime.utcnow(),
    )


    db.add(audit)
    db.flush()


    return audit