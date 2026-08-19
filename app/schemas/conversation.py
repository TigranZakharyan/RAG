from datetime import datetime

from pydantic import BaseModel


class ConversationCreate(BaseModel):
    title: str


class ConversationUpdate(BaseModel):
    title: str | None = None


class ConversationResponse(BaseModel):
    id: int
    user_id: int
    title: str
    created_at: datetime
    updated_at: datetime


class ConversationListResponse(BaseModel):
    conversations: list[ConversationResponse]