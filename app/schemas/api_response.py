from typing import Generic, TypeVar

from pydantic import BaseModel, Field


DataType = TypeVar("DataType")


class ApiResponse(BaseModel, Generic[DataType]):
    success: bool = True
    message: str
    data: DataType | None = None


class ApiErrorResponse(BaseModel):
    success: bool = False
    message: str
    errors: list[str] = Field(default_factory=list)