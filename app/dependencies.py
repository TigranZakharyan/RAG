from fastapi import Cookie, Depends, HTTPException, status, Depends
from fastapi import Security
from fastapi.security import APIKeyCookie
from sqlmodel import Session, select

from db.database import get_session
from libs.auth import verify_access_token
from models.user import User

access_token_cookie = APIKeyCookie(
    name="access_token",
    auto_error=True,
)

async def auth_dependency(
    access_token: str = Depends(access_token_cookie),
    session: Session = Depends(get_session),
) -> User:
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    try:
        payload = verify_access_token(access_token)

        user_id = payload.get("sub")

        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token",
            )

        user = session.exec(
            select(User).where(User.id == int(user_id))
        ).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
            )

        return user

    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token",
        )