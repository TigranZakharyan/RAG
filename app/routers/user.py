from typing import Annotated

from fastapi import APIRouter, Depends

from models.user import User
from dependencies import auth_dependency
from schemas.user import MeResponse

user_router = APIRouter(
    prefix="/users",
    tags=["users"],
)

@user_router.get("/me", response_model=MeResponse)
async def get_me(
    user: User = Depends(auth_dependency)
):
    print(user)
    return MeResponse(
        id=user.id,
        username=user.username,
    )