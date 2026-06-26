"""Authentication: password hashing, tokens, and the dependencies used to
protect endpoints.

Access tokens are short-lived JWTs (carry `type=access`). Refresh tokens are
opaque, high-entropy strings stored server-side *hashed* so they can be revoked
(see app.store.RefreshTokenStore). Verification / reset tokens are likewise
opaque random strings.
"""
import hashlib
import secrets
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


# --- passwords ---------------------------------------------------------------


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


# --- tokens ------------------------------------------------------------------


def create_access_token(subject: int | str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    payload = {"sub": str(subject), "type": "access", "exp": expire}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def generate_opaque_token() -> str:
    """A random token to hand to a client (refresh / verify / reset)."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """Hash a high-entropy token for storage (sha256 is fine; not a password)."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


# --- dependencies ------------------------------------------------------------


def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    try:
        payload = jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
        )
        if payload.get("type") != "access":
            raise _credentials_error
        user_id = int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise _credentials_error

    user = user_store.get(user_id)
    if user is None:
        raise _credentials_error
    return user


def require_verified_user(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="email not verified",
        )
    return current_user


def require_project_owner(project_id: int, current_user: User) -> Project:
    """404 if missing; 403 unless the user owns it (admins bypass ownership)."""
    project = project_store.get(project_id)
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="project not found"
        )
    if current_user.role != "admin" and project.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="not the project owner"
        )
    return project
