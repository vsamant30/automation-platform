from fastapi import APIRouter, Depends, HTTPException

from app.core.auth import get_current_user
from app.core.permissions import require_admin
from app.db.models import User
from app.schemas.agent import (
    AgentCreate,
    AgentResponse,
    AgentUpdate,
)
from app.schemas.api_response import ApiResponse
from app.services.agent_service import (
    create_agent,
    delete_agent,
    get_agent,
    get_agents,
    update_agent,
)


router = APIRouter()


@router.get(
    "/",
    response_model=ApiResponse[list[AgentResponse]],
)
def get_agents_v1(
    current_user: User = Depends(get_current_user),
):
    require_admin(current_user)

    agents = get_agents()

    return ApiResponse(
        success=True,
        message="Agents retrieved successfully.",
        data=agents,
    )


@router.get(
    "/{agent_id}",
    response_model=ApiResponse[AgentResponse],
)
def get_agent_v1(
    agent_id: int,
    current_user: User = Depends(get_current_user),
):
    require_admin(current_user)

    agent = get_agent(agent_id)

    if agent is None:
        raise HTTPException(
            status_code=404,
            detail="Agent not found.",
        )

    return ApiResponse(
        success=True,
        message="Agent retrieved successfully.",
        data=agent,
    )


@router.post(
    "/",
    response_model=ApiResponse[AgentResponse],
    status_code=201,
)
def create_agent_v1(
    agent_data: AgentCreate,
    current_user: User = Depends(get_current_user),
):
    require_admin(current_user)

    try:
        agent = create_agent(
            name=agent_data.name,
            platform=agent_data.platform,
            base_url=agent_data.base_url,
            hostname=agent_data.hostname,
        )

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

    return ApiResponse(
        success=True,
        message="Agent created successfully.",
        data=agent,
    )


@router.put(
    "/{agent_id}",
    response_model=ApiResponse[AgentResponse],
)
def update_agent_v1(
    agent_id: int,
    agent_data: AgentUpdate,
    current_user: User = Depends(get_current_user),
):
    require_admin(current_user)

    try:
        agent = update_agent(
            agent_id=agent_id,
            name=agent_data.name,
            platform=agent_data.platform,
            base_url=agent_data.base_url,
            hostname=agent_data.hostname,
            is_enabled=agent_data.is_enabled,
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
        message="Agent updated successfully.",
        data=agent,
    )


@router.delete(
    "/{agent_id}",
    response_model=ApiResponse[dict],
)
def delete_agent_v1(
    agent_id: int,
    current_user: User = Depends(get_current_user),
):
    require_admin(current_user)

    deleted = delete_agent(agent_id)

    if not deleted:
        raise HTTPException(
            status_code=404,
            detail="Agent not found.",
        )

    return ApiResponse(
        success=True,
        message="Agent deleted successfully.",
        data={
            "agent_id": agent_id,
            "deleted": True,
        },
    )