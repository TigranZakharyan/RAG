from core.celery import celery_app
from services.ingestion_service import IngestionService
from services.chat_service import chat_service


@celery_app.task(
    bind=True,
    name="process_ingestion",
)
def process_ingestion(self, job_id: str):
    IngestionService(job_id).process()


@celery_app.task(
    bind=True,
    name="process_chat_message",
)
def process_chat_message(
    self,
    conversation_id: int,
    user_id: int,
    message_text: str,
    top_k: int = 5,
    score_threshold: float = 0.3,
    model: str | None = None,
    temperature: float | None = None,
):
    msg = chat_service.process_rag_chat_sync(
        conversation_id=conversation_id,
        user_id=user_id,
        message_text=message_text,
        top_k=top_k,
        score_threshold=score_threshold,
        model=model,
        temperature=temperature,
    )
    return {"message_id": msg.id, "conversation_id": conversation_id}