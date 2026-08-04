from datetime import datetime

from pydantic import BaseModel, ConfigDict


class JobCreate(BaseModel):
    name: str
    is_enabled: bool = True
    dependency_job_id: int | None = None


class JobResponse(BaseModel):
    id: int
    name: str
    status: str
    is_enabled: bool
    dependency_job_id: int | None = None

    result: str | None = None
    error_message: str | None = None

    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration: float | None = None

    created_at: datetime

    model_config = ConfigDict(from_attributes=True)