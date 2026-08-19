from qdrant_client import QdrantClient, models

from core.settings import settings


class QdrantService:

    def __init__(self):
        self.client = QdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_service_api_key or None,
        )

    def collection_name(
        self,
        conversation_id: int,
    ) -> str:
        return f"conversation_{conversation_id}"

    def get_or_create_collection(
        self,
        conversation_id: int,
    ):
        collection_name = self.collection_name(
            conversation_id
        )

        collections = self.client.get_collections()

        exists = any(
            collection.name == collection_name
            for collection in collections.collections
        )

        if not exists:
            self.client.create_collection(
                collection_name=collection_name,
                vectors_config=models.VectorParams(
                    size=1024,  # change to your embedding dimension
                    distance=models.Distance.COSINE,
                ),
            )

        return collection_name

    def delete_ingestion(
        self,
        conversation_id: int,
        ingestion_id: str,
    ):
        collection_name = self.collection_name(
            conversation_id
        )

        try:
            self.client.delete(
                collection_name=collection_name,
                points_selector=models.FilterSelector(
                    filter=models.Filter(
                        must=[
                            models.FieldCondition(
                                key="ingestion_id",
                                match=models.MatchValue(
                                    value=ingestion_id
                                ),
                            )
                        ]
                    )
                ),
            )
        except Exception:
            # Collection may not exist yet.
            pass


qdrant_service = QdrantService()