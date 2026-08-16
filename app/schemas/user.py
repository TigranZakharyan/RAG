from pydantic import BaseModel

class MeResponse(BaseModel):
    id: int
    username: str