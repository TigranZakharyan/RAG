import uvicorn
from core.settings import settings
from fastapi import FastAPI

app = FastAPI(title="RAG-AI", version="0.1.0")

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=settings.api_port, reload=True)