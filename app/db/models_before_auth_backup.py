from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
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

    # Scheduling Information
    schedule_enabled = Column(
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