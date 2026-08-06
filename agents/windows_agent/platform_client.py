import json

from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from agents.windows_agent.config import (
    WindowsAgentSettings,
)


def _build_headers(
    settings: WindowsAgentSettings,
) -> dict[str, str]:
    """
    Build the common HTTP headers used by the
    Windows Agent.
    """

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": (
            "Automation-Platform-Windows-Agent/1.0"
        ),
    }

    if settings.authentication_token:
        headers["Authorization"] = (
            f"Bearer {settings.authentication_token}"
        )

    return headers


def _send_json_request(
    *,
    url: str,
    method: str,
    settings: WindowsAgentSettings,
    payload: dict | None = None,
) -> dict:
    """
    Send one JSON request to the Automation Platform.
    """

    request_body = None

    if payload is not None:
        request_body = json.dumps(
            payload
        ).encode("utf-8")

    request = Request(
        url=url,
        data=request_body,
        headers=_build_headers(settings),
        method=method.upper(),
    )

    try:
        with urlopen(
            request,
            timeout=settings.request_timeout_seconds,
        ) as response:
            response_body = (
                response.read()
                .decode("utf-8")
                .strip()
            )

            if not response_body:
                return {}

            return json.loads(response_body)

    except HTTPError as error:
        error_body = (
            error.read()
            .decode("utf-8", errors="replace")
            .strip()
        )

        raise RuntimeError(
            "Automation Platform request failed. "
            f"HTTP status: {error.code}. "
            f"Response: {error_body or '-'}"
        ) from error

    except URLError as error:
        raise RuntimeError(
            "Unable to connect to the Automation Platform. "
            f"Reason: {error.reason}"
        ) from error

    except TimeoutError as error:
        raise RuntimeError(
            "Automation Platform request timed out."
        ) from error

    except json.JSONDecodeError as error:
        raise RuntimeError(
            "Automation Platform returned invalid JSON."
        ) from error


def send_heartbeat(
    settings: WindowsAgentSettings,
) -> dict:
    """
    Send the current agent heartbeat to the platform.
    """

    if settings.agent_id is None:
        raise ValueError(
            "AUTOMATION_AGENT_ID is not configured."
        )

    if not settings.authentication_token:
        raise ValueError(
            "AUTOMATION_AGENT_TOKEN is not configured."
        )

    heartbeat_url = (
        f"{settings.platform_url}"
        f"/api/v1/agents/{settings.agent_id}"
        "/heartbeat"
    )

    return _send_json_request(
        url=heartbeat_url,
        method="POST",
        settings=settings,
        payload={
            "hostname": settings.hostname,
        },
    )