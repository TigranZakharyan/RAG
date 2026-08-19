from qdrant_client import QdrantClient, models

from services.embedding_service import embedding_service
from core.qdrant import qdrant_client


class QdrantService:

    def get_collection_name(
        self,
        conversation_id: int,
    ) -> str:
        return f"conversation_{conversation_id}"

    def get_or_create_collection(
        self,
        conversation_id: int,
    ) -> str:

        collection_name = self.get_collection_name(
            conversation_id
        )

        if qdrant_client.collection_exists(
            collection_name
        ):
            return collection_name

        dense_size = (
            embedding_service.dense_model
            .get_sentence_embedding_dimension()
        )

        qdrant_client.create_collection(
            collection_name=collection_name,

            vectors_config={
                "dense": models.VectorParams(
                    size=dense_size,
                    distance=models.Distance.COSINE,
                ),
            },

            sparse_vectors_config={
                "sparse": models.SparseVectorParams(
                    modifier=models.Modifier.IDF,
                ),
            },
        )

        # Payload indexes

        qdrant_client.create_payload_index(
            collection_name=collection_name,
            field_name="file_id",
            field_schema=models.PayloadSchemaType.INTEGER,
        )

        qdrant_client.create_payload_index(
            collection_name=collection_name,
            field_name="chunk_id",
            field_schema=models.PayloadSchemaType.KEYWORD,
        )

        qdrant_client.create_payload_index(
            collection_name=collection_name,
            field_name="parent_id",
            field_schema=models.PayloadSchemaType.KEYWORD,
        )

        return collection_name


qdrant_service = QdrantService()