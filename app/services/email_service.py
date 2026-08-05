import logging
import smtplib

from email.message import EmailMessage

from app.core.config import settings
from app.db.models import Job, JobExecution


logger = logging.getLogger(__name__)


def _get_recipients() -> list[str]:
    """
    Return a cleaned list of configured email recipients.
    """

    return [
        address.strip()
        for address in settings.EMAIL_TO_ADDRESSES.split(",")
        if address.strip()
    ]


def _should_send_notification(
    execution: JobExecution,
) -> bool:
    """
    Decide whether an email should be sent for
    the supplied execution status.
    """

    if not settings.EMAIL_NOTIFICATIONS_ENABLED:
        return False

    if execution.status == "Completed":
        return settings.EMAIL_NOTIFY_ON_COMPLETED

    if execution.status == "Failed":
        return settings.EMAIL_NOTIFY_ON_FAILED

    return False


def _validate_email_configuration() -> None:
    """
    Validate the required SMTP configuration.
    """

    if not settings.SMTP_HOST:
        raise ValueError(
            "SMTP_HOST is not configured."
        )

    if not settings.EMAIL_FROM_ADDRESS:
        raise ValueError(
            "EMAIL_FROM_ADDRESS is not configured."
        )

    if not _get_recipients():
        raise ValueError(
            "EMAIL_TO_ADDRESSES is not configured."
        )

    if (
        settings.SMTP_USE_SSL
        and settings.SMTP_USE_TLS
    ):
        raise ValueError(
            "SMTP_USE_SSL and SMTP_USE_TLS "
            "cannot both be enabled."
        )


def _build_job_notification(
    job: Job,
    execution: JobExecution,
) -> EmailMessage:
    """
    Build the execution notification email.
    """

    message = EmailMessage()

    message["From"] = settings.EMAIL_FROM_ADDRESS
    message["To"] = ", ".join(_get_recipients())

    message["Subject"] = (
        f"[{execution.status}] "
        f"Automation Job: {job.name}"
    )

    result_text = execution.result or "-"
    error_text = execution.error_message or "-"

    body = f"""
Automation job execution notification

Job ID: {job.id}
Job Name: {job.name}
Execution ID: {execution.id}
Status: {execution.status}

Started At: {execution.started_at or "-"}
Completed At: {execution.completed_at or "-"}
Duration: {
    f"{execution.duration:.4f} seconds"
    if execution.duration is not None
    else "-"
}

Result:
{result_text}

Error:
{error_text}
""".strip()

    message.set_content(body)

    return message


def _send_message(
    message: EmailMessage,
) -> None:
    """
    Send one email through the configured SMTP server.
    """

    if settings.SMTP_USE_SSL:
        smtp_client = smtplib.SMTP_SSL(
            host=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            timeout=30,
        )
    else:
        smtp_client = smtplib.SMTP(
            host=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            timeout=30,
        )

    try:
        smtp_client.ehlo()

        if (
            settings.SMTP_USE_TLS
            and not settings.SMTP_USE_SSL
        ):
            smtp_client.starttls()
            smtp_client.ehlo()

        if settings.SMTP_USERNAME:
            smtp_client.login(
                settings.SMTP_USERNAME,
                settings.SMTP_PASSWORD,
            )

        smtp_client.send_message(message)

    finally:
        smtp_client.quit()


def send_job_execution_notification(
    job: Job,
    execution: JobExecution,
) -> bool:
    """
    Send a job execution notification.

    Email failures are logged and never raised to
    the job execution flow.
    """

    if not _should_send_notification(execution):
        return False

    try:
        _validate_email_configuration()

        message = _build_job_notification(
            job=job,
            execution=execution,
        )

        _send_message(message)

        logger.info(
            "Execution notification email sent. "
            "Job ID: %s, Execution ID: %s",
            job.id,
            execution.id,
        )

        return True

    except Exception:
        logger.exception(
            "Execution notification email failed. "
            "Job ID: %s, Execution ID: %s",
            job.id,
            execution.id,
        )

        return False