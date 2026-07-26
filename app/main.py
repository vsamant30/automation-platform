import os
import shutil

from datetime import datetime

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.requests import Request
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.api.jobs import router as jobs_router
from app.db.database import SessionLocal
from app.db.models import Job, JobExecution

from app.scheduler.scheduler import (
    start_scheduler,
    sync_job_schedule,
)

from app.services.execution_logger import (
    get_execution_log_path,
    write_execution_log,
)

from app.services.job_runner import execute_job

from fastapi import FastAPI, Request, Form, HTTPException

from uuid import uuid4

app = FastAPI(
    title="Automation Platform",
    description="Local automation job management platform",
    version="1.0.0",
)

templates = Jinja2Templates(directory="app/templates")


@app.on_event("startup")
def startup_event():
    start_scheduler()


@app.get("/dashboard")
def dashboard(request: Request):
    db = SessionLocal()

    try:
        jobs = db.query(Job).all()

        total_jobs = db.query(Job).count()

        completed_jobs = (
            db.query(Job)
            .filter(Job.status == "Completed")
            .count()
        )

        running_jobs = (
            db.query(Job)
            .filter(Job.status == "Running")
            .count()
        )

        failed_jobs = (
            db.query(Job)
            .filter(Job.status == "Failed")
            .count()
        )

        return templates.TemplateResponse(
            request=request,
            name="dashboard.html",
            context={
                "request": request,
                "jobs": jobs,
                "total_jobs": total_jobs,
                "completed_jobs": completed_jobs,
                "running_jobs": running_jobs,
                "failed_jobs": failed_jobs,
            },
        )

    finally:
        db.close()
        

@app.get("/history")
def execution_history(request: Request):
    db = SessionLocal()

    try:
        executions = (
            db.query(JobExecution)
            .order_by(JobExecution.id.desc())
            .all()
        )

        return templates.TemplateResponse(
            request=request,
            name="history.html",
            context={
                "request": request,
                "executions": executions,
            },
        )

    finally:
        db.close()        

@app.get("/executions/{execution_id}/details")
def execution_details(
    execution_id: int,
    request: Request,
):
    db = SessionLocal()

    try:
        execution = (
            db.query(JobExecution)
            .filter(JobExecution.id == execution_id)
            .first()
        )

        if not execution:
            return RedirectResponse(
                url="/history",
                status_code=303,
            )

        job = (
            db.query(Job)
            .filter(Job.id == execution.job_id)
            .first()
        )

        return templates.TemplateResponse(
            request=request,
            name="execution_details.html",
            context={
                "request": request,
                "execution": execution,
                "job": job,
            },
        )

    finally:
        db.close()

@app.get("/jobs/{job_id}/details")
def job_details(job_id: int, request: Request):
    db = SessionLocal()

    try:
        job = (
            db.query(Job)
            .filter(Job.id == job_id)
            .first()
        )

        if not job:
            return RedirectResponse(
                url="/dashboard",
                status_code=303,
            )

        executions = (
            db.query(JobExecution)
            .filter(JobExecution.job_id == job_id)
            .order_by(JobExecution.id.desc())
            .limit(10)
            .all()
        )

        return templates.TemplateResponse(
            request=request,
            name="job_details.html",
            context={
                "request": request,
                "job": job,
                "executions": executions,
            },
        )

    finally:
        db.close()
        
@app.get("/executions/{execution_id}/download")
def download_execution_log(execution_id: int):
    db = SessionLocal()

    try:
        execution = (
            db.query(JobExecution)
            .filter(JobExecution.id == execution_id)
            .first()
        )

        if not execution:
            raise HTTPException(
                status_code=404,
                detail="Execution not found.",
            )

        log_path = get_execution_log_path(execution_id)

        if not log_path.exists():
            raise HTTPException(
                status_code=404,
                detail="Execution log file not found.",
            )

        return FileResponse(
            path=str(log_path),
            media_type="text/plain",
            filename=log_path.name,
        )

    finally:
        db.close()

@app.get("/jobs/{job_id}/edit")
def edit_job_page(job_id: int, request: Request):
    db = SessionLocal()

    try:
        job = (
            db.query(Job)
            .filter(Job.id == job_id)
            .first()
        )

        if not job:
            return RedirectResponse(
                url="/dashboard",
                status_code=303,
            )

        return templates.TemplateResponse(
            request=request,
            name="edit_job.html",
            context={
                "request": request,
                "job": job,
            },
        )

    finally:
        db.close()


@app.get("/jobs/{job_id}/schedule")
def schedule_job_page(request: Request, job_id: int):
    db = SessionLocal()

    try:
        job = db.query(Job).filter(Job.id == job_id).first()

        if not job:
            raise HTTPException(
                status_code=404,
                detail="Job not found",
            )

        return templates.TemplateResponse(
            request=request,
            name="schedule_job.html",
            context={
                "request": request,
                "job": job,
           },
        )

    finally:
        db.close()



