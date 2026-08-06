import logging
import sys
import time

from agents.windows_agent.config import (
    WindowsAgentSettings,
    load_agent_settings,
)
from agents.windows_agent.platform_client import (
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