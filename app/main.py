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
from routers.chat import chat_router

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="RAG-AI", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def on_startup():
    ensure_bucket()
    SQLModel.metadata.create_all(engine)

app.include_router(auth_router)
app.include_router(user_router)
app.include_router(conversation_router)
app.include_router(file_router)
app.include_router(chat_router)




if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=settings.api_port, reload=True)