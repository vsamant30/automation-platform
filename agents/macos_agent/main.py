import logging
import os
import signal
import threading
import sys
import time

from agents.macos_agent.config import (
    MacOSAgentSettings,
    load_agent_settings,
)

from agents.macos_agent.executor import (
    execute_script,
)

from agents.macos_agent.platform_client import (
    append_job_log,
    claim_next_job,
    complete_job,
    download_job_script,
    fail_job,
    mark_job_running,
    send_heartbeat,
)


logger = logging.getLogger(
    "automation_platform_macos_agent"
)


def configure_logging() -> None:
    """
    Configure console logging for the macOS Agent.
    """

    logging.basicConfig(
        level=logging.INFO,
        format=(
            "%(asctime)s [%(levelname)s] "
            "%(name)s: %(message)s"
        ),
    )


def run_heartbeat_once(
    settings: MacOSAgentSettings,
) -> bool:
    """
    Send one heartbeat and report whether it succeeded.
    """

    try:
        response = send_heartbeat(settings)

        logger.info(
            "Heartbeat sent successfully. "
            "Agent ID: %s, Hostname: %s, Response: %s",
            settings.agent_id,
            settings.hostname,
            response,
        )

        return True

    except Exception:
        logger.exception(
            "Heartbeat failed. "
            "Agent ID: %s, Hostname: %s",
            settings.agent_id,
            settings.hostname,
        )

        return False


def append_job_log_safely(
    settings: MacOSAgentSettings,
    *,
    agent_job_id: int,
    stream: str,
    message: str,
) -> None:
    """
    Send a remote job log without interrupting
    the job if log delivery fails.
    """

    cleaned_message = message.rstrip()

    if not cleaned_message:
        return

    try:
        append_job_log(
            settings=settings,
            agent_job_id=agent_job_id,
            stream=stream,
            message=cleaned_message,
        )

    except Exception:
        logger.exception(
            "Unable to send live job log. "
            "Agent Job ID: %s, Stream: %s",
            agent_job_id,
            stream,
        )


