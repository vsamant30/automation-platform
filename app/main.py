import json
import os
import shutil

from datetime import datetime
from threading import Lock, Thread
from uuid import uuid4

from fastapi import (
    FastAPI,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
)
from fastapi.exceptions import RequestValidationError
from fastapi.responses import (
    FileResponse,
    HTMLResponse,
    RedirectResponse,
)
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.api.auth import router as auth_router
from app.api.auth_v1 import router as auth_v1_router
from app.api.agents_v1 import router as agents_v1_router
from app.api.agent_jobs_v1 import router as agent_jobs_v1_router
from app.api.jobs import router as jobs_router
from app.api.jobs_v1 import router as jobs_v1_router
from app.api.pages import router as pages_router
from app.api.users import router as users_router
from app.api.users_v1 import router as users_v1_router

from app.core.auth import (
    create_access_token,
    get_current_user_from_cookie,
    require_admin,
)
from app.core.exceptions import (
    generic_exception_handler,
    validation_exception_handler,
)
from app.core.security import verify_password

from app.db.database import SessionLocal, engine
from app.db.models import (
    Base,
    Job,
    JobExecution,
    User,
)

from app.scheduler.scheduler import (
    pause_scheduled_job,
    resume_scheduled_job,
    start_scheduler,
    sync_job_schedule,
)

from app.services.audit_service import log_audit_event
from app.services.execution_logger import (
    get_execution_log_path,
)
from app.services.job_execution_service import (
    execute_job_with_history,
)
from app.services.job_runner import stop_active_execution

from app.services.job_name_validator import (
    validate_job_name,
)


OPENAPI_TAGS = [
    {
        "name": "API v1 - Authentication",
        "description": (
            "Authenticate API clients, generate JWT access "
            "tokens, and retrieve the authenticated profile."
        ),
    },
    {
        "name": "API v1 - Agents",
        "description": (
            "Register, retrieve, update, and remove "
            "remote execution agents."
        ),
    },
    {
        "name": "API v1 - Agent Jobs",
        "description": (
            "Queue, claim, run, complete, and fail "
            "remote execution jobs."
        ),
    },
    {
        "name": "API v1 - Jobs",
        "description": (
            "Create, view, validate, execute, and control "
            "automation jobs through the versioned REST API."
        ),
    },
    {
        "name": "API v1 - Users",
        "description": (
            "Administer platform users and role-based access."
        ),
    },
    {
        "name": "Legacy Authentication API",
        "description": (
            "Unversioned authentication endpoints retained "
            "for backward compatibility."
        ),
    },
    {
        "name": "Legacy Jobs API",
        "description": (
            "Unversioned job endpoints retained for backward "
            "compatibility."
        ),
    },
    {
        "name": "Legacy Users API",
        "description": (
            "Unversioned user endpoints retained for backward "
            "compatibility."
        ),
    },
    {
        "name": "System",
        "description": (
            "Basic platform status and health-check endpoints."
        ),
    },
]

app = FastAPI(
    title="Automation Platform API",
    summary=(
        "Enterprise automation orchestration and "
        "job-management API."
    ),
    description="""
# Automation Platform API

The Automation Platform provides browser-based administration
and versioned REST APIs for managing and executing automation
jobs.

## Core capabilities

- JWT bearer authentication
- Role-based access control
- Job creation and execution
- Scheduling and pause/resume controls
- Dependency and conditional workflow support
- Execution history and downloadable logs
- Audit logging
- Configurable email notifications
- Versioned REST endpoints

## Authentication

Protected REST endpoints require a JWT access token.

1. Call `POST /api/v1/auth/login`.
2. Copy the returned access token.
3. Select **Authorize** in Swagger.
4. Enter the token in the Bearer authentication field.

Swagger normally adds the `Bearer` prefix automatically when
using its authorization dialog.

## Recommended API version

New integrations should use endpoints under `/api/v1`.

Unversioned endpoints remain available only for backward
compatibility.
""",
    version="2.0.0",
    contact={
        "name": "Vinayak Samant",
    },
    openapi_tags=OPENAPI_TAGS,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    swagger_ui_parameters={
        "persistAuthorization": True,
        "filter": True,
        "displayRequestDuration": True,
        "docExpansion": "none",
        "defaultModelsExpandDepth": 1,
        "defaultModelExpandDepth": 1,
        "tryItOutEnabled": True,
    },
)

