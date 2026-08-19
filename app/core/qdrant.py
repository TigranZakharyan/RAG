from qdrant_client import QdrantClient
from core.settings import settings

qdrant_client = QdrantClient(
    url=settings.qdrant_url,
    api_key=settings.qdrant_service_api_key or None,
)