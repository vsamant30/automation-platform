from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AgentJobQueueRequest(BaseModel):
    agent_id: int
    job_id: int
    job_execution_id: int | None = None


class AgentJobClaimResponse(BaseModel):
    id: int
    agent_id: int
    job_id: int
    job_execution_id: int | None

    job_name: str
    script_type: str
    script_path: str

    status: str

    queued_at: datetime
    claimed_at: datetime | None
    started_at: datetime | None
    completed_at: datetime | None

    model_config = ConfigDict(
        from_attributes=True
    )


class AgentJobRunningRequest(BaseModel):
    agent_id: int


class AgentJobCompleteRequest(BaseModel):
    agent_id: int
    result: str | None = None


class AgentJobFailRequest(BaseModel):
    agent_id: int
    error_message: str
    result: str | None = None


class AgentJobResponse(BaseModel):
    id: int
    agent_id: int
    job_id: int
    job_execution_id: int | None

    job_name: str
    script_type: str
    script_path: str

    status: str
    result: str | None
    error_message: str | None

    queued_at: datetime
    claimed_at: datetime | None
    started_at: datetime | None
    completed_at: datetime | None

    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True
    )