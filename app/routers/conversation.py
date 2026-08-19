from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from core.database import get_session
from dependencies import auth_dependency
from models.conversation import Conversation
from models.user import User
from schemas.conversation import (
    ConversationCreate,
    ConversationListResponse,
    ConversationResponse,
    ConversationUpdate,
)


conversation_router = APIRouter(
    prefix="/conversations",
    tags=["conversations"],
)


# Create conversation
@conversation_router.post(
    "/",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_conversation(
    data: ConversationCreate,
    session: Session = Depends(get_session),
    user: Annotated[User, Depends(auth_dependency)] = None,
):
    conversation = Conversation(
        user_id=user.id,
        title=data.title,
    )

    session.add(conversation)
    session.commit()
    session.refresh(conversation)

    return conversation


# Get all conversations of current user
@conversation_router.get(
    "/",
    response_model=ConversationListResponse,
)
async def get_conversations(
    session: Session = Depends(get_session),
    user: Annotated[User, Depends(auth_dependency)] = None,
):
    conversations = session.exec(
        select(Conversation)
        .where(Conversation.user_id == user.id)
        .order_by(Conversation.updated_at.desc())
    ).all()

    return ConversationListResponse(
        conversations=[
            ConversationResponse(
                id=conversation.id,
                user_id=conversation.user_id,
                title=conversation.title,
                created_at=conversation.created_at,
                updated_at=conversation.updated_at,
            )
            for conversation in conversations
        ]
    )


# Get conversation by ID
@conversation_router.get(
    "/{conversation_id}",
    response_model=ConversationResponse,
)
async def get_conversation(
    conversation_id: int,
    session: Session = Depends(get_session),
    user: Annotated[User, Depends(auth_dependency)] = None,
):
    conversation = session.exec(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == user.id,
        )
    ).first()

    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )

    return conversation


# Update conversation
@conversation_router.patch(
    "/{conversation_id}",
    response_model=ConversationResponse,
)
async def update_conversation(
    conversation_id: int,
    data: ConversationUpdate,
    session: Session = Depends(get_session),
    user: Annotated[User, Depends(auth_dependency)] = None,
):
    conversation = session.exec(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == user.id,
        )
    ).first()

    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )

    if data.title is not None:
        conversation.title = data.title

    session.add(conversation)
    session.commit()
    session.refresh(conversation)

    return conversation


# Delete conversation
@conversation_router.delete(
    "/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_conversation(
    conversation_id: int,
    session: Session = Depends(get_session),
    user: Annotated[User, Depends(auth_dependency)] = None,
):
    conversation = session.exec(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == user.id,
        )
    ).first()

    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )

    session.delete(conversation)
    session.commit()

    return None