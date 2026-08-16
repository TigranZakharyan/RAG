import uvicorn
from core.settings import settings
from fastapi import FastAPI
from sqlmodel import SQLModel
from db.database import get_session, engine
from routers.auth import auth_router
from routers.user import user_router

app = FastAPI(title="RAG-AI", version="0.1.0")

@app.on_event("startup")
def on_startup():
    SQLModel.metadata.create_all(engine)

app.include_router(auth_router)
app.include_router(user_router)

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=settings.api_port, reload=True)