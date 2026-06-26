"""Auth flow: registration, login, token refresh/logout, email verification,
and password reset.

Log in to receive a short-lived **access** token (bearer) and a longer-lived
**refresh** token. Rotate via /auth/refresh; revoke via /auth/logout. New
accounts are unverified until /auth/verify-email; authoring requires a verified
email.
"""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from app.auth import (
    create_access_token,
    generate_opaque_token,
    get_current_user,
    hash_password,
    hash_token,
    verify_password,
)
from app.config import settings
from app.email import send_email
from app.models import (
    ForgotPasswordRequest,
    RefreshRequest,
    ResetPasswordRequest,
    Token,
    User,
    UserCreate,
    VerifyEmailRequest,
)
from app.store import refresh_token_store, user_store

router = APIRouter(prefix="/auth", tags=["auth"])


def _issue_tokens(user_id: int) -> Token:
    raw_refresh = generate_opaque_token()
    expires = datetime.utcnow() + timedelta(days=settings.refresh_token_expire_days)
    refresh_token_store.create(user_id, hash_token(raw_refresh), expires)
    return Token(
        access_token=create_access_token(user_id), refresh_token=raw_refresh
    )


@router.post("/register", response_model=User, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate) -> User:
    if user_store.get_orm_by_email(payload.email) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="email already registered"
        )
    verification_token = generate_opaque_token()
    user = user_store.create(
        payload.email, hash_password(payload.password), verification_token
    )
    send_email(
        payload.email,
        "Verify your email",
        f"Confirm your account: {settings.app_base_url}/verify-email"
        f"?token={verification_token}",
    )
    return user


@router.post("/login", response_model=Token)
def login(form: OAuth2PasswordRequestForm = Depends()) -> Token:
    # OAuth2 form uses `username`; we treat it as the email.
    user = user_store.get_orm_by_email(form.username)
    if user is None or not verify_password(form.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return _issue_tokens(user.id)


@router.post("/refresh", response_model=Token)
def refresh(payload: RefreshRequest) -> Token:
    # Rotation: the presented refresh token is consumed (revoked) and replaced.
    user_id = refresh_token_store.consume(hash_token(payload.refresh_token))
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid or expired refresh token",
        )
    return _issue_tokens(user_id)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(payload: RefreshRequest) -> None:
    # Idempotent: revoking an unknown/already-revoked token is a no-op.
    refresh_token_store.revoke(hash_token(payload.refresh_token))


@router.post("/verify-email", response_model=User)
def verify_email(payload: VerifyEmailRequest) -> User:
    user = user_store.verify_by_token(payload.token)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid verification token",
        )
    return user


@router.post("/forgot-password", status_code=status.HTTP_202_ACCEPTED)
def forgot_password(payload: ForgotPasswordRequest) -> dict:
    token = generate_opaque_token()
    expires = datetime.utcnow() + timedelta(
        minutes=settings.reset_token_expire_minutes
    )
    # Only send if the email exists, but always return the same response so the
    # endpoint can't be used to enumerate registered emails.
    if user_store.set_reset_token(payload.email, token, expires):
        send_email(
            payload.email,
            "Reset your password",
            f"Reset your password: {settings.app_base_url}/reset-password"
            f"?token={token}",
        )
    return {"detail": "if that email exists, a reset link has been sent"}


@router.post("/reset-password", status_code=status.HTTP_204_NO_CONTENT)
def reset_password(payload: ResetPasswordRequest) -> None:
    user_id = user_store.reset_password_by_token(
        payload.token, hash_password(payload.new_password)
    )
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid or expired reset token",
        )
    # A reset invalidates every existing session.
    refresh_token_store.revoke_all_for_user(user_id)


@router.get("/me", response_model=User)
def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user
