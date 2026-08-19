import uvicorn
from core.settings import settings
from core.minio import ensure_bucket

from fastapi import FastAPI
from sqlmodel import SQLModel
from core.database import get_session, engine

from routers.auth import auth_router
from routers.user import user_router
from routers.conversation import conversation_router
from routers.file import file_router

app = FastAPI(title="RAG-AI", version="0.1.0")

@app.on_event("startup")
def on_startup():
    ensure_bucket()
    SQLModel.metadata.create_all(engine)

app.include_router(auth_router)
app.include_router(user_router)
app.include_router(conversation_router)
app.include_router(file_router)


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=settings.api_port, reload=True)