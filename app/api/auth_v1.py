from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.auth import (
    create_access_token,
    get_current_user,
)
from app.core.security import verify_password
from app.db.database import get_db
from app.db.models import User
from app.schemas.api_response import ApiResponse
from app.schemas.auth import LoginRequest, TokenResponse
from app.schemas.user import UserResponse


router = APIRouter()


@router.post(
    "/login",
    response_model=ApiResponse[TokenResponse],
)
def login_v1(
    request: LoginRequest,
    db: Session = Depends(get_db),
):
    user = (
        db.query(User)
        .filter(User.username == request.username)
        .first()
    )

    if not user or not verify_password(
        request.password,
        user.hashed_password,
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid username or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=403,
            detail="User account is inactive.",
        )

    token = create_access_token(
        {
            "sub": user.username,
            "role": user.role,
        }
    )

    return ApiResponse(
        success=True,
        message="Login successful.",
        data=TokenResponse(
            access_token=token,
        ),
    )


@router.get(
    "/me",
    response_model=ApiResponse[UserResponse],
)
def get_my_profile_v1(
    current_user: User = Depends(get_current_user),
):
    return ApiResponse(
        success=True,
        message="User profile retrieved successfully.",
        data=current_user,
    )