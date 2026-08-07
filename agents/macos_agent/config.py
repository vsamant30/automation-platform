import os
import socket

from dataclasses import dataclass


DEFAULT_PLATFORM_URL = "http://127.0.0.1:8000"
DEFAULT_HEARTBEAT_INTERVAL_SECONDS = 60
DEFAULT_REQUEST_TIMEOUT_SECONDS = 30


def _get_optional_integer(
    environment_variable: str,
) -> int | None:
    raw_value = os.getenv(
        environment_variable,
        "",
    ).strip()

    if not raw_value:
        return None

    try:
        value = int(raw_value)

    except ValueError as error:
        raise ValueError(
            f"{environment_variable} must be an integer."
        ) from error

    if value <= 0:
        raise ValueError(
            f"{environment_variable} must be greater than zero."
        )

    return value


def _get_positive_integer(
    environment_variable: str,
    default_value: int,
) -> int:
    raw_value = os.getenv(
        environment_variable,
        str(default_value),
    ).strip()

    try:
        value = int(raw_value)

    except ValueError as error:
        raise ValueError(
            f"{environment_variable} must be an integer."
        ) from error

    if value <= 0:
        raise ValueError(
            f"{environment_variable} must be greater than zero."
        )

    return value


def _clean_platform_url(
    platform_url: str,
) -> str:
    cleaned_url = platform_url.strip().rstrip("/")

    if not cleaned_url:
        raise ValueError(
            "AUTOMATION_PLATFORM_URL is required."
        )

    if not cleaned_url.startswith(
        ("http://", "https://")
    ):
        raise ValueError(
            "AUTOMATION_PLATFORM_URL must start with "
            "http:// or https://."
        )

    return cleaned_url


@dataclass(frozen=True)
class MacOSAgentSettings:
    platform_url: str
    agent_id: int | None
    agent_name: str
    hostname: str
    api_key: str
    heartbeat_interval_seconds: int
    request_timeout_seconds: int


def load_agent_settings() -> MacOSAgentSettings:
    """
    Load and validate macOS Agent configuration
    from environment variables.
    """

    platform_url = _clean_platform_url(
        os.getenv(
            "AUTOMATION_PLATFORM_URL",
            DEFAULT_PLATFORM_URL,
        )
    )

    agent_id = _get_optional_integer(
        "AUTOMATION_AGENT_ID"
    )

    hostname = os.getenv(
        "AUTOMATION_AGENT_HOSTNAME",
        socket.gethostname(),
    ).strip()

    if not hostname:
        raise ValueError(
            "AUTOMATION_AGENT_HOSTNAME is required."
        )

    agent_name = os.getenv(
        "AUTOMATION_AGENT_NAME",
        hostname,
    ).strip()

    if not agent_name:
        raise ValueError(
            "AUTOMATION_AGENT_NAME is required."
        )

    api_key = os.getenv(
        "AUTOMATION_AGENT_API_KEY",
        "",
    ).strip()

    if not api_key:
        raise ValueError(
            "AUTOMATION_AGENT_API_KEY is not configured."
        )

    heartbeat_interval_seconds = (
        _get_positive_integer(
            "AUTOMATION_AGENT_HEARTBEAT_SECONDS",
            DEFAULT_HEARTBEAT_INTERVAL_SECONDS,
        )
    )

    request_timeout_seconds = (
        _get_positive_integer(
            "AUTOMATION_AGENT_REQUEST_TIMEOUT_SECONDS",
            DEFAULT_REQUEST_TIMEOUT_SECONDS,
        )
    )

    return MacOSAgentSettings(
        platform_url=platform_url,
        agent_id=agent_id,
        agent_name=agent_name,
        hostname=hostname,
        api_key=api_key,
        heartbeat_interval_seconds=(
            heartbeat_interval_seconds
        ),
        request_timeout_seconds=(
            request_timeout_seconds
        ),
    )