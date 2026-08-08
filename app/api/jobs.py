from app.services.job_name_validator import (
    JOB_NAME_PATTERN,
    validate_job_name,
)

from app.services.job_execution_service import (
    execute_job_with_history,
)

from fastapi import APIRouter, Depends, HTTPException, Request, Query
from sqlalchemy.orm import Session

from app.core.auth import (
    get_current_user,
    get_current_user_from_cookie,
)


from app.core.permissions import require_admin
from app.db.database import get_db
from app.db.models import Job, User
from app.schemas.job import JobCreate, JobResponse
from app.services.audit_service import log_audit_event

router = APIRouter()


@router.get("/", response_model=list[JobResponse])
def get_jobs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return db.query(Job).all()


@router.post("/", response_model=JobResponse, status_code=201)
def create_job(
    job_data: JobCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):

    require_admin(current_user)

    job_name = validate_job_name(
        db=db,
        job_name=job_data.name,
    )

    new_job = Job(
        name=job_name,
        status="Pending",
        is_enabled=job_data.is_enabled,
    )

    db.add(new_job)
    db.flush()

    log_audit_event(
        db=db,
        user_id=current_user.id,
        username=current_user.username,
        action="CREATE_JOB",
        entity_type="Job",
        entity_id=new_job.id,
        new_value=f"Created job '{new_job.name}'",
    )

    db.commit()
    db.refresh(new_job)

    return new_job


@router.post("/{job_id}/run")
def run_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    job = db.query(Job).filter(Job.id == job_id).first()

    if not job:
        raise HTTPException(
            status_code=404,
            detail="Job not found",
        )

    require_admin(current_user)

    if not job.is_enabled:
        raise HTTPException(
            status_code=400,
            detail="Job is disabled.",
        )

    old_status = job.status

    log_audit_event(
        db=db,
        user_id=current_user.id,
        username=current_user.username,
        action="RUN_JOB",
        entity_type="Job",
        entity_id=job.id,
        old_value=old_status,
        new_value="Running (manual execution)",
    )

    db.commit()

    execution = execute_job_with_history(
        db=db,
        job=job,
    )

    if execution is None:
        raise HTTPException(
            status_code=500,
            detail="Job execution could not be created.",
        )

    return {
        "job_id": job.id,
        "execution_id": execution.id,
        "status": execution.status,
        "result": execution.result,
        "error_message": execution.error_message,
    }


@router.put("/{job_id}/toggle")
def toggle_job(
    request: Request,
    job_id: int,
    db: Session = Depends(get_db),
):
    current_user = get_current_user_from_cookie(
        request,
        db,
    )

    if not current_user:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated.",
        )

    require_admin(current_user)

    job = (
        db.query(Job)
        .filter(Job.id == job_id)
        .first()
    )

    if not job:
        raise HTTPException(
            status_code=404,
            detail="Job not found",
        )

    old_value = str(job.is_enabled)

    job.is_enabled = not job.is_enabled

    log_audit_event(
        db=db,
        user_id=current_user.id,
        username=current_user.username,
        action=(
            "ENABLE_JOB"
            if job.is_enabled
            else "DISABLE_JOB"
        ),
        entity_type="Job",
        entity_id=job.id,
        old_value=old_value,
        new_value=str(job.is_enabled),
    )

    db.commit()
    db.refresh(job)

    return {
        "job_id": job.id,
        "is_enabled": job.is_enabled,
        "message": (
            "Job enabled"
            if job.is_enabled
            else "Job disabled"
        ),
    }



@router.get("/check-name")
def check_job_name(
    name: str = Query(...),
    exclude_job_id: int | None = Query(None),
    db: Session = Depends(get_db),
):
    cleaned_name = name.strip()

    if not cleaned_name:
        return {
            "valid": False,
            "exists": False,
            "name": cleaned_name,
            "message": "Job name is required.",
        }

    if len(cleaned_name) > 100:
        return {
            "valid": False,
            "exists": False,
            "name": cleaned_name,
            "message": "Job name must not exceed 100 characters.",
        }

    if not JOB_NAME_PATTERN.fullmatch(cleaned_name):
        return {
            "valid": False,
            "exists": False,
            "name": cleaned_name,
            "message": (
                "Job name may contain only letters, numbers, "
                "spaces, underscores (_), and hyphens (-)."
            ),
        }

    query = db.query(Job).filter(
        Job.name.ilike(cleaned_name)
    )

    if exclude_job_id is not None:
        query = query.filter(
            Job.id != exclude_job_id
        )

    existing_job = query.first()

    if existing_job:
        return {
            "valid": False,
            "exists": True,
            "name": existing_job.name,
            "message": (
                f'Job name "{existing_job.name}" already exists. '
                "Please choose a different name."
            ),
        }

    return {
        "valid": True,
        "exists": False,
        "name": cleaned_name,
        "message": f'"{cleaned_name}" is available.',
    }




