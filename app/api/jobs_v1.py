from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.db.database import get_db
from app.db.models import Job, User
from app.schemas.api_response import ApiResponse
from app.schemas.job import JobResponse


router = APIRouter()


@router.get(
    "/",
    response_model=ApiResponse[list[JobResponse]],
)
def get_jobs_v1(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    jobs = db.query(Job).all()

    return ApiResponse(
        success=True,
        message="Jobs retrieved successfully.",
        data=jobs,
    )