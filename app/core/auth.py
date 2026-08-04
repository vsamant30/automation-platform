from datetime import datetime, timedelta

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import User

from app.core.config import settings

security_scheme = HTTPBearer()


def create_access_token(data: dict) -> str:
    to_encode = data.copy()

    expire = datetime.utcnow() + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )

    to_encode.update({"exp": expire})

    return jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def verify_access_token(token: str) -> dict:
    return jwt.decode(
        token,
        settings.SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
    db: Session = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=401,
        detail="Invalid or expired authentication token",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = verify_access_token(credentials.credentials)
        username = payload.get("sub")

        if not username:
            raise credentials_exception

    except JWTError:
        raise credentials_exception

    user = (
        db.query(User)
        .filter(User.username == username)
        .first()
    )

    if not user or not user.is_active:
        raise credentials_exception

    return user


def get_current_user_from_cookie(
    request: Request,
    db: Session,
) -> User | None:
    token = request.cookies.get("access_token")

    if not token:
        return None

    try:
        payload = verify_access_token(token)
        username = payload.get("sub")

        if not username:
            return None

    except JWTError:
        return None

    user = (
        db.query(User)
        .filter(User.username == username)
        .first()
    )

    if not user or not user.is_active:
        return None

    return user


def require_admin(user: User) -> None:
    if user.role.lower() != "admin":
        raise HTTPException(
            status_code=403,
            detail="Administrator privileges required.",
        )