app.add_exception_handler(
    RequestValidationError,
    validation_exception_handler,
)

app.add_exception_handler(
    Exception,
    generic_exception_handler,
)

app.mount("/static", StaticFiles(directory="app/static"), name="static")

templates = Jinja2Templates(directory="app/templates")

_manual_run_lock = Lock()
_manual_running_job_ids: set[int] = set()


@app.on_event("startup")
def startup_event():
    Base.metadata.create_all(bind=engine)
    start_scheduler()
    
    
@app.post(
    "/login-page",
    include_in_schema=False,
)
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
      

@app.get(
    "/logout",
    include_in_schema=False,
)
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

            
@app.get(
    "/executions/{execution_id}/download",
    include_in_schema=False,
)
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

        
            
@app.post(
    "/upload-script",
    include_in_schema=False,
)
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
        db.flush()

        log_audit_event(
            db=db,
            user_id=current_user.id,
            username=current_user.username,
            action="UPLOAD_SCRIPT",
            entity_type="Job",
            entity_id=new_job.id,
            new_value=json.dumps(
                {
                    "job_name": new_job.name,
                    "description": new_job.description,
                    "script_type": new_job.script_type,
                    "original_filename": original_filename,
                    "stored_path": new_job.script_path,
                },
                default=str,
            ),
        )

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



@app.post(
    "/dashboard/jobs/create",
    include_in_schema=False,
)
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
        db.flush()

        log_audit_event(
            db=db,
            user_id=current_user.id,
            username=current_user.username,
            action="CREATE_JOB",
            entity_type="Job",
            entity_id=new_job.id,
            new_value=f"Created job '{new_job.name}' from dashboard",
        )

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

def _run_job_in_background(job_id: int):
    db = SessionLocal()

    try:
        job = (
            db.query(Job)
            .filter(Job.id == job_id)
            .first()
        )

        if not job:
            return

        execute_job_with_history(
            db=db,
            job=job,
        )

    finally:
        db.close()

        with _manual_run_lock:
            _manual_running_job_ids.discard(job_id)


@app.post(
    "/dashboard/jobs/{job_id}/run",
    include_in_schema=False,
)

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

        running_execution = (
            db.query(JobExecution)
            .filter(
                JobExecution.job_id == job.id,
                JobExecution.status == "Running",
            )
            .order_by(JobExecution.id.desc())
            .first()
        )

        if running_execution:
            return RedirectResponse(
            url="/dashboard?already_running=true",
            status_code=303,
        )

        with _manual_run_lock:
            if job.id in _manual_running_job_ids:
                return RedirectResponse(
                    url="/dashboard?already_running=true",
                    status_code=303,
                )

            _manual_running_job_ids.add(job.id)

        old_status = job.status

        try:
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

            Thread(
                target=_run_job_in_background,
                args=(job.id,),
                daemon=True,
            ).start()

        except Exception:
            db.rollback()

            with _manual_run_lock:
                _manual_running_job_ids.discard(job.id)

            raise

        return RedirectResponse(
            url="/dashboard",
            status_code=303,
        )

    finally:
        db.close()        

@app.post(
    "/dashboard/jobs/{job_id}/pause",
    include_in_schema=False,
)
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

        old_value = str(job.schedule_paused)

        pause_scheduled_job(job_id)

        db.expire(job)
        db.refresh(job)

        log_audit_event(
            db=db,
            user_id=current_user.id,
            username=current_user.username,
            action="PAUSE_SCHEDULE",
            entity_type="Job",
            entity_id=job.id,
            old_value=old_value,
            new_value=str(job.schedule_paused),
        )

        db.commit()

        return RedirectResponse(
            url="/dashboard?paused=true",
            status_code=303,
        )

    finally:
        db.close()