@app.post("/jobs/{job_id}/schedule")
def save_job_schedule(
    job_id: int,
    schedule_enabled: str | None = Form(None),
    schedule_type: str = Form("manual"),
    interval_minutes: str = Form(""),
    schedule_time: str = Form(""),
    schedule_day: str = Form("mon"),
    cron_expression: str = Form(""),
):
    db = SessionLocal()

    try:
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

        enabled = schedule_enabled is not None
        schedule_type = schedule_type.strip().lower()

        # Manual or unchecked scheduling
        if not enabled or schedule_type == "manual":
            job.schedule_enabled = False
            job.schedule_type = "manual"
            job.schedule_value = None
            job.next_run = None

        elif schedule_type == "interval":
            try:
                minutes = int(interval_minutes)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail="Interval must be a valid number.",
                )

            if minutes < 1:
                raise HTTPException(
                    status_code=400,
                    detail="Interval must be at least 1 minute.",
                )

            job.schedule_enabled = True
            job.schedule_type = "interval"
            job.schedule_value = str(minutes)
            job.next_run = None

        elif schedule_type == "hourly":
            if not schedule_time:
                raise HTTPException(
                    status_code=400,
                    detail="Please select an execution time.",
                )

            job.schedule_enabled = True
            job.schedule_type = "hourly"
            job.schedule_value = schedule_time
            job.next_run = None

        elif schedule_type == "daily":
            if not schedule_time:
                raise HTTPException(
                    status_code=400,
                    detail="Please select a daily execution time.",
                )

            job.schedule_enabled = True
            job.schedule_type = "daily"
            job.schedule_value = schedule_time
            job.next_run = None

        elif schedule_type == "weekly":
            if not schedule_time:
                raise HTTPException(
                    status_code=400,
                    detail="Please select a weekly execution time.",
                )

            valid_days = {
                "mon",
                "tue",
                "wed",
                "thu",
                "fri",
                "sat",
                "sun",
            }

            if schedule_day not in valid_days:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid day of the week.",
                )

            job.schedule_enabled = True
            job.schedule_type = "weekly"
            job.schedule_value = (
                f"{schedule_day}|{schedule_time}"
            )
            job.next_run = None

        elif schedule_type == "cron":
            cleaned_cron = cron_expression.strip()

            if len(cleaned_cron.split()) != 5:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Cron expression must contain "
                        "exactly 5 fields."
                    ),
                )

            job.schedule_enabled = True
            job.schedule_type = "cron"
            job.schedule_value = cleaned_cron
            job.next_run = None

        else:
            raise HTTPException(
                status_code=400,
                detail="Unsupported schedule type.",
            )

        db.commit()
        db.refresh(job)

        sync_job_schedule(job.id)

        return RedirectResponse(
            url=f"/jobs/{job.id}/details",
            status_code=303,
        )

    except HTTPException:
        db.rollback()
        raise

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()




@app.post("/jobs/{job_id}/edit")
def update_job(
    job_id: int,
    job_name: str = Form(...),
    description: str = Form(""),
    script_type: str = Form(...),
    script_path: str = Form(...),
):
    db = SessionLocal()

    try:
        job = (
            db.query(Job)
            .filter(Job.id == job_id)
            .first()
        )

        if not job:
            return RedirectResponse(
                url="/dashboard",
                status_code=303,
            )

        job.name = job_name.strip()
        job.description = description.strip()
        job.script_type = script_type.strip().lower()
        job.script_path = script_path.strip()

        db.commit()

        return RedirectResponse(
            url=f"/jobs/{job.id}/details",
            status_code=303,
        )

    finally:
        db.close()

@app.get("/upload-script")
def upload_script_page(request: Request):

    return templates.TemplateResponse(
        request=request,
        name="upload_script.html",
        context={
            "request": request,
        },
    )
    
