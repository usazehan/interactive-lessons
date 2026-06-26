"""Authentication: password hashing, JWT access tokens, and the current-user
dependency used to protect endpoints.
"""
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app.config import settings
from app.models import Project, User
from app.store import project_store, user_store

# tokenUrl is the login route, so the docs "Authorize" button works.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

_credentials_error = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


def _pw_bytes(password: str) -> bytes:
    # bcrypt only uses the first 72 bytes; truncate so long inputs don't error.
    return password.encode("utf-8")[:72]


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_pw_bytes(password), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(_pw_bytes(password), hashed.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(subject: int | str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    payload = {"sub": str(subject), "exp": expire}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    try:
        payload = jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
        )
        user_id = int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise _credentials_error

    user = user_store.get(user_id)
    if user is None:
        raise _credentials_error
    return user


def require_project_owner(project_id: int, current_user: User) -> Project:
    """404 if the project is missing, 403 if the user isn't its owner."""
    project = project_store.get(project_id)
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="project not found"
        )
    if project.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="not the project owner"
        )
    return project
