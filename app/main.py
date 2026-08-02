import os
import shutil

from app.services.job_name_validator import validate_job_name

from fastapi import HTTPException

from datetime import datetime

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.staticfiles import StaticFiles
from fastapi.requests import Request
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.api.jobs import router as jobs_router
from app.api.auth import router as auth_router
from app.api.pages import router as pages_router

from app.core.auth import (
    create_access_token,
    get_current_user_from_cookie,
    require_admin,
)

from app.core.security import verify_password
from app.db.database import engine
from app.db.models import Base

from app.db.database import SessionLocal
from app.db.models import Job, JobExecution, User

from app.api.users import router as users_router

from fastapi import Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.scheduler.scheduler import (
    start_scheduler,
    sync_job_schedule,
    pause_scheduled_job,
    resume_scheduled_job,
)

from app.services.execution_logger import get_execution_log_path

from app.services.job_execution_service import execute_job_with_history

from fastapi import FastAPI, Request, Form, HTTPException

from uuid import uuid4

app = FastAPI(
    title="Automation Platform",
    description="Local automation job management platform",
    version="1.0.0",
)

app.mount("/static", StaticFiles(directory="app/static"), name="static")

templates = Jinja2Templates(directory="app/templates")


@app.on_event("startup")
def startup_event():
    Base.metadata.create_all(bind=engine)
    start_scheduler()
    
    
@app.post("/login-page")
async def browser_login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    db = SessionLocal()

    try:
        cleaned_username = username.strip()

        user = (
            db.query(User)
            .filter(User.username == cleaned_username)
            .first()
        )

        if not user or not verify_password(
            password,
            user.hashed_password,
        ):
            return templates.TemplateResponse(
                request=request,
                name="login.html",
                context={
                    "request": request,
                    "error": "Invalid username or password.",
                },
                status_code=401,
            )

        if not user.is_active:
            return templates.TemplateResponse(
                request=request,
                name="login.html",
                context={
                    "request": request,
                    "error": "Your account is inactive. Contact the administrator.",
                },
                status_code=403,
            )

        token = create_access_token(
            {
                "sub": user.username,
                "role": user.role,
            }
        )

        response = RedirectResponse(
            url="/dashboard",
            status_code=303,
        )

        response.set_cookie(
            key="access_token",
            value=token,
            httponly=True,
            samesite="lax",
            secure=False,
            max_age=3600,
            path="/",
    )
        return response

    finally:
        db.close()
      

@app.get("/logout")
def logout():
    response = RedirectResponse(
        url="/login-page",
        status_code=303,
    )

    response.delete_cookie(
        key="access_token",
        path="/",
    )

    return response

            
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

        
            
@app.post("/upload-script")
def upload_script(
    request: Request,
    job_name: str = Form(...),
    description: str = Form(""),
    script_type: str = Form(...),
    script_file: UploadFile = File(...),
):
    db = SessionLocal()

    try:
        current_user = get_current_user_from_cookie(
            request,
            db,
        )

       

        require_admin(current_user)

        try:
            cleaned_job_name = validate_job_name(
                db=db,
                job_name=job_name,
            )

        except HTTPException as error:
            return templates.TemplateResponse(
                request=request,
                name="upload_script.html",
                context={
                    "request": request,
                    "current_user": current_user,
                    "validation_error": error.detail,
                    "job_name": job_name,
                    "description": description,
                    "script_type": script_type,
                },
                status_code=400,
         )

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
def create_job_from_dashboard(
    request: Request,
    job_name: str = Form(...),
    category: str = Form("General"),
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

        try:
            cleaned_name = validate_job_name(
                db=db,
                job_name=job_name,
            )

        except HTTPException as error:
            return RedirectResponse(
                url=f"/dashboard?validation_error={error.detail}",
                status_code=303,
            )

        new_job = Job(
            name=cleaned_name,
            category=category,
            status="Pending",
        )

        db.add(new_job)
        db.commit()
        db.refresh(new_job)

        return RedirectResponse(
            url="/dashboard?created=true",
            status_code=303,
        )

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()

@app.post("/dashboard/jobs/{job_id}/run")
def run_job_from_dashboard(
    request: Request,
    job_id: int,
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

        execute_job_with_history(
            db=db,
            job=job,
        )

        return RedirectResponse(
            url="/dashboard",
            status_code=303,
        )

    finally:
        db.close()        

@app.post("/dashboard/jobs/{job_id}/pause")
def pause_job_schedule(
    request: Request,
    job_id: int,
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

        pause_scheduled_job(job_id)

        return RedirectResponse(
            url="/dashboard?paused=true",
            status_code=303,
        )

    finally:
        db.close()


@app.post("/dashboard/jobs/{job_id}/resume")
def resume_job_schedule(
    request: Request,
    job_id: int,
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

        resume_scheduled_job(job_id)

        return RedirectResponse(
            url="/dashboard?resumed=true",
            status_code=303,
        )

    finally:
        db.close()
        

@app.post("/executions/{execution_id}/retry")
def retry_execution(
    request: Request,
    execution_id: int,
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

        job = (
            db.query(Job)
            .filter(Job.id == execution.job_id)
            .first()
        )

        if not job:
            raise HTTPException(
                status_code=404,
                detail="Job not found.",
            )

        execute_job_with_history(
            db=db,
            job=job,
        )

        return RedirectResponse(
           url="/history",
           status_code=303,
   )

    finally:
        db.close()

@app.post("/dashboard/jobs/{job_id}/duplicate")
def duplicate_job(
    request: Request,
    job_id: int,
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

        original_job = (
            db.query(Job)
            .filter(Job.id == job_id)
            .first()
        )

        if not original_job:
            return RedirectResponse(
                url="/dashboard",
                status_code=303,
            )

        duplicated_job = Job(
            name=f"{original_job.name} - Copy",
            description=original_job.description,
            script_type=original_job.script_type,
            script_path=original_job.script_path,
            status="Pending",
            schedule_enabled=False,
        )

        db.add(duplicated_job)
        db.commit()

        return RedirectResponse(
            url="/dashboard?duplicated=true",
            status_code=303,
        )

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()



@app.post("/dashboard/jobs/{job_id}/delete")
def delete_job(
    request: Request,
    job_id: int,
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

        if job:
            db.delete(job)
            db.commit()

        return RedirectResponse(
            url="/dashboard?deleted=true",
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

app.include_router(
    auth_router,
    tags=["Authentication"],
)

app.include_router(users_router)

app.include_router(
    pages_router,
    tags=["Browser Pages"],
)

