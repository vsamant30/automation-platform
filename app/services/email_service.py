import logging
import smtplib

from email.message import EmailMessage

from app.db.database import SessionLocal

from app.db.models import (
    ApplicationSettings,
    Job,
    JobExecution,
)

logger = logging.getLogger(__name__)



def _get_application_settings() -> ApplicationSettings:
    """
    Return the single application settings record.
    """

    db = SessionLocal()

    try:
        settings_row = (
            db.query(ApplicationSettings)
            .first()
        )

        if settings_row is None:
            raise ValueError(
                "Application settings not found."
            )

        db.expunge(settings_row)

        return settings_row

    finally:
        db.close()



def _get_recipients(
    application_settings: ApplicationSettings,
) -> list[str]:
    """
    Return a cleaned list of configured email recipients.
    """

    return [
        address.strip()
        for address in (
            application_settings.email_to_addresses
            or ""
        ).split(",")
        if address.strip()
    ]


def _should_send_notification(
    execution: JobExecution,
) -> bool:
    """
    Decide whether an email should be sent for
    the supplied execution status.
    """

    application_settings = (
        _get_application_settings()
    )

    if (
        not application_settings
        .email_notifications_enabled
    ):
        return False

    if execution.status == "Completed":
        return (
            application_settings
            .notify_on_completed
        )

    if execution.status == "Failed":
        return (
            application_settings
            .notify_on_failed
        )

    return False



def _validate_email_configuration(
    application_settings: ApplicationSettings,
) -> None:
    """
    Validate the required SMTP configuration.
    """

    if not application_settings.smtp_host:
        raise ValueError(
            "SMTP host is not configured."
        )

    if not application_settings.email_from_address:
        raise ValueError(
            "Sender email address is not configured."
        )

    if not _get_recipients(application_settings):
        raise ValueError(
            "Recipient email addresses are not configured."
    )

    if (
        application_settings.smtp_use_ssl
        and application_settings.smtp_use_tls
    ):
        raise ValueError(
            "SMTP SSL and TLS cannot both be enabled."
        )


def _build_job_notification(
    job: Job,
    execution: JobExecution,
    application_settings: ApplicationSettings,
) -> EmailMessage:
    """
    Build the execution notification email.
    """

    message = EmailMessage()

    message["From"] = (
        application_settings.email_from_address
    )

    message["To"] = ", ".join(
        _get_recipients(application_settings)
    )

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
    application_settings: ApplicationSettings,
) -> None:
    """
    Send one email through the configured SMTP server.
    """

    if application_settings.smtp_use_ssl:
        smtp_client = smtplib.SMTP_SSL(
            host=application_settings.smtp_host,
            port=application_settings.smtp_port,
            timeout=30,
        )
    else:
        smtp_client = smtplib.SMTP(
            host=application_settings.smtp_host,
            port=application_settings.smtp_port,
            timeout=30,
        )

    try:
        smtp_client.ehlo()

        if (
            application_settings.smtp_use_tls
            and not application_settings.smtp_use_ssl
        ):
            smtp_client.starttls()
            smtp_client.ehlo()

        if application_settings.smtp_username:
            smtp_client.login(
                application_settings.smtp_username,
                application_settings.smtp_password or "",
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
        application_settings = (
            _get_application_settings()
        )

        _validate_email_configuration(
            application_settings
        )

        message = _build_job_notification(
            job=job,
            execution=execution,
            application_settings=application_settings,
        )

        _send_message(
            message=message,
            application_settings=application_settings,
        )

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

def send_test_email() -> bool:
    """
    Send a test email using the current
    application settings.
    """

    try:
        application_settings = (
            _get_application_settings()
        )

        _validate_email_configuration(
            application_settings
        )

        message = EmailMessage()

        message["From"] = (
            application_settings.email_from_address
        )

        message["To"] = ", ".join(
            _get_recipients(
                application_settings
            )
        )

        message["Subject"] = (
            "Automation Platform - SMTP Test Successful"
        )

        message.set_content(
    f"""
Hello,

This is a test email from Automation Platform.

Your SMTP configuration has been verified successfully.

Configuration Details
---------------------
SMTP Host : {application_settings.smtp_host}
SMTP Port : {application_settings.smtp_port}
TLS       : {"Enabled" if application_settings.smtp_use_tls else "Disabled"}
SSL       : {"Enabled" if application_settings.smtp_use_ssl else "Disabled"}

If you received this email, your Automation Platform is ready to send execution notifications.

Regards,
Automation Platform
""".strip()
)

        _send_message(
            message=message,
            application_settings=application_settings,
        )

        logger.info(
            "Test email sent successfully."
        )

        return True

    except Exception:
        logger.exception(
            "Failed to send test email."
        )

        return False