def process_next_job_once(
    settings: MacOSAgentSettings,
) -> bool:
    """
    Claim, download, execute, and report one
    queued remote job.

    Return False when no queued job is available
    or when processing fails.
    """

    agent_job_id = None
    downloaded_script_path = None

    try:
        agent_job = claim_next_job(settings)

        if agent_job is None:
            logger.info(
                "No queued remote job is available. "
                "Agent ID: %s",
                settings.agent_id,
            )

            return False

        agent_job_id = agent_job["id"]

        logger.info(
            "Remote job claimed. "
            "Agent Job ID: %s, Job ID: %s, Job Name: %s",
            agent_job_id,
            agent_job["job_id"],
            agent_job["job_name"],
        )

        append_job_log_safely(
            settings=settings,
            agent_job_id=agent_job_id,
            stream="system",
            message=(
                "Remote job claimed by agent. "
                f"Job ID: {agent_job['job_id']}, "
                f"Job Name: {agent_job['job_name']}"
            ),
        )

        running_job = mark_job_running(
            settings=settings,
            agent_job_id=agent_job_id,
        )

        logger.info(
            "Remote job marked as running. "
            "Agent Job ID: %s, Status: %s",
            running_job["id"],
            running_job["status"],
        )

        append_job_log_safely(
            settings=settings,
            agent_job_id=agent_job_id,
            stream="system",
            message="Remote job marked as Running.",
        )

        download_directory = os.path.join(
            "agents",
            "macos_agent",
            "downloads",
            f"agent_job_{agent_job_id}",
        )

        downloaded_script_path = download_job_script(
            settings=settings,
            job_id=agent_job["job_id"],
            destination_directory=download_directory,
        )

        logger.info(
            "Remote job script downloaded. "
            "Agent Job ID: %s, Local Path: %s",
            agent_job_id,
            downloaded_script_path,
        )

        append_job_log_safely(
            settings=settings,
            agent_job_id=agent_job_id,
            stream="system",
            message=(
                "Remote job script downloaded successfully. "
                f"Local file: "
                f"{os.path.basename(downloaded_script_path)}"
            ),
        )

        append_job_log_safely(
            settings=settings,
            agent_job_id=agent_job_id,
            stream="system",
            message=(
                "Starting script execution. "
                f"Script type: {agent_job['script_type']}"
            ),
        )

        def stream_output(
            stream: str,
            message: str,
        ) -> None:
            append_job_log_safely(
                settings=settings,
                agent_job_id=agent_job_id,
                stream=stream,
                message=message,
            )


        execution_result = execute_script(
            script_type=agent_job["script_type"],
            script_path=downloaded_script_path,
            on_output=stream_output,
        )


        if execution_result.success:
            append_job_log_safely(
                settings=settings,
                agent_job_id=agent_job_id,
                stream="system",
                message=(
                    "Script execution completed successfully. "
                    f"Return code: "
                    f"{execution_result.return_code}"
                ),
            )

            completed_job = complete_job(
                settings=settings,
                agent_job_id=agent_job_id,
                result=execution_result.output,
            )

            logger.info(
                "Remote job completed successfully. "
                "Agent Job ID: %s, Status: %s, Return Code: %s",
                completed_job["id"],
                completed_job["status"],
                execution_result.return_code,
            )

            return True

        failure_message = (
            execution_result.error
            or (
                "Script execution failed with "
                f"return code {execution_result.return_code}."
            )
        )

        append_job_log_safely(
            settings=settings,
            agent_job_id=agent_job_id,
            stream="system",
            message=(
                "Script execution failed. "
                f"Return code: {execution_result.return_code}"
            ),
        )

        failed_job = fail_job(
            settings=settings,
            agent_job_id=agent_job_id,
            error_message=failure_message,
            result=execution_result.output,
        )

        logger.error(
            "Remote job failed. "
            "Agent Job ID: %s, Status: %s, Return Code: %s",
            failed_job["id"],
            failed_job["status"],
            execution_result.return_code,
        )

        return False

    except Exception as error:
        if agent_job_id is not None:
            append_job_log_safely(
                settings=settings,
                agent_job_id=agent_job_id,
                stream="stderr",
                message=(
                    "Remote job processing failed: "
                    f"{error}"
                ),
            )

            try:
                fail_job(
                    settings=settings,
                    agent_job_id=agent_job_id,
                    error_message=str(error),
                )

            except Exception:
                logger.exception(
                    "Unable to report remote job failure. "
                    "Agent Job ID: %s",
                    agent_job_id,
                )

        logger.exception(
            "Remote job processing failed. "
            "Agent ID: %s",
            settings.agent_id,
        )

        return False

    finally:
        if (
            downloaded_script_path
            and os.path.isfile(downloaded_script_path)
        ):
            try:
                os.remove(downloaded_script_path)

                logger.info(
                    "Downloaded script removed. "
                    "Path: %s",
                    downloaded_script_path,
                )

                if agent_job_id is not None:
                    append_job_log_safely(
                        settings=settings,
                        agent_job_id=agent_job_id,
                        stream="system",
                        message=(
                            "Downloaded temporary script "
                            "was removed."
                        ),
                    )

            except OSError:
                logger.exception(
                    "Unable to remove downloaded script. "
                    "Path: %s",
                    downloaded_script_path,
                )


def run_agent(
    settings: MacOSAgentSettings,
    stop_event=None,
) -> None:
    """
    Run the macOS Agent heartbeat and job-processing loop.

    When stop_event is provided, stop gracefully when
    the event is set. CLI execution can continue without
    providing a stop event.
    """

    logger.info(
        "macOS Agent started. "
        "Agent name: %s, Hostname: %s, "
        "Platform URL: %s, Heartbeat interval: %s seconds",
        settings.agent_name,
        settings.hostname,
        settings.platform_url,
        settings.heartbeat_interval_seconds,
    )

    while (
        stop_event is None
        or not stop_event.is_set()
    ):
        run_heartbeat_once(settings)

        process_next_job_once(settings)

        if stop_event is None:
            time.sleep(
                settings.heartbeat_interval_seconds
            )

        else:
            if stop_event.wait(
                settings.heartbeat_interval_seconds
            ):
                break

    logger.info(
        "macOS Agent loop stopped gracefully."
    )


def main() -> int:
    """
    macOS Agent application entry point.
    """

    configure_logging()

    stop_event = threading.Event()

    def request_shutdown(
        signum,
        frame,
    ) -> None:
        logger.info(
            "macOS Agent shutdown requested. "
            "Signal: %s",
            signum,
        )

        stop_event.set()

    signal.signal(
        signal.SIGTERM,
        request_shutdown,
    )

    signal.signal(
        signal.SIGINT,
        request_shutdown,
    )

    try:
        settings = load_agent_settings()

        if settings.agent_id is None:
            raise ValueError(
                "AUTOMATION_AGENT_ID is not configured."
            )

        if not settings.api_key:
            raise ValueError(
                "AUTOMATION_AGENT_API_KEY is not configured."
            )

        run_agent(
            settings=settings,
            stop_event=stop_event,
        )

    except KeyboardInterrupt:
        logger.info(
            "macOS Agent stopped by the user."
        )

        return 0

    except Exception:
        logger.exception(
            "macOS Agent could not start."
        )

        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())