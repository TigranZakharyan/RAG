import json
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlmodel import Session, select

from core.database import get_session
from dependencies import auth_dependency
from models.conversation import Conversation
from models.message import Message, MessageRole
from models.user import User
from schemas.chat import (
    AsyncChatResponse,
    ChatHistoryResponse,
    ChatRequest,
    ChunkSource,
    MessageResponse,
)
from services.chat_service import chat_service
from workers.tasks import process_chat_message

chat_router = APIRouter(
    prefix="/chat",
    tags=["chat"],
)


def _verify_conversation_ownership(
    conversation_id: int,
    user_id: int,
    session: Session,
) -> Conversation:
    conversation = session.exec(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id,
        )
    ).first()
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )
    return conversation


@chat_router.post(
    "/{conversation_id}/stream",
    summary="Real-time RAG chat streaming with Ollama (SSE)",
)
async def stream_chat_endpoint(
    conversation_id: int,
    request: ChatRequest,
    session: Session = Depends(get_session),
    user: Annotated[User, Depends(auth_dependency)] = None,
):
    """
    Stream answer tokens directly in real time from Ollama using Server-Sent Events (SSE).
    Also performs hybrid retrieval from Qdrant, includes full parent chunks, and persists
    the conversation history and cited sources.
    """
    _verify_conversation_ownership(conversation_id, user.id, session)

    return StreamingResponse(
        chat_service.stream_rag_chat(
            conversation_id=conversation_id,
            user_id=user.id,
            chat_request=request,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@chat_router.post(
    "/{conversation_id}/async",
    response_model=AsyncChatResponse,
    summary="Background task RAG generation via Celery",
)
async def async_chat_endpoint(
    conversation_id: int,
    request: ChatRequest,
    session: Session = Depends(get_session),
    user: Annotated[User, Depends(auth_dependency)] = None,
):
    """
    Triggers RAG retrieval, prompt generation, and Ollama answer compilation in a background
    Celery task. The generated answer and sources are saved into the database upon completion.
    """
    _verify_conversation_ownership(conversation_id, user.id, session)

    task = process_chat_message.delay(
        conversation_id=conversation_id,
        user_id=user.id,
        message_text=request.message,
        top_k=request.top_k,
        score_threshold=request.score_threshold,
        model=request.model,
        temperature=request.temperature,
    )

    return AsyncChatResponse(
        task_id=task.id,
        status="queued",
        conversation_id=conversation_id,
    )


@chat_router.post(
    "/{conversation_id}",
    response_model=MessageResponse,
    summary="Synchronous RAG generation",
)
async def sync_chat_endpoint(
    conversation_id: int,
    request: ChatRequest,
    session: Session = Depends(get_session),
    user: Annotated[User, Depends(auth_dependency)] = None,
):
    """
    Executes RAG search, builds prompt, and waits for complete Ollama answer synchronously.
    """
    _verify_conversation_ownership(conversation_id, user.id, session)

    msg = chat_service.process_rag_chat_sync(
        conversation_id=conversation_id,
        user_id=user.id,
        message_text=request.message,
        top_k=request.top_k,
        score_threshold=request.score_threshold,
        model=request.model,
        temperature=request.temperature,
    )

    sources_list = None
    if msg.sources:
        try:
            raw_sources = json.loads(msg.sources)
            sources_list = [ChunkSource(**s) for s in raw_sources]
        except Exception:
            sources_list = None

    return MessageResponse(
        id=msg.id,
        conversation_id=msg.conversation_id,
        user_id=msg.user_id,
        role=msg.role.value if hasattr(msg.role, "value") else str(msg.role),
        content=msg.content,
        sources=sources_list,
        created_at=msg.created_at,
    )


@chat_router.get(
    "/{conversation_id}/messages",
    response_model=ChatHistoryResponse,
    summary="Get conversation message history and sources",
)
async def get_messages(
    conversation_id: int,
    limit: int = Query(default=50, ge=1, le=200),
    session: Session = Depends(get_session),
    user: Annotated[User, Depends(auth_dependency)] = None,
):
    _verify_conversation_ownership(conversation_id, user.id, session)

    messages = session.exec(
        select(Message)
        .where(
            Message.conversation_id == conversation_id,
            Message.user_id == user.id,
        )
        .order_by(Message.created_at.asc())
        .limit(limit)
    ).all()

    formatted_messages = []
    for msg in messages:
        sources_list = None
        if msg.sources:
            try:
                raw_sources = json.loads(msg.sources)
                sources_list = [ChunkSource(**s) for s in raw_sources]
            except Exception:
                sources_list = None

        formatted_messages.append(
            MessageResponse(
                id=msg.id,
                conversation_id=msg.conversation_id,
                user_id=msg.user_id,
                role=msg.role.value if hasattr(msg.role, "value") else str(msg.role),
                content=msg.content,
                sources=sources_list,
                created_at=msg.created_at,
            )
        )

    return ChatHistoryResponse(messages=formatted_messages)


@chat_router.delete(
    "/{conversation_id}/messages",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Clear conversation messages",
)
async def clear_messages(
    conversation_id: int,
    session: Session = Depends(get_session),
    user: Annotated[User, Depends(auth_dependency)] = None,
):
    _verify_conversation_ownership(conversation_id, user.id, session)

    messages = session.exec(
        select(Message).where(
            Message.conversation_id == conversation_id,
            Message.user_id == user.id,
        )
    ).all()

    for msg in messages:
        session.delete(msg)
    session.commit()

    return None
