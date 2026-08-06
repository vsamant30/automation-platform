from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AgentJobLogCreate(BaseModel):
    stream: str = Field(
        default="stdout",
        min_length=1,
        max_length=20,
    )

    message: str = Field(
        min_length=1,
    )


class AgentJobLogResponse(BaseModel):
    id: int
    agent_job_id: int
    stream: str
    message: str
    sequence: int
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
    )