from pydantic import BaseModel

class FileCreate(BaseModel):
    conversation_id: int