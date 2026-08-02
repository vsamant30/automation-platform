from fastapi import HTTPException

from app.db.models import User


def require_admin(user: User):
    if user.role.lower() != "admin":
        raise HTTPException(
            status_code=403,
            detail="Admin privileges required",
        )

    return user