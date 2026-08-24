from datetime import datetime, timezone
from enum import Enum
from sqlmodel import SQLModel, Field


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class Message(SQLModel, table=True):
    __tablename__ = "messages"

    id: int | None = Field(default=None, primary_key=True)
    conversation_id: int = Field(
        foreign_key="conversation.id",
        index=True,
        nullable=False,
    )
    user_id: int = Field(
        foreign_key="user.id",
        index=True,
        nullable=False,
    )
    role: MessageRole = Field(
        default=MessageRole.USER,
        nullable=False,
    )
    content: str = Field(
        nullable=False,
    )
    sources: str | None = Field(
        default=None,
        nullable=True,
        description="JSON serialized list of retrieved chunk sources/citations",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
