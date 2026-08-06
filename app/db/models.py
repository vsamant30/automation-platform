from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)

from app.db.database import Base


class Job(Base):
    __tablename__ = "jobs"

    # Primary Key
    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    # Job Information
    name = Column(
        String,
        nullable=False,
    )
    
    category = Column(
        String,
        nullable=False,
        default="General",
   )

    description = Column(
        Text,
        nullable=True,
    )

    script_type = Column(
        String,
        nullable=False,
        default="python",
    )

    script_path = Column(
        String,
        nullable=True,
    )

    # Optional dependency on another job.
    dependency_job_id = Column(
        Integer,
        ForeignKey("jobs.id"),
        nullable=True,
    )

    # Optional condition applied to the dependency result.
    condition_type = Column(
        String,
        nullable=True,
    )

    condition_value = Column(
        Text,
        nullable=True,
    )

    is_enabled = Column(
        Boolean,
        default=True,
        nullable=False,
    )
    
    
    # Scheduling Information
    schedule_enabled = Column(
        Boolean,
        default=False,
        nullable=False,
    )
    
    schedule_paused = Column(
        Boolean,
        default=False,
        nullable=False,
   )

    schedule_type = Column(
        String,
        default="manual",
        nullable=False,
    )

    schedule_value = Column(
        String,
        nullable=True,
    )

    next_run = Column(
        DateTime,
        nullable=True,
    )

    # Job Status
    status = Column(
        String,
        default="Pending",
    )

    result = Column(
        Text,
        nullable=True,
    )

    error_message = Column(
        Text,
        nullable=True,
    )

    # Execution Details
    started_at = Column(
        DateTime,
        nullable=True,
    )

    completed_at = Column(
        DateTime,
        nullable=True,
    )

    duration = Column(
        Float,
        nullable=True,
    )

    # Audit
    created_at = Column(
        DateTime,
        default=datetime.utcnow,
    )


class JobExecution(Base):
    __tablename__ = "job_executions"

    # Primary Key
    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    # Related Job Information
    job_id = Column(
        Integer,
        nullable=False,
    )

    job_name = Column(
        String,
        nullable=False,
    )

    # Execution Status
    status = Column(
        String,
        default="Running",
    )

    result = Column(
        Text,
        nullable=True,
    )

    error_message = Column(
        Text,
        nullable=True,
    )

    # Execution Timing
    started_at = Column(
        DateTime,
        nullable=True,
    )

    completed_at = Column(
        DateTime,
        nullable=True,
    )

    duration = Column(
        Float,
        nullable=True,
    )

    # Audit
    created_at = Column(
        DateTime,
        default=datetime.utcnow,
    )

class User(Base):
    __tablename__ = "users"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    username = Column(
        String,
        unique=True,
        index=True,
        nullable=False,
    )

    email = Column(
        String,
        unique=True,
        index=True,
        nullable=True,
    )

    hashed_password = Column(
        String,
        nullable=False,
    )

    role = Column(
        String,
        default="admin",
        nullable=False,
    )

    is_active = Column(
        Boolean,
        default=True,
        nullable=False,
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    user_id = Column(
        Integer,
        nullable=True,
    )

    username = Column(
        String,
        nullable=True,
    )

    action = Column(
        String,
        nullable=False,
        index=True,
    )

    entity_type = Column(
        String,
        nullable=False,
        index=True,
    )

    entity_id = Column(
        Integer,
        nullable=True,
    )

    old_value = Column(
        Text,
        nullable=True,
    )

    new_value = Column(
        Text,
        nullable=True,
    )

    ip_address = Column(
        String,
        nullable=True,
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        index=True,
    )

class ApplicationSettings(Base):
    __tablename__ = "application_settings"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    email_notifications_enabled = Column(
        Boolean,
        default=False,
        nullable=False,
    )

    smtp_host = Column(
        String,
        nullable=True,
    )

    smtp_port = Column(
        Integer,
        default=587,
        nullable=False,
    )

    smtp_username = Column(
        String,
        nullable=True,
    )

    smtp_password = Column(
        String,
        nullable=True,
    )

    smtp_use_tls = Column(
        Boolean,
        default=True,
        nullable=False,
    )

    smtp_use_ssl = Column(
        Boolean,
        default=False,
        nullable=False,
    )

    email_from_address = Column(
        String,
        nullable=True,
    )

    email_to_addresses = Column(
        Text,
        nullable=True,
    )

    notify_on_completed = Column(
        Boolean,
        default=True,
        nullable=False,
    )

    notify_on_failed = Column(
        Boolean,
        default=True,
        nullable=False,
    )

    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )