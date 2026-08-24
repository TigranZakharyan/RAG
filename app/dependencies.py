from fastapi import Cookie, Depends, Header, HTTPException, status
from sqlmodel import Session, select

from core.database import get_session
from libs.auth import verify_access_token
from models.user import User


async def auth_dependency(
    access_token: str | None = Cookie(default=None),
    authorization: str | None = Header(default=None),
    session: Session = Depends(get_session),
) -> User:
    token = access_token
    if not token and authorization and authorization.startswith("Bearer "):
        token = authorization.split("Bearer ")[1].strip()

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )


    try:
        payload = verify_access_token(token)

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