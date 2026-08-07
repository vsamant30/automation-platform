from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.auth import (
    get_authenticated_agent_id,
    get_current_user,
)
from app.core.permissions import require_admin
from app.db.database import get_db
from app.db.models import AgentJob, Job, User
from app.schemas.api_response import ApiResponse
from app.schemas.job import JobCreate, JobResponse
from app.services.audit_service import log_audit_event
from app.services.job_name_validator import validate_job_name
from app.services.job_execution_service import execute_job_with_history



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


@router.get(
    "/workflow",
    response_model=ApiResponse[list[dict]],
)
def get_workflow_v1(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    jobs = db.query(Job).all()

    workflow = []

    for job in jobs:
        workflow.append(
            {
                "job_id": job.id,
                "job_name": job.name,
                "depends_on": job.dependency_job_id,
                "condition_type": job.condition_type,
                "condition_value": job.condition_value,
                "enabled": job.is_enabled,
            }
        )

    return ApiResponse(
        success=True,
        message="Workflow retrieved successfully.",
        data=workflow,
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

    if job_data.dependency_job_id is not None:
        dependency_job = (
            db.query(Job)
            .filter(
                Job.id == job_data.dependency_job_id
            )
            .first()
        )

        if dependency_job is None:
            raise HTTPException(
                status_code=400,
                detail="Dependency job does not exist.",
            )

    if (
        job_data.condition_type is not None
        or job_data.condition_value is not None
    ) and job_data.dependency_job_id is None:
        raise HTTPException(
            status_code=400,
            detail=(
                "Conditional execution requires "
                "a dependency job."
            ),
        )

    new_job = Job(
        name=job_name,
        status="Pending",
        is_enabled=job_data.is_enabled,
        dependency_job_id=job_data.dependency_job_id,
        condition_type=job_data.condition_type,
        condition_value=job_data.condition_value,
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

    execution = execute_job_with_history(
        db=db,
        job=job,
    )

    if execution is None:
        raise HTTPException(
            status_code=500,
            detail="Job execution could not be created.",
        )

    return ApiResponse(
        success=execution.status == "Completed",
        message=(
            "Job executed successfully."
            if execution.status == "Completed"
            else "Job execution failed."
        ),
        data={
            "job_id": job.id,
            "execution_id": execution.id,
            "status": execution.status,
            "result": execution.result,
            "error_message": execution.error_message,
        },
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


@router.get(
    "/{job_id}/script",
    response_class=FileResponse,
)
def download_job_script_v1(
    job_id: int,
    db: Session = Depends(get_db),
    authenticated_agent_id: int = Depends(
        get_authenticated_agent_id
    ),
):
    """
    Download the uploaded script belonging to one job
    assigned to the authenticated Remote Agent.
    """

    job = (
        db.query(Job)
        .filter(Job.id == job_id)
        .first()
    )

    if job is None:
        raise HTTPException(
            status_code=404,
            detail="Job not found.",
        )

    if not job.is_enabled:
        raise HTTPException(
            status_code=400,
            detail="Job is disabled.",
        )

    agent_job = (
        db.query(AgentJob)
        .filter(
            AgentJob.agent_id == authenticated_agent_id,
            AgentJob.job_id == job_id,
            AgentJob.status.in_(
                ["Claimed", "Running"]
            ),
        )
        .order_by(AgentJob.id.desc())
        .first()
    )

    if agent_job is None:
        raise HTTPException(
            status_code=403,
            detail=(
                "Job is not assigned to the "
                "authenticated Agent."
            ),
        )

    configured_script_path = (
        job.script_path or ""
    ).strip()

    if not configured_script_path:
        raise HTTPException(
            status_code=404,
            detail="Job script path is not configured.",
        )

    uploads_directory = (
        Path("uploads")
        .resolve()
    )

    script_path = Path(
        configured_script_path
    ).resolve()

    try:
        script_path.relative_to(
            uploads_directory
        )

    except ValueError as error:
        raise HTTPException(
            status_code=403,
            detail=(
                "Job script is outside the allowed "
                "uploads directory."
            ),
        ) from error

    if not script_path.is_file():
        raise HTTPException(
            status_code=404,
            detail="Job script file was not found.",
        )

    return FileResponse(
        path=str(script_path),
        filename=script_path.name,
        media_type="application/octet-stream",
    )