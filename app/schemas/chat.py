from datetime import datetime
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(
        ...,
        min_length=1,
        description="The query / prompt message from the user",
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Number of relevant chunks to retrieve",
    )
    score_threshold: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="Minimum similarity score threshold",
    )
    temperature: float | None = Field(
        default=None,
        ge=0.0,
        le=2.0,
        description="Optional temperature override for Ollama generation",
    )
    model: str | None = Field(
        default=None,
        description="Optional Ollama model override (e.g. llama3.2)",
    )


class ChunkSource(BaseModel):
    chunk_id: str | None = None
    parent_id: str | None = None
    file_id: int | None = None
    filename: str | None = None
    heading_path: str | None = None
    content: str
    parent_content: str | None = None
    score: float


class MessageResponse(BaseModel):
    id: int
    conversation_id: int
    user_id: int
    role: str
    content: str
    sources: list[ChunkSource] | None = None
    created_at: datetime


class ChatHistoryResponse(BaseModel):
    messages: list[MessageResponse]


class AsyncChatResponse(BaseModel):
    task_id: str
    status: str
    conversation_id: int
