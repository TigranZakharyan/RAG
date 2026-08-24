import json
import logging
from typing import AsyncGenerator
from sqlmodel import Session, select

from core.database import engine
from models.message import Message, MessageRole
from schemas.chat import ChatRequest, ChunkSource
from services.ollama_service import ollama_service
from services.prompt_service import prompt_service
from services.retrieval_service import retrieval_service

logger = logging.getLogger(__name__)


class ChatService:
    def get_conversation_history(
        self,
        session: Session,
        conversation_id: int,
        user_id: int,
        limit: int = 20,
    ) -> list[Message]:
        """
        Fetches chronologically ordered conversation messages for context memory.
        """
        return list(
            session.exec(
                select(Message)
                .where(
                    Message.conversation_id == conversation_id,
                    Message.user_id == user_id,
                )
                .order_by(Message.created_at.asc())
                .limit(limit)
            ).all()
        )

    def save_message(
        self,
        session: Session,
        conversation_id: int,
        user_id: int,
        role: MessageRole,
        content: str,
        sources: list[ChunkSource] | None = None,
    ) -> Message:
        """
        Persists a user or assistant message to Postgres with optional JSON sources.
        """
        sources_json = (
            json.dumps([s.model_dump() for s in sources]) if sources else None
        )

        message = Message(
            conversation_id=conversation_id,
            user_id=user_id,
            role=role,
            content=content,
            sources=sources_json,
        )
        session.add(message)
        session.commit()
        session.refresh(message)
        return message

    async def stream_rag_chat(
        self,
        conversation_id: int,
        user_id: int,
        chat_request: ChatRequest,
    ) -> AsyncGenerator[str, None]:
        """
        Main RAG streaming pipeline:
        1. Hybrid retrieval from Qdrant
        2. Format prompt with history & context
        3. Emit retrieved sources as first SSE metadata event
        4. Stream generated tokens in real-time as SSE data events
        5. Persist User query & Complete Assistant Response to database
        """
        # Step 1: Hybrid Retrieval
        sources = retrieval_service.retrieve_context(
            conversation_id=conversation_id,
            user_id=user_id,
            query=chat_request.message,
            top_k=chat_request.top_k,
            score_threshold=chat_request.score_threshold,
        )

        # Step 2: Fetch history & build prompt
        with Session(engine) as session:
            history = self.get_conversation_history(
                session=session,
                conversation_id=conversation_id,
                user_id=user_id,
            )

        messages = prompt_service.build_chat_messages(
            query=chat_request.message,
            sources=sources,
            history=history,
        )

        # Step 3: Emit source metadata first to client
        sources_event = {
            "event": "sources",
            "sources": [s.model_dump() for s in sources],
        }
        yield f"event: sources\ndata: {json.dumps(sources_event)}\n\n"

        # Step 4: Stream tokens from Ollama
        assistant_content_chunks: list[str] = []

        async for token in ollama_service.stream_chat(
            messages=messages,
            model=chat_request.model,
            temperature=chat_request.temperature,
        ):
            assistant_content_chunks.append(token)
            token_payload = {"token": token}
            yield f"event: token\ndata: {json.dumps(token_payload)}\n\n"

        full_assistant_reply = "".join(assistant_content_chunks).strip()

        # Step 5: Persist both user and assistant messages in Postgres
        with Session(engine) as session:
            # Save user question
            self.save_message(
                session=session,
                conversation_id=conversation_id,
                user_id=user_id,
                role=MessageRole.USER,
                content=chat_request.message,
            )

            # Save assistant reply with sources
            assistant_msg = self.save_message(
                session=session,
                conversation_id=conversation_id,
                user_id=user_id,
                role=MessageRole.ASSISTANT,
                content=full_assistant_reply,
                sources=sources,
            )

            done_event = {
                "event": "done",
                "message_id": assistant_msg.id,
                "conversation_id": conversation_id,
            }
            yield f"event: done\ndata: {json.dumps(done_event)}\n\n"

    def process_rag_chat_sync(
        self,
        conversation_id: int,
        user_id: int,
        message_text: str,
        top_k: int = 5,
        score_threshold: float = 0.3,
        model: str | None = None,
        temperature: float | None = None,
    ) -> Message:
        """
        Synchronous RAG chat flow used by Celery background worker tasks.
        """
        with Session(engine) as session:
            # 1. Retrieve context
            sources = retrieval_service.retrieve_context(
                conversation_id=conversation_id,
                user_id=user_id,
                query=message_text,
                top_k=top_k,
                score_threshold=score_threshold,
            )

            # 2. Get history & format prompt
            history = self.get_conversation_history(
                session=session,
                conversation_id=conversation_id,
                user_id=user_id,
            )

            messages = prompt_service.build_chat_messages(
                query=message_text,
                sources=sources,
                history=history,
            )

            # 3. Save user message
            self.save_message(
                session=session,
                conversation_id=conversation_id,
                user_id=user_id,
                role=MessageRole.USER,
                content=message_text,
            )

            # 4. Generate response via Ollama
            reply = ollama_service.generate(
                messages=messages,
                model=model,
                temperature=temperature,
            )

            # 5. Save assistant reply
            assistant_msg = self.save_message(
                session=session,
                conversation_id=conversation_id,
                user_id=user_id,
                role=MessageRole.ASSISTANT,
                content=reply,
                sources=sources,
            )

            return assistant_msg


chat_service = ChatService()
