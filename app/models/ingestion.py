from datetime import datetime, timezone
from enum import Enum

from sqlmodel import SQLModel, Field


class IngestionStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    CANCELLING = "cancelling"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    FAILED = "failed"


class IngestionJob(SQLModel, table=True):
    __tablename__ = "ingestion_jobs"

    id: str = Field(primary_key=True)

    user_id: int = Field(
        foreign_key="user.id",
        index=True,
    )

    conversation_id: int = Field(
        foreign_key="conversation.id",
        index=True,
    )

    file_id: int = Field(
        foreign_key="file.id",
        index=True,
    )

    status: IngestionStatus = Field(
        default=IngestionStatus.QUEUED,
        index=True,
    )

    progress: int = Field(
        default=0,
    )

    current_stage: str | None = None

    total_chunks: int = 0

    processed_chunks: int = 0

    error: str | None = None

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    started_at: datetime | None = None

    completed_at: datetime | None = None