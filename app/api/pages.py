from app.services.job_name_validator import validate_job_name

from app.services.agent_service import get_agents

from app.services.agent_job_service import (
    get_agent_job,
    get_agent_jobs,
    queue_job_for_agent,
)

from app.services.agent_job_log_service import (
    get_agent_job_logs,
)

import csv
import io
import json
from datetime import datetime, timedelta


from app.services.audit_service import log_audit_event

from fastapi import (
    APIRouter,
    Form,
    HTTPException,
    Query,
    Request,
)
from fastapi.responses import (
    FileResponse,
    HTMLResponse,
    RedirectResponse,
    StreamingResponse,
)
from fastapi.templating import Jinja2Templates

from app.core.auth import (
    get_current_user_from_cookie,
    require_admin,
)
from app.db.database import SessionLocal

from app.db.models import (
    ApplicationSettings,

    AuditLog,
    Job,
    JobExecution,
)

from app.scheduler.scheduler import sync_job_schedule

from app.services.email_service import (
    send_test_email,
)

from app.services.job_execution_service import (
    execute_job_with_history,
)
from app.services.execution_logger import (
    get_execution_log_path,
)




router = APIRouter(
    include_in_schema=False,
)

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


def _get_dashboard_statistics(db):
    """
    Return the current dashboard job counts and
    operational execution metrics.
    """

    twenty_four_hours_ago = (
        datetime.utcnow() - timedelta(hours=24)
    )

    recent_executions = (
        db.query(JobExecution)
        .filter(
            JobExecution.created_at
            >= twenty_four_hours_ago
        )
        .all()
    )

    completed_executions_24h = sum(
        1
        for execution in recent_executions
        if execution.status == "Completed"
    )

    failed_executions_24h = sum(
        1
        for execution in recent_executions
        if execution.status == "Failed"
    )

    finished_executions_24h = (
        completed_executions_24h
        + failed_executions_24h
    )

    if finished_executions_24h > 0:
        success_rate_24h = round(
            (
                completed_executions_24h
                / finished_executions_24h
            )
            * 100,
            1,
        )
    else:
        success_rate_24h = 0.0

    recorded_durations = [
        execution.duration
        for execution in recent_executions
        if execution.duration is not None
    ]

    if recorded_durations:
        average_duration_24h = round(
            sum(recorded_durations)
            / len(recorded_durations),
            4,
        )
    else:
        average_duration_24h = 0.0

    return {
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

        "executions_24h": len(recent_executions),

        "success_rate_24h": success_rate_24h,

        "average_duration_24h": (
            average_duration_24h
        ),

        "pending_jobs": (
            db.query(Job)
            .filter(Job.status == "Pending")
            .count()
        ),

        "paused_schedules": (
            db.query(Job)
            .filter(
                Job.schedule_enabled == True,
                Job.schedule_paused == True,
            )
            .count()
        ),
    }

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

        statistics = _get_dashboard_statistics(db)

        return templates.TemplateResponse(
            request=request,
            name="dashboard.html",
            context={
                "request": request,
                "current_user": current_user,
                "jobs": jobs,
                **statistics,
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

        statistics = _get_dashboard_statistics(db)

        return {
            "statistics": statistics,
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


@router.get("/api/workflow-data")
def workflow_data(request: Request):
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

        jobs = (
            db.query(Job)
            .order_by(Job.id)
            .all()
        )

        return {
            "workflow": [
                {
                    "job_id": job.id,
                    "job_name": job.name,
                    "depends_on": job.dependency_job_id,
                    "condition_type": job.condition_type,
                    "condition_value": job.condition_value,
                    "enabled": job.is_enabled,
                    "status": job.status,
                }
                for job in jobs
            ]
        }

    finally:
        db.close()


@router.get("/history/export.csv")
def export_execution_history(
    request: Request,
    search: str = Query(""),
    status: str = Query(""),
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

        query = db.query(JobExecution)

        cleaned_search = search.strip()
        cleaned_status = status.strip()

        if cleaned_search:
            query = query.filter(
                JobExecution.job_name.ilike(
                    f"%{cleaned_search}%"
                )
            )

        if cleaned_status:
            query = query.filter(
                JobExecution.status.ilike(
                    cleaned_status
                )
            )

        executions = (
            query
            .order_by(JobExecution.id.desc())
            .all()
        )

        def safe_csv_value(value):
            if value is None:
                return ""

            text = str(value)

            if text.startswith(("=", "+", "-", "@")):
                return f"'{text}"

            return text

        output = io.StringIO(newline="")

        writer = csv.writer(output)

        writer.writerow(
            [
                "Execution ID",
                "Job ID",
                "Job Name",
                "Status",
                "Started At",
                "Completed At",
                "Duration Seconds",
                "Result",
                "Error Message",
                "Created At",
            ]
        )

        for execution in executions:
            writer.writerow(
                [
                    safe_csv_value(execution.id),
                    safe_csv_value(execution.job_id),
                    safe_csv_value(execution.job_name),
                    safe_csv_value(execution.status),
                    safe_csv_value(execution.started_at),
                    safe_csv_value(execution.completed_at),
                    safe_csv_value(
                        execution.duration
                        if execution.duration is not None
                        else ""
                    ),
                    safe_csv_value(execution.result),
                    safe_csv_value(execution.error_message),
                    safe_csv_value(execution.created_at),
                ]
            )

        csv_content = output.getvalue()
        output.close()

        response = StreamingResponse(
            iter([csv_content]),
            media_type="text/csv; charset=utf-8",
        )

        response.headers["Content-Disposition"] = (
            'attachment; filename="execution_history.csv"'
        )

        return response

    finally:
        db.close()

@router.get("/settings")
def application_settings_page(request: Request):
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

        application_settings = (
            db.query(ApplicationSettings)
            .order_by(ApplicationSettings.id)
            .first()
        )

        if application_settings is None:
            application_settings = ApplicationSettings(
                email_notifications_enabled=False,
                smtp_port=587,
                smtp_use_tls=True,
                smtp_use_ssl=False,
                notify_on_completed=True,
                notify_on_failed=True,
            )

            db.add(application_settings)
            db.commit()
            db.refresh(application_settings)

        return templates.TemplateResponse(
            request=request,
            name="settings.html",
            context={
                "request": request,
                "current_user": current_user,
                "application_settings": (
                    application_settings
                ),
            },
        )

    finally:
        db.close()

@router.post("/settings")
def save_application_settings(
    request: Request,
    email_notifications_enabled: str | None = Form(None),
    smtp_host: str = Form(""),
    smtp_port: str = Form("587"),
    smtp_username: str = Form(""),
    smtp_password: str = Form(""),
    smtp_use_tls: str | None = Form(None),
    smtp_use_ssl: str | None = Form(None),
    email_from_address: str = Form(""),
    email_to_addresses: str = Form(""),
    notify_on_completed: str | None = Form(None),
    notify_on_failed: str | None = Form(None),
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

        application_settings = (
            db.query(ApplicationSettings)
            .order_by(ApplicationSettings.id)
            .first()
        )

        if application_settings is None:
            application_settings = ApplicationSettings()

            db.add(application_settings)
            db.flush()

        try:
            cleaned_smtp_port = int(
                smtp_port.strip()
            )
        except ValueError:
            return RedirectResponse(
                url="/settings?error=invalid_port",
                status_code=303,
            )

        if not 1 <= cleaned_smtp_port <= 65535:
            return RedirectResponse(
                url="/settings?error=invalid_port",
                status_code=303,
            )

        use_tls = smtp_use_tls is not None
        use_ssl = smtp_use_ssl is not None

        if use_tls and use_ssl:
            return RedirectResponse(
                url="/settings?error=tls_ssl_conflict",
                status_code=303,
            )

        old_value = json.dumps(
            {
                "email_notifications_enabled": (
                    application_settings
                    .email_notifications_enabled
                ),
                "smtp_host": (
                    application_settings.smtp_host
                ),
                "smtp_port": (
                    application_settings.smtp_port
                ),
                "smtp_username": (
                    application_settings.smtp_username
                ),
                "smtp_use_tls": (
                    application_settings.smtp_use_tls
                ),
                "smtp_use_ssl": (
                    application_settings.smtp_use_ssl
                ),
                "email_from_address": (
                    application_settings
                    .email_from_address
                ),
                "email_to_addresses": (
                    application_settings
                    .email_to_addresses
                ),
                "notify_on_completed": (
                    application_settings
                    .notify_on_completed
                ),
                "notify_on_failed": (
                    application_settings
                    .notify_on_failed
                ),
            },
            default=str,
        )

        application_settings.email_notifications_enabled = (
            email_notifications_enabled is not None
        )

        application_settings.smtp_host = (
            smtp_host.strip() or None
        )

        application_settings.smtp_port = (
            cleaned_smtp_port
        )

        application_settings.smtp_username = (
            smtp_username.strip() or None
        )

        if smtp_password:
            application_settings.smtp_password = (
                smtp_password
            )

        application_settings.smtp_use_tls = use_tls
        application_settings.smtp_use_ssl = use_ssl

        application_settings.email_from_address = (
            email_from_address.strip() or None
        )

        application_settings.email_to_addresses = (
            email_to_addresses.strip() or None
        )

        application_settings.notify_on_completed = (
            notify_on_completed is not None
        )

        application_settings.notify_on_failed = (
            notify_on_failed is not None
        )

        new_value = json.dumps(
            {
                "email_notifications_enabled": (
                    application_settings
                    .email_notifications_enabled
                ),
                "smtp_host": (
                    application_settings.smtp_host
                ),
                "smtp_port": (
                    application_settings.smtp_port
                ),
                "smtp_username": (
                    application_settings.smtp_username
                ),
                "smtp_use_tls": (
                    application_settings.smtp_use_tls
                ),
                "smtp_use_ssl": (
                    application_settings.smtp_use_ssl
                ),
                "email_from_address": (
                    application_settings
                    .email_from_address
                ),
                "email_to_addresses": (
                    application_settings
                    .email_to_addresses
                ),
                "notify_on_completed": (
                    application_settings
                    .notify_on_completed
                ),
                "notify_on_failed": (
                    application_settings
                    .notify_on_failed
                ),
            },
            default=str,
        )

        log_audit_event(
            db=db,
            user_id=current_user.id,
            username=current_user.username,
            action="UPDATE_APPLICATION_SETTINGS",
            entity_type="ApplicationSettings",
            entity_id=application_settings.id,
            old_value=old_value,
            new_value=new_value,
        )

        db.commit()

        return RedirectResponse(
            url="/settings?saved=true",
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


@router.post("/settings/test-email")
def test_application_email(request: Request):
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

        email_sent = send_test_email()

        log_audit_event(
            db=db,
            user_id=current_user.id,
            username=current_user.username,
            action="TEST_EMAIL",
            entity_type="ApplicationSettings",
            entity_id=None,
            old_value=None,
            new_value=(
                "Test email sent successfully."
                if email_sent
                else "Test email failed."
            ),
        )

        db.commit()

        if email_sent:
            return RedirectResponse(
                url="/settings?test_email=success",
                status_code=303,
            )

        return RedirectResponse(
            url="/settings?test_email=failed",
            status_code=303,
        )

    except HTTPException:
        db.rollback()
        raise

    except Exception:
        db.rollback()

        return RedirectResponse(
            url="/settings?test_email=failed",
            status_code=303,
        )

    finally:
        db.close()


@router.get("/audit-logs")
def audit_logs_page(request: Request):
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

        audit_logs = (
            db.query(AuditLog)
            .order_by(AuditLog.id.desc())
            .limit(200)
            .all()
        )

        return templates.TemplateResponse(
            request=request,
            name="audit_logs.html",
            context={
                "request": request,
                "current_user": current_user,
                "audit_logs": audit_logs,
            },
        )

    finally:
        db.close()

@router.get("/audit-logs/export.csv")
def export_audit_logs(request: Request):
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

        audit_logs = (
            db.query(AuditLog)
            .order_by(AuditLog.id.desc())
            .all()
        )

        def safe_csv_value(value):
            if value is None:
                return ""

            text = str(value)

            if text.startswith(("=", "+", "-", "@")):
                return f"'{text}"

            return text

        output = io.StringIO(newline="")

        writer = csv.writer(output)

        writer.writerow(
            [
                "Audit ID",
                "Created At",
                "User ID",
                "Username",
                "Action",
                "Entity Type",
                "Entity ID",
                "Old Value",
                "New Value",
                "IP Address",
            ]
        )

        for audit in audit_logs:
            writer.writerow(
                [
                    safe_csv_value(audit.id),
                    safe_csv_value(audit.created_at),
                    safe_csv_value(audit.user_id),
                    safe_csv_value(audit.username),
                    safe_csv_value(audit.action),
                    safe_csv_value(audit.entity_type),
                    safe_csv_value(audit.entity_id),
                    safe_csv_value(audit.old_value),
                    safe_csv_value(audit.new_value),
                    safe_csv_value(audit.ip_address),
                ]
            )

        csv_content = output.getvalue()
        output.close()

        response = StreamingResponse(
            iter([csv_content]),
            media_type="text/csv; charset=utf-8",
        )

        response.headers["Content-Disposition"] = (
            'attachment; filename="audit_logs.csv"'
        )

        return response

    finally:
        db.close()


@router.get("/executions/{execution_id}/log/download")
def download_execution_log(
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
            raise HTTPException(
                status_code=404,
                detail="Execution not found.",
            )

        log_path = get_execution_log_path(
            execution.id
        )

        if not log_path.is_file():
            raise HTTPException(
                status_code=404,
                detail="Execution log file was not found.",
            )

        return FileResponse(
            path=log_path,
            media_type="text/plain",
            filename=log_path.name,
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


        old_value = json.dumps(
            {
               "name": job.name,
               "description": job.description,
               "script_type": job.script_type,
               "category": job.category,
               "script_path": job.script_path,
            },
            default=str,
        )

        job.name = cleaned_name
        job.description = description.strip()
        job.script_type = script_type.strip().lower()
        job.category = category.strip()
        job.script_path = script_path.strip()

        new_value = json.dumps(
            {
               "name": job.name,
               "description": job.description,
               "script_type": job.script_type,
               "category": job.category,
               "script_path": job.script_path,
            },
            default=str,
        )

        log_audit_event(
            db=db,
            user_id=current_user.id,
            username=current_user.username,
            action="EDIT_JOB",
            entity_type="Job",
            entity_id=job.id,
            old_value=old_value,
            new_value=new_value,
        )

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

        old_value = json.dumps(
            {
                "schedule_enabled": job.schedule_enabled,
                "schedule_type": job.schedule_type,
                "schedule_value": job.schedule_value,
                "next_run": job.next_run,
            },
            default=str,
        )

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

        new_value = json.dumps(
            {
                "schedule_enabled": job.schedule_enabled,
                "schedule_type": job.schedule_type,
                "schedule_value": job.schedule_value,
                "next_run": job.next_run,
            },
            default=str,
        )

        log_audit_event(
            db=db,
            user_id=current_user.id,
            username=current_user.username,
            action="SCHEDULE_JOB",
            entity_type="Job",
            entity_id=job.id,
            old_value=old_value,
            new_value=new_value,
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

@router.post("/jobs/{job_id}/retry")
def retry_job(
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
            raise HTTPException(
                status_code=404,
                detail="Job not found",
            )

        if job.status != "Failed":
            raise HTTPException(
                status_code=400,
                detail="Only failed jobs can be retried.",
            )

        previous_status = job.status

        execution = execute_job_with_history(
            db=db,
            job=job,
        )

        log_audit_event(
            db=db,
            user_id=current_user.id,
            username=current_user.username,
            action="RETRY_JOB",
            entity_type="Job",
            entity_id=job.id,
            old_value=previous_status,
            new_value=execution.status,
        )

        db.commit()

        return RedirectResponse(
            url=f"/jobs/{job.id}/details",
            status_code=303,
        )

    finally:
        db.close()


@router.get("/agents")
def agents_page(
    request: Request,
    agent_job_id: int | None = Query(None),
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

        agents = get_agents()
        agent_jobs = get_agent_jobs()

        jobs = (
            db.query(Job)
            .filter(Job.is_enabled == True)
            .order_by(Job.name.asc())
            .all()
        )

        selected_agent_job = None

        if agent_job_id is not None:
            selected_agent_job = get_agent_job(
                agent_job_id
            )

        elif agent_jobs:
            selected_agent_job = agent_jobs[0]

        agent_job_logs = (
            get_agent_job_logs(selected_agent_job.id)
            if selected_agent_job is not None
            else []
        )

        return templates.TemplateResponse(
            request=request,
            name="agents.html",
            context={
                "request": request,
                "current_user": current_user,
                "agents": agents,
                "jobs": jobs,
                "agent_jobs": agent_jobs,
                "selected_agent_job": selected_agent_job,
                "agent_job_logs": agent_job_logs,
            },
        )

    finally:
        db.close()


@router.post("/agents/queue")
def queue_agent_job_page(
    request: Request,
    agent_id: int = Form(...),
    job_id: int = Form(...),
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
            agent_job = queue_job_for_agent(
                agent_id=agent_id,
                job_id=job_id,
            )

        except ValueError:
            return RedirectResponse(
                url="/agents",
                status_code=303,
            )

        return RedirectResponse(
            url=(
                "/agents?agent_job_id="
                f"{agent_job.id}"
            ),
            status_code=303,
        )

    finally:
        db.close()