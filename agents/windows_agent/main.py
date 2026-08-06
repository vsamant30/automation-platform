import logging
import sys
import time

from agents.windows_agent.config import (
    WindowsAgentSettings,
    load_agent_settings,
)

from agents.windows_agent.executor import (
    execute_script,
)

from agents.windows_agent.platform_client import (
    claim_next_job,
    complete_job,
    fail_job,
    mark_job_running,
    send_heartbeat,
)


logger = logging.getLogger(
    "automation_platform_windows_agent"
)


def configure_logging() -> None:
    """
    Configure console logging for the Windows Agent.
    """

    logging.basicConfig(
        level=logging.INFO,
        format=(
            "%(asctime)s [%(levelname)s] "
            "%(name)s: %(message)s"
        ),
    )


def run_heartbeat_once(
    settings: WindowsAgentSettings,
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


def process_next_job_once(
    settings: WindowsAgentSettings,
) -> bool:
    """
    Claim and execute one queued remote job.

    Return False when no queued job is available
    or when processing fails.
    """

    agent_job_id = None

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

        execution_result = execute_script(
            script_type=agent_job["script_type"],
            script_path=agent_job["script_path"],
        )

        if execution_result.success:
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

        failed_job = fail_job(
            settings=settings,
            agent_job_id=agent_job_id,
            error_message=(
                execution_result.error
                or (
                    "Script execution failed with "
                    f"return code {execution_result.return_code}."
                )
            ),
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


def run_agent(
    settings: WindowsAgentSettings,
) -> None:
    """
    Run the Windows Agent heartbeat loop.
    """

    logger.info(
        "Windows Agent started. "
        "Agent name: %s, Hostname: %s, "
        "Platform URL: %s, Heartbeat interval: %s seconds",
        settings.agent_name,
        settings.hostname,
        settings.platform_url,
        settings.heartbeat_interval_seconds,
    )

    while True:
        run_heartbeat_once(settings)

        process_next_job_once(settings)

        time.sleep(
            settings.heartbeat_interval_seconds
        )


def main() -> int:
    """
    Windows Agent application entry point.
    """

    configure_logging()

    try:
        settings = load_agent_settings()

        if settings.agent_id is None:
            raise ValueError(
                "AUTOMATION_AGENT_ID is not configured."
            )

        if not settings.authentication_token:
            raise ValueError(
                "AUTOMATION_AGENT_TOKEN is not configured."
            )

        run_agent(settings)

    except KeyboardInterrupt:
        logger.info(
            "Windows Agent stopped by the user."
        )

        return 0

    except Exception:
        logger.exception(
            "Windows Agent could not start."
        )

        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())