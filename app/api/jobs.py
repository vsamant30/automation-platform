from datetime import datetime

from fastapi import HTTPException
from app.services.job_runner import execute_job

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import Job
from app.schemas.job import JobCreate, JobResponse

router = APIRouter()


@router.get("/", response_model=list[JobResponse])
def get_jobs(db: Session = Depends(get_db)):
    return db.query(Job).all()


@router.post("/", response_model=JobResponse, status_code=201)
def create_job(job_data: JobCreate, db: Session = Depends(get_db)):
    new_job = Job(
        name=job_data.name,
        status="Pending",
    )

    db.add(new_job)
    db.commit()
    db.refresh(new_job)

    return new_job

@router.post("/{job_id}/run")
def run_job(job_id: int, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    try:
        job.status = "Running"
        job.started_at = datetime.utcnow()
        db.commit()

        result = execute_job(job.name)

        job.status = "Completed"
        job.result = result
        job.error_message = None

        job.completed_at = datetime.utcnow()
        job.duration = (
            job.completed_at - job.started_at
        ).total_seconds()

        db.commit()

        return {
            "job_id": job.id,
            "status": job.status,
            "result": result,
        }

    except Exception as error:

        job.status = "Failed"
        job.result = None
        job.error_message = str(error)

        job.completed_at = datetime.utcnow()

        if job.started_at:
            job.duration = (
                job.completed_at - job.started_at
            ).total_seconds()

        db.commit()

        raise HTTPException(
            status_code=500,
            detail=f"Job execution failed: {str(error)}",
        )