from datetime import datetime

from pydantic import BaseModel, ConfigDict


class JobCreate(BaseModel):
    name: str


class JobResponse(BaseModel):
    id: int
    name: str
    status: str

    result: str | None = None
    error_message: str | None = None

    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration: float | None = None

    created_at: datetime

    model_config = ConfigDict(from_attributes=True)