from fastapi import APIRouter, Depends, HTTPException

from app.core.auth import (
    get_authenticated_agent_id,
    get_current_user,
)
from app.core.permissions import require_admin
from app.db.models import User
from app.schemas.agent_job import (
    AgentJobClaimResponse,
    AgentJobCompleteRequest,
    AgentJobFailRequest,
    AgentJobQueueRequest,
    AgentJobResponse,
    AgentJobRunningRequest,
)

from app.schemas.agent_job_log import (
    AgentJobLogCreate,
    AgentJobLogResponse,
)

from app.services.agent_job_log_service import (
    append_agent_job_log,
    get_agent_job_logs,
)

from app.schemas.api_response import ApiResponse
from app.services.agent_job_service import (
    claim_next_agent_job,
    complete_agent_job,
    fail_agent_job,
    get_agent_job,
    get_agent_jobs,
    mark_agent_job_running,
    queue_job_for_agent,
)


router = APIRouter()


@router.get(
    "/",
    response_model=ApiResponse[list[AgentJobResponse]],
)
def get_agent_jobs_v1(
    current_user: User = Depends(get_current_user),
):
    require_admin(current_user)

    agent_jobs = get_agent_jobs()

    return ApiResponse(
        success=True,
        message="Agent jobs retrieved successfully.",
        data=agent_jobs,
    )


@router.get(
    "/{agent_job_id}",
    response_model=ApiResponse[AgentJobResponse],
)
def get_agent_job_v1(
    agent_job_id: int,
    current_user: User = Depends(get_current_user),
):
    require_admin(current_user)

    agent_job = get_agent_job(agent_job_id)

    if agent_job is None:
        raise HTTPException(
            status_code=404,
            detail="Agent job not found.",
        )

    return ApiResponse(
        success=True,
        message="Agent job retrieved successfully.",
        data=agent_job,
    )


@router.post(
    "/",
    response_model=ApiResponse[AgentJobResponse],
    status_code=201,
)
def queue_agent_job_v1(
    queue_data: AgentJobQueueRequest,
    current_user: User = Depends(get_current_user),
):
    require_admin(current_user)

    try:
        agent_job = queue_job_for_agent(
            agent_id=queue_data.agent_id,
            job_id=queue_data.job_id,
            job_execution_id=(
                queue_data.job_execution_id
            ),
        )

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

    return ApiResponse(
        success=True,
        message="Agent job queued successfully.",
        data=agent_job,
    )


@router.post(
    "/agents/{agent_id}/claim",
    response_model=ApiResponse[
        AgentJobClaimResponse | None
    ],
)
def claim_agent_job_v1(
    agent_id: int,
    authenticated_agent_id: int = Depends(
        get_authenticated_agent_id
    ),
):
    if authenticated_agent_id != agent_id:
        raise HTTPException(
            status_code=403,
            detail="Agent ID does not match authenticated Agent.",
        )

    try:
        agent_job = claim_next_agent_job(
            agent_id
        )

    except ValueError as error:
        error_message = str(error)

        status_code = (
            404
            if error_message.startswith(
                "Agent not found:"
            )
            else 400
        )

        raise HTTPException(
            status_code=status_code,
            detail=error_message,
        ) from error

    return ApiResponse(
        success=True,
        message=(
            "Agent job claimed successfully."
            if agent_job is not None
            else "No queued agent job is available."
        ),
        data=agent_job,
    )


@router.post(
    "/{agent_job_id}/running",
    response_model=ApiResponse[AgentJobResponse],
)
def mark_agent_job_running_v1(
    agent_job_id: int,
    request_data: AgentJobRunningRequest,
    authenticated_agent_id: int = Depends(
        get_authenticated_agent_id
    ),
):
    if authenticated_agent_id != request_data.agent_id:
        raise HTTPException(
            status_code=403,
            detail="Agent ID does not match authenticated Agent.",
        )

    try:
        agent_job = mark_agent_job_running(
            agent_job_id=agent_job_id,
            agent_id=request_data.agent_id,
        )

    except ValueError as error:
        error_message = str(error)

        status_code = (
            404
            if error_message.startswith(
                "Agent job not found:"
            )
            else 400
        )

        raise HTTPException(
            status_code=status_code,
            detail=error_message,
        ) from error

    return ApiResponse(
        success=True,
        message="Agent job marked as running.",
        data=agent_job,
    )


