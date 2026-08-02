from app.services.job_name_validator import validate_job_name

from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.core.auth import (
    get_current_user_from_cookie,
    require_admin,
)
from app.db.database import SessionLocal
from app.db.models import Job, JobExecution
from app.scheduler.scheduler import sync_job_schedule
from fastapi import HTTPException


router = APIRouter()

templates = Jinja2Templates(
    directory="app/templates"
)


@router.get(
    "/login-page",
    response_class=HTMLResponse,
)
async def login_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={
            "request": request,
            "error": None,
        },
    )


@router.get("/dashboard")
def dashboard(request: Request):
    db = SessionLocal()

    try:
        current_user = get_current_user_from_cookie(
            request,
            db,
        )

        if not current_user:
            return RedirectResponse(
                url="/login-page",
                status_code=303,
            )

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

        scheduled_jobs = (
            db.query(Job)
            .filter(Job.schedule_enabled == True)
            .count()
        )

        return templates.TemplateResponse(
            request=request,
            name="dashboard.html",
            context={
                "request": request,
                "current_user": current_user,
                "jobs": jobs,
                "total_jobs": total_jobs,
                "completed_jobs": completed_jobs,
                "running_jobs": running_jobs,
                "scheduled_jobs": scheduled_jobs,
                "failed_jobs": failed_jobs,
            },
        )

    finally:
        db.close()
        

@router.get("/api/dashboard-data")
def dashboard_data(request: Request):
    db = SessionLocal()

    try:
        current_user = get_current_user_from_cookie(
            request,
            db,
        )

        if not current_user:
            raise HTTPException(
                status_code=401,
                detail="Not authenticated",
            )

        jobs = db.query(Job).all()

        return {
            "statistics": {
                "total_jobs": db.query(Job).count(),
                "completed_jobs": (
                    db.query(Job)
                    .filter(Job.status == "Completed")
                    .count()
                ),
                "running_jobs": (
                    db.query(Job)
                    .filter(Job.status == "Running")
                    .count()
                ),
                "scheduled_jobs": (
                    db.query(Job)
                    .filter(Job.schedule_enabled == True)
                    .count()
                ),
                "failed_jobs": (
                    db.query(Job)
                    .filter(Job.status == "Failed")
                    .count()
                ),
            },
            "jobs": [
                {
                    "id": job.id,
                    "name": job.name,
                    "status": job.status,
                    "category": job.category,
                    "duration": job.duration,
                    "created_at": (
                        str(job.created_at)
                        if job.created_at
                        else ""
                    ),
                    
                    "is_enabled": job.is_enabled,
                    "schedule_enabled": job.schedule_enabled,
                    "schedule_paused": job.schedule_paused,
                }
                for job in jobs
            ],
        }

    finally:
        db.close()        
        
        
@router.get("/history")
def execution_history(request: Request):
    db = SessionLocal()

    try:
        current_user = get_current_user_from_cookie(
            request,
            db,
        )

        if not current_user:
            return RedirectResponse(
                url="/login-page",
                status_code=303,
            )

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
                "current_user": current_user,
                "executions": executions,
            },
        )

    finally:
        db.close()        
        
        
        
@router.get("/executions/{execution_id}/details")
def execution_details(
    execution_id: int,
    request: Request,
):
    db = SessionLocal()

    try:
        current_user = get_current_user_from_cookie(
            request,
            db,
        )

        if not current_user:
            return RedirectResponse(
                url="/login-page",
                status_code=303,
            )

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
                "current_user": current_user,
                "execution": execution,
                "job": job,
            },
        )

    finally:
        db.close()
        
        
@router.get("/jobs/{job_id}/details")
def job_details(job_id: int, request: Request):
    db = SessionLocal()

    try:
        current_user = get_current_user_from_cookie(
            request,
            db,
        )

        if not current_user:
            return RedirectResponse(
                url="/login-page",
                status_code=303,
            )

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
                "current_user": current_user,
                "job": job,
                "executions": executions,
            },
        )

    finally:
        db.close()
        
@router.get("/jobs/{job_id}/edit")
def edit_job_page(job_id: int, request: Request):
    db = SessionLocal()

    try:
        current_user = get_current_user_from_cookie(
            request,
            db,
        )

        if not current_user:
            return RedirectResponse(
                url="/login-page",
                status_code=303,
            )
            
        require_admin(current_user)    

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
                "current_user": current_user,
                "job": job,
            },
        )

    finally:
        db.close()
        
        
@router.get("/jobs/{job_id}/schedule")
def schedule_job_page(request: Request, job_id: int):
    db = SessionLocal()

    try:
        current_user = get_current_user_from_cookie(
            request,
            db,
        )

        if not current_user:
            return RedirectResponse(
                url="/login-page",
                status_code=303,
            )
            
        require_admin(current_user)

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
            name="schedule_job.html",
            context={
                "request": request,
                "current_user": current_user,
                "job": job,
            },
        )

    finally:
        db.close()
        
        
@router.get("/upload-script")
def upload_script_page(request: Request):
    db = SessionLocal()

    try:
        current_user = get_current_user_from_cookie(
            request,
            db,
        )

        if not current_user:
            return RedirectResponse(
                url="/login-page",
                status_code=303,
            )
            
        require_admin(current_user)    

        return templates.TemplateResponse(
            request=request,
            name="upload_script.html",
            context={
                "request": request,
                "current_user": current_user,
            },
        )

    finally:
        db.close()
        

@router.post("/jobs/{job_id}/edit")
def update_job(
    request: Request,
    job_id: int,
    job_name: str = Form(...),
    description: str = Form(""),
    script_type: str = Form(...),
    category: str = Form("General"),
    script_path: str = Form(...),
):
    db = SessionLocal()

    try:
        current_user = get_current_user_from_cookie(
            request,
            db,
        )

        if not current_user:
            return RedirectResponse(
                url="/login-page",
                status_code=303,
            )
            
        require_admin(current_user)    

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
            cleaned_name = validate_job_name(
                db=db,
                job_name=job_name,
                exclude_job_id=job_id,
            )
        except HTTPException as error:
            return RedirectResponse(
                url=(
                    f"/jobs/{job_id}/edit"
                    f"?validation_error={error.detail}"
                ),
                status_code=303,
            )
            
            
        job.name = cleaned_name
        
        
        
        
        job.description = description.strip()
        job.script_type = script_type.strip().lower()
        job.category = category.strip()
        job.script_path = script_path.strip()

        db.commit()

        return RedirectResponse(
            url=f"/jobs/{job.id}/details",
            status_code=303,
        )

    finally:
        db.close()
        
        
@router.post("/jobs/{job_id}/schedule")
def save_job_schedule(
    request: Request,
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
        current_user = get_current_user_from_cookie(
            request,
            db,
        )

        if not current_user:
            return RedirectResponse(
                url="/login-page",
                status_code=303,
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

        enabled = schedule_enabled is not None
        schedule_type = schedule_type.strip().lower()

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