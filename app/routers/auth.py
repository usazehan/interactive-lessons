"""Registration and login.

Register with an email + password, then log in to receive a JWT access token
to send as `Authorization: Bearer <token>` on protected requests.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from app.auth import (
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from app.models import Token, User, UserCreate
from app.store import user_store

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=User, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate) -> User:
    if user_store.get_orm_by_email(payload.email) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="email already registered"
        )
    return user_store.create(payload.email, hash_password(payload.password))


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
    return Token(access_token=create_access_token(user.id))


@router.get("/me", response_model=User)
def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user