@app.post("/upload-script")
def upload_script(
    job_name: str = Form(...),
    description: str = Form(""),
    script_type: str = Form(...),
    script_file: UploadFile = File(...),
):
    db = SessionLocal()

    try:
        cleaned_job_name = job_name.strip()
        cleaned_description = description.strip()
        cleaned_script_type = script_type.strip().lower()

        if not cleaned_job_name:
            return RedirectResponse(
                url="/upload-script",
                status_code=303,
            )

        allowed_extensions = {
            "python": ".py",
            "powershell": ".ps1",
            "batch": (".bat", ".cmd"),
        }

        if cleaned_script_type not in allowed_extensions:
            return RedirectResponse(
                url="/upload-script",
                status_code=303,
            )

        original_filename = os.path.basename(
            script_file.filename or ""
        )

        file_extension = os.path.splitext(
            original_filename
        )[1].lower()

        expected_extension = allowed_extensions[
            cleaned_script_type
        ]

        if isinstance(expected_extension, tuple):
            extension_is_valid = (
                file_extension in expected_extension
            )
        else:
            extension_is_valid = (
                file_extension == expected_extension
            )

        if not extension_is_valid:
            return RedirectResponse(
                url="/upload-script",
                status_code=303,
            )

        safe_filename = "".join(
            character
            if character.isalnum() or character in "._-"
            else "_"
            for character in original_filename
        )

        if not safe_filename:
            return RedirectResponse(
                url="/upload-script",
                status_code=303,
            )

        upload_directory = os.path.abspath("uploads")
        os.makedirs(upload_directory, exist_ok=True)

        filename_without_extension = os.path.splitext(
            safe_filename
        )[0]

        unique_filename = (
            f"{filename_without_extension}_"
            f"{uuid4().hex[:8]}"
            f"{file_extension}"
        )

        destination_path = os.path.join(
            upload_directory,
            unique_filename,
        )
        
        with open(destination_path, "wb") as destination_file:
            shutil.copyfileobj(
                script_file.file,
                destination_file,
            )

        new_job = Job(
            name=cleaned_job_name,
            description=cleaned_description,
            script_type=cleaned_script_type,
            script_path=destination_path,
            status="Pending",
        )

        db.add(new_job)
        db.commit()
        db.refresh(new_job)

        return RedirectResponse(
            url=f"/jobs/{new_job.id}/details",
            status_code=303,
        )

    except Exception:
        db.rollback()
        raise

    finally:
        script_file.file.close()
        db.close()

@app.post("/dashboard/jobs/create")
def create_job_from_dashboard(job_name: str = Form(...)):
    db = SessionLocal()

    try:
        cleaned_name = job_name.strip()

        if not cleaned_name:
            return RedirectResponse(
                url="/dashboard",
                status_code=303,
            )

        new_job = Job(
            name=cleaned_name,
            status="Pending",
        )

        db.add(new_job)
        db.commit()

        return RedirectResponse(
            url="/dashboard",
            status_code=303,
        )

    finally:
        db.close()


@app.post("/dashboard/jobs/{job_id}/run")
def run_job_from_dashboard(job_id: int):
    db = SessionLocal()
    execution = None

    try:
        job = (
            db.query(Job)
            .filter(Job.id == job_id)
            .first()
        )

        if not job:
            return RedirectResponse(
                url="/dashboard",
                status_code=303,
            )

        try:
            started_at = datetime.utcnow()

            job.status = "Running"
            job.started_at = started_at
            job.completed_at = None
            job.duration = None
            job.result = None
            job.error_message = None

            execution = JobExecution(
                job_id=job.id,
                job_name=job.name,
                status="Running",
                started_at=started_at,
            )

            db.add(execution)
            db.commit()

            db.refresh(job)
            db.refresh(execution)

            result = execute_job(job)

            completed_at = datetime.utcnow()
            duration = (
                completed_at - started_at
            ).total_seconds()

            job.status = "Completed"
            job.result = result
            job.error_message = None
            job.completed_at = completed_at
            job.duration = duration

            execution.status = "Completed"
            execution.result = result
            execution.error_message = None
            execution.completed_at = completed_at
            execution.duration = duration

            db.commit()
            db.refresh(execution)
            write_execution_log(job, execution)

        except Exception as error:
            completed_at = datetime.utcnow()

            job.status = "Failed"
            job.result = None
            job.error_message = str(error)
            job.completed_at = completed_at

            if job.started_at:
                job.duration = (
                    completed_at - job.started_at
                ).total_seconds()

            if execution is not None:
                execution.status = "Failed"
                execution.result = None
                execution.error_message = str(error)
                execution.completed_at = completed_at
                execution.duration = job.duration

            db.commit()

            if execution is not None:
                db.refresh(execution)
                write_execution_log(job, execution)

        return RedirectResponse(
            url="/dashboard",
            status_code=303,
        )

    finally:
        db.close()

@app.post("/dashboard/jobs/{job_id}/delete")
def delete_job_from_dashboard(job_id: int):
    db = SessionLocal()

    try:
        job = (
            db.query(Job)
            .filter(Job.id == job_id)
            .first()
        )

        if job:
            db.delete(job)
            db.commit()

        return RedirectResponse(
            url="/dashboard",
            status_code=303,
        )

    finally:
        db.close()


@app.get("/")
def root():
    return {
        "status": "success",
        "message": "Automation Platform API is running",
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
    }


app.include_router(
    jobs_router,
    prefix="/jobs",
    tags=["Jobs"],
)