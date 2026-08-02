import re

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.db.models import Job


JOB_NAME_PATTERN = re.compile(r"^[A-Za-z0-9 _-]+$")


def validate_job_name(
    db: Session,
    job_name: str,
    exclude_job_id: int | None = None,
) -> str:
    cleaned_name = job_name.strip()

    if not cleaned_name:
        raise HTTPException(
            status_code=400,
            detail="Job name is required.",
        )

    if len(cleaned_name) > 100:
        raise HTTPException(
            status_code=400,
            detail="Job name must not exceed 100 characters.",
        )

    if not JOB_NAME_PATTERN.fullmatch(cleaned_name):
        raise HTTPException(
            status_code=400,
            detail=(
                "Job name may contain only letters, numbers, "
                "spaces, underscores (_), and hyphens (-)."
            ),
        )

    query = db.query(Job).filter(
        Job.name.ilike(cleaned_name)
    )

    if exclude_job_id is not None:
        query = query.filter(
            Job.id != exclude_job_id
        )

    existing_job = query.first()

    if existing_job:
        raise HTTPException(
            status_code=400,
            detail=(
                f'Job name "{existing_job.name}" already exists. '
                "Please choose a different name."
            ),
        )

    return cleaned_name