@app.post(
    "/dashboard/jobs/{job_id}/resume",
    include_in_schema=False,
)
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

        old_value = str(job.schedule_paused)

        resume_scheduled_job(job_id)

        db.expire(job)
        db.refresh(job)

        log_audit_event(
            db=db,
            user_id=current_user.id,
            username=current_user.username,
            action="RESUME_SCHEDULE",
            entity_type="Job",
            entity_id=job.id,
            old_value=old_value,
            new_value=str(job.schedule_paused),
        )

        db.commit()

        return RedirectResponse(
            url="/dashboard?resumed=true",
            status_code=303,
        )

    finally:
        db.close()



@app.post(
    "/executions/{execution_id}/stop",
    include_in_schema=False,
)
def stop_execution(
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

        if execution.status != "Running":
            raise HTTPException(
                status_code=409,
                detail="Only a running execution can be stopped.",
            )

        stop_requested = stop_active_execution(
            execution.id
        )

        if not stop_requested:
            raise HTTPException(
                status_code=409,
                detail=(
                    "The execution is marked as running, "
                    "but no active local process was found."
                ),
            )

        return RedirectResponse(
            url="/history",
            status_code=303,
        )

    finally:
        db.close()


@app.post(
    "/executions/{execution_id}/retry",
    include_in_schema=False,
)
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

        log_audit_event(
            db=db,
            user_id=current_user.id,
            username=current_user.username,
            action="RETRY_JOB",
            entity_type="Job",
            entity_id=job.id,
            old_value=f"Execution ID {execution.id}",
            new_value="Retry requested",
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

@app.post(
    "/dashboard/jobs/{job_id}/duplicate",
    include_in_schema=False,
)
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
        db.flush()

        log_audit_event(
            db=db,
            user_id=current_user.id,
            username=current_user.username,
            action="DUPLICATE_JOB",
            entity_type="Job",
            entity_id=duplicated_job.id,
            old_value=f"Copied from Job ID {original_job.id}",
            new_value=f"Created duplicate '{duplicated_job.name}'",
        )

        db.commit()
        db.refresh(duplicated_job)

        return RedirectResponse(
            url="/dashboard?duplicated=true",
            status_code=303,
        )

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()



@app.post(
    "/dashboard/jobs/{job_id}/delete",
    include_in_schema=False,
)
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
            deleted_job_value = json.dumps(
                {
                    "name": job.name,
                    "description": job.description,
                    "category": job.category,
                    "script_type": job.script_type,
                    "script_path": job.script_path,
                    "status": job.status,
                },
                default=str,
            )

            log_audit_event(
                db=db,
                user_id=current_user.id,
                username=current_user.username,
                action="DELETE_JOB",
                entity_type="Job",
                entity_id=job.id,
                old_value=deleted_job_value,
                new_value=None,
            )

            db.delete(job)
            db.commit()

        return RedirectResponse(
            url="/dashboard?deleted=true",
            status_code=303,
)

    finally:
        db.close()        
        


@app.get(
    "/",
    tags=["System"],
    summary="Platform status",
)
def root():
    return {
        "status": "success",
        "message": "Automation Platform API is running",
    }


@app.get(
    "/health",
    tags=["System"],
    summary="Platform health check",
)
def health_check():
    return {
        "status": "healthy",
    }


# Existing routes retained for browser compatibility.
app.include_router(
    jobs_router,
    prefix="/jobs",
    tags=["Legacy Jobs API"],
)

app.include_router(
    auth_router,
    tags=["Legacy Authentication API"],
)

app.include_router(
    users_router,
    prefix="/users",
    tags=["Legacy Users API"],
)

# Versioned REST API for v2.0 clients.
app.include_router(
    auth_v1_router,
    prefix="/api/v1/auth",
    tags=["API v1 - Authentication"],
)

app.include_router(
    agents_v1_router,
    prefix="/api/v1/agents",
    tags=["API v1 - Agents"],
)

app.include_router(
    agent_jobs_v1_router,
    prefix="/api/v1/agent-jobs",
    tags=["API v1 - Agent Jobs"],
)

app.include_router(
    jobs_v1_router,
    prefix="/api/v1/jobs",
    tags=["API v1 - Jobs"],
)

app.include_router(
    users_v1_router,
    prefix="/api/v1/users",
    tags=["API v1 - Users"],
)

# Browser pages must remain unversioned.
app.include_router(
    pages_router,
)

