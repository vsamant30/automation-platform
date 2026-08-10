from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AgentCreate(BaseModel):
    name: str
    platform: str
    base_url: str
    hostname: str | None = None


class AgentUpdate(BaseModel):
    name: str
    platform: str
    base_url: str
    hostname: str | None = None
    is_enabled: bool


class AgentHeartbeat(BaseModel):
    hostname: str | None = None


class AgentResponse(BaseModel):
    id: int
    name: str
    platform: str
    hostname: str | None
    base_url: str
    status: str
    is_enabled: bool
    last_seen_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True
    )


class AgentAPIKeyResponse(BaseModel):
    agent_id: int
    api_key: str