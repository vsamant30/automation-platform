import json
import os

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


def claim_next_job(
    settings: WindowsAgentSettings,
) -> dict | None:
    """
    Ask the Automation Platform for the oldest
    queued job assigned to this agent.
    """

    if settings.agent_id is None:
        raise ValueError(
            "AUTOMATION_AGENT_ID is not configured."
        )

    if not settings.authentication_token:
        raise ValueError(
            "AUTOMATION_AGENT_TOKEN is not configured."
        )

    claim_url = (
        f"{settings.platform_url}"
        f"/api/v1/agent-jobs"
        f"/agents/{settings.agent_id}/claim"
    )

    response = _send_json_request(
        url=claim_url,
        method="POST",
        settings=settings,
    )

    if not response.get("success", False):
        raise RuntimeError(
            response.get(
                "message",
                "Unable to claim agent job.",
            )
        )

    return response.get("data")

def mark_job_running(
    settings: WindowsAgentSettings,
    agent_job_id: int,
) -> dict:
    """
    Notify the Automation Platform that
    the agent has started executing a job.
    """

    running_url = (
        f"{settings.platform_url}"
        f"/api/v1/agent-jobs"
        f"/{agent_job_id}/running"
    )

    response = _send_json_request(
        url=running_url,
        method="POST",
        settings=settings,
        payload={
            "agent_id": settings.agent_id,
        },
    )

    if not response.get("success", False):
        raise RuntimeError(
            response.get(
                "message",
                "Unable to mark job as running.",
            )
        )

    return response.get("data")


def complete_job(
    settings: WindowsAgentSettings,
    agent_job_id: int,
    result: str | None = None,
) -> dict:
    """
    Notify the Automation Platform that
    the job completed successfully.
    """

    complete_url = (
        f"{settings.platform_url}"
        f"/api/v1/agent-jobs"
        f"/{agent_job_id}/complete"
    )

    response = _send_json_request(
        url=complete_url,
        method="POST",
        settings=settings,
        payload={
            "agent_id": settings.agent_id,
            "result": result,
        },
    )

    if not response.get("success", False):
        raise RuntimeError(
            response.get(
                "message",
                "Unable to complete job.",
            )
        )

    return response.get("data")


def fail_job(
    settings: WindowsAgentSettings,
    agent_job_id: int,
    error_message: str,
    result: str | None = None,
) -> dict:
    """
    Notify the Automation Platform that
    the job failed.
    """

    cleaned_error_message = error_message.strip()

    if not cleaned_error_message:
        raise ValueError(
            "Error message is required."
        )

    fail_url = (
        f"{settings.platform_url}"
        f"/api/v1/agent-jobs"
        f"/{agent_job_id}/fail"
    )

    response = _send_json_request(
        url=fail_url,
        method="POST",
        settings=settings,
        payload={
            "agent_id": settings.agent_id,
            "error_message": cleaned_error_message,
            "result": result,
        },
    )

    if not response.get("success", False):
        raise RuntimeError(
            response.get(
                "message",
                "Unable to mark job as failed.",
            )
        )

    return response.get("data")


def download_job_script(
    settings: WindowsAgentSettings,
    *,
    job_id: int,
    destination_directory: str,
) -> str:
    """
    Download one job script from the platform
    and return its saved local path.
    """

    if job_id <= 0:
        raise ValueError(
            "Job ID must be greater than zero."
        )

    cleaned_destination_directory = (
        destination_directory.strip()
    )

    if not cleaned_destination_directory:
        raise ValueError(
            "Destination directory is required."
        )

    os.makedirs(
        cleaned_destination_directory,
        exist_ok=True,
    )

    download_url = (
        f"{settings.platform_url}"
        f"/api/v1/jobs/{job_id}/script"
    )

    request = Request(
        url=download_url,
        headers=_build_headers(settings),
        method="GET",
    )

    try:
        with urlopen(
            request,
            timeout=settings.request_timeout_seconds,
        ) as response:
            content_disposition = response.headers.get(
                "Content-Disposition",
                "",
            )

            filename = ""

            if "filename=" in content_disposition:
                filename = (
                    content_disposition
                    .split("filename=", 1)[1]
                    .strip()
                    .strip('"')
                )

            if not filename:
                filename = (
                    f"job_{job_id}_script"
                )

            safe_filename = os.path.basename(
                filename
            )

            destination_path = os.path.join(
                cleaned_destination_directory,
                safe_filename,
            )

            with open(
                destination_path,
                "wb",
            ) as destination_file:
                destination_file.write(
                    response.read()
                )

            return destination_path

    except HTTPError as error:
        error_body = (
            error.read()
            .decode("utf-8", errors="replace")
            .strip()
        )

        raise RuntimeError(
            "Job script download failed. "
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
            "Job script download timed out."
        ) from error