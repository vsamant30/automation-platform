from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.permissions import require_admin
from app.db.database import get_db
from app.db.models import Job, User
from app.schemas.api_response import ApiResponse
from app.schemas.job import JobCreate, JobResponse
from app.services.audit_service import log_audit_event
from app.services.job_name_validator import validate_job_name
from app.services.job_runner import execute_job



router = APIRouter()


@router.get(
    "/",
    response_model=ApiResponse[list[JobResponse]],
)
def get_jobs_v1(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    jobs = db.query(Job).all()

    return ApiResponse(
        success=True,
        message="Jobs retrieved successfully.",
        data=jobs,
    )


@router.post(
    "/",
    response_model=ApiResponse[JobResponse],
    status_code=201,
)
def create_job_v1(
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

    try:
        db.add(new_job)
        db.flush()

        log_audit_event(
            db=db,
            user_id=current_user.id,
            username=current_user.username,
            action="CREATE_JOB",
            entity_type="Job",
            entity_id=new_job.id,
            new_value=(
                f"Created job '{new_job.name}' "
                "through API v1"
            ),
        )

        db.commit()
        db.refresh(new_job)

    except Exception:
        db.rollback()
        raise

    return ApiResponse(
        success=True,
        message="Job created successfully.",
        data=new_job,
    )

@router.post(
    "/{job_id}/run",
    response_model=ApiResponse[dict],
)
def run_job_v1(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
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

    if not job.is_enabled:
        raise HTTPException(
            status_code=400,
            detail="Job is disabled.",
        )

    old_status = job.status

    try:
        job.status = "Running"

        log_audit_event(
            db=db,
            user_id=current_user.id,
            username=current_user.username,
            action="RUN_JOB",
            entity_type="Job",
            entity_id=job.id,
            old_value=old_status,
            new_value="Running through API v1",
        )

        db.commit()

        result = execute_job(job.name)

        job.status = "Completed"
        job.result = result

        db.commit()

        return ApiResponse(
            success=True,
            message="Job executed successfully.",
            data={
                "job_id": job.id,
                "status": job.status,
                "result": result,
            },
        )

    except Exception as ex:

        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=str(ex),
        )

@router.put(
    "/{job_id}/toggle",
    response_model=ApiResponse[dict],
)
def toggle_job_v1(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
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

    try:
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

    except Exception:
        db.rollback()
        raise

    return ApiResponse(
        success=True,
        message=(
            "Job enabled successfully."
            if job.is_enabled
            else "Job disabled successfully."
        ),
        data={
            "job_id": job.id,
            "is_enabled": job.is_enabled,
        },
    )

@router.get(
    "/check-name",
    response_model=ApiResponse[dict],
)
def check_job_name_v1(
    name: str = Query(...),
    exclude_job_id: int | None = Query(None),
    db: Session = Depends(get_db),
):
    cleaned_name = name.strip()

    if not cleaned_name:
        return ApiResponse(
            success=False,
            message="Job name is required.",
            data={
                "valid": False,
                "exists": False,
                "name": cleaned_name,
            },
        )

    if len(cleaned_name) > 100:
        return ApiResponse(
            success=False,
            message="Job name must not exceed 100 characters.",
            data={
                "valid": False,
                "exists": False,
                "name": cleaned_name,
            },
        )

    validated_name = validate_job_name(
        db=db,
        job_name=cleaned_name,
        exclude_job_id=exclude_job_id,
    )

    return ApiResponse(
        success=True,
        message="Job name validation completed.",
        data={
            "valid": True,
            "exists": False,
            "name": validated_name,
        },
    )