from sqlmodel import SQLModel, Field

class File(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    conversation_id: int = Field(foreign_key="conversation.id")
    path: str
    filename: str
    original_filename: str
    size: int