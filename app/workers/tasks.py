from core.celery import celery_app
from services.ingestion_service import IngestionService


@celery_app.task(
    bind=True,
    name="process_ingestion",
)
def process_ingestion(self, job_id: str):
    IngestionService(job_id).process()