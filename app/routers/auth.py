from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status, Response 
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import Session, select

from models.user import User
from libs.crypt import verify_password, crypt_password
from libs.auth import create_access_token
from core.database import get_session
from schemas.auth import UserCreate, UserCreateResponse, LoginResponse

auth_router = APIRouter(prefix="/auth", tags=["auth"])

@auth_router.post(
    "/register",
    response_model=UserCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register_user(
    data: UserCreate,
    session: Session = Depends(get_session),
):
    # Check if username already exists
    existing_user = session.exec(
        select(User).where(User.username == data.username)
    ).first()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this username already exists",
        )

    hashed_password = crypt_password(data.password)

    user = User(
        username=data.username,
        password=hashed_password,
    )

    session.add(user)
    session.commit()
    session.refresh(user)

    return UserCreateResponse(
        id=user.id,
        username=user.username,
    )

@auth_router.post("/login", response_model=LoginResponse)
async def login_user(
    response: Response,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    session: Session = Depends(get_session),
):
    user = session.exec(
        select(User).where(User.username == form_data.username)
    ).first()

    if not user or not verify_password(
        form_data.password,
        user.password,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(
        {"sub": str(user.id)}
    )

    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=True,       # False for local HTTP development
        samesite="lax",
        max_age=60 * 60,
    )

    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
    )

@auth_router.post("/logout")
async def logout_user(response: Response):
    response.delete_cookie(
        key="access_token",
    )

    return {
        "message": "Logout successful",
    }