@router.post(
    "/{agent_job_id}/complete",
    response_model=ApiResponse[AgentJobResponse],
)
def complete_agent_job_v1(
    agent_job_id: int,
    request_data: AgentJobCompleteRequest,
    authenticated_agent_id: int = Depends(
        get_authenticated_agent_id
    ),
):
    if authenticated_agent_id != request_data.agent_id:
        raise HTTPException(
            status_code=403,
            detail="Agent ID does not match authenticated Agent.",
        )

    try:
        agent_job = complete_agent_job(
            agent_job_id=agent_job_id,
            agent_id=request_data.agent_id,
            result=request_data.result,
        )

    except ValueError as error:
        error_message = str(error)

        status_code = (
            404
            if error_message.startswith(
                "Agent job not found:"
            )
            else 400
        )

        raise HTTPException(
            status_code=status_code,
            detail=error_message,
        ) from error

    return ApiResponse(
        success=True,
        message="Agent job completed successfully.",
        data=agent_job,
    )


@router.post(
    "/{agent_job_id}/fail",
    response_model=ApiResponse[AgentJobResponse],
)
def fail_agent_job_v1(
    agent_job_id: int,
    request_data: AgentJobFailRequest,
    authenticated_agent_id: int = Depends(
        get_authenticated_agent_id
    ),
):
    if authenticated_agent_id != request_data.agent_id:
        raise HTTPException(
            status_code=403,
            detail="Agent ID does not match authenticated Agent.",
        )

    try:
        agent_job = fail_agent_job(
            agent_job_id=agent_job_id,
            agent_id=request_data.agent_id,
            error_message=request_data.error_message,
            result=request_data.result,
        )

    except ValueError as error:
        error_message = str(error)

        status_code = (
            404
            if error_message.startswith(
                "Agent job not found:"
            )
            else 400
        )

        raise HTTPException(
            status_code=status_code,
            detail=error_message,
        ) from error

    return ApiResponse(
        success=True,
        message="Agent job marked as failed.",
        data=agent_job,
    )


@router.post(
    "/{agent_job_id}/logs",
    response_model=ApiResponse[AgentJobLogResponse],
    status_code=201,
)

def append_agent_job_log_v1(
    agent_job_id: int,
    log_data: AgentJobLogCreate,
    authenticated_agent_id: int = Depends(
        get_authenticated_agent_id
    ),
):
    """
    Append one live log line to a remote job.
    """

    agent_job = get_agent_job(
        agent_job_id
    )

    if agent_job is None:
        raise HTTPException(
            status_code=404,
            detail="Agent job not found.",
        )

    if agent_job.agent_id != authenticated_agent_id:
        raise HTTPException(
            status_code=403,
            detail=(
                "Agent job does not belong to "
                "the authenticated Agent."
            ),
        )

    try:
        log = append_agent_job_log(
            agent_job_id=agent_job_id,
            stream=log_data.stream,
            message=log_data.message,
        )

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

    return ApiResponse(
        success=True,
        message="Agent job log appended successfully.",
        data=log,
    )

@router.get(
    "/{agent_job_id}/logs",
    response_model=ApiResponse[list[AgentJobLogResponse]],
)
def get_agent_job_logs_v1(
    agent_job_id: int,
    current_user: User = Depends(get_current_user),
):
    """
    Return live log lines for one remote job.
    """

    logs = get_agent_job_logs(
        agent_job_id
    )

    return ApiResponse(
        success=True,
        message="Agent job logs retrieved successfully.",
        data=logs,
    )
