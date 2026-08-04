from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.permissions import require_admin
from app.core.security import hash_password
from app.db.database import get_db
from app.db.models import User
from app.schemas.api_response import ApiResponse
from app.schemas.user import UserCreate, UserResponse


router = APIRouter()


@router.get(
    "/",
    response_model=ApiResponse[list[UserResponse]],
)
def get_users_v1(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_admin(current_user)

    users = db.query(User).all()

    return ApiResponse(
        success=True,
        message="Users retrieved successfully.",
        data=users,
    )


@router.post(
    "/",
    response_model=ApiResponse[UserResponse],
    status_code=201,
)
def create_user_v1(
    user_data: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_admin(current_user)

    existing_username = (
        db.query(User)
        .filter(User.username == user_data.username)
        .first()
    )

    if existing_username:
        raise HTTPException(
            status_code=400,
            detail="Username already exists.",
        )

    existing_email = (
        db.query(User)
        .filter(User.email == user_data.email)
        .first()
    )

    if existing_email:
        raise HTTPException(
            status_code=400,
            detail="Email already exists.",
        )

    new_user = User(
        username=user_data.username.strip(),
        email=user_data.email,
        hashed_password=hash_password(user_data.password),
        role=user_data.role.strip().lower(),
        is_active=True,
    )

    try:
        db.add(new_user)
        db.commit()
        db.refresh(new_user)

    except Exception:
        db.rollback()
        raise

    return ApiResponse(
        success=True,
        message="User created successfully.",
        data=new_user,
    )