import logging
from typing import Any
from qdrant_client import models

from core.qdrant import qdrant_client
from schemas.chat import ChunkSource
from services.embedding_service import embedding_service
from services.qdrant_service import qdrant_service

logger = logging.getLogger(__name__)


class RetrievalService:
    def __init__(self):
        self.client = qdrant_client

    def retrieve_context(
        self,
        conversation_id: int,
        user_id: int,
        query: str,
        top_k: int = 5,
        score_threshold: float = 0.3,
    ) -> list[ChunkSource]:
        """
        Hybrid retrieval combining Dense semantic embedding and BM25 Sparse representation
        using Qdrant's Reciprocal Rank Fusion (RRF) across conversation vector points.
        """
        collection_name = qdrant_service.collection_name(conversation_id)

        try:
            # Check if collection exists
            collections = self.client.get_collections()
            exists = any(c.name == collection_name for c in collections.collections)
            if not exists:
                logger.info("Qdrant collection %s does not exist yet.", collection_name)
                return []

            # 1. Embed query with query prefix for dense embedding and sparse BM25
            dense_query = embedding_service.dense_model.encode(
                f"query: {query}",
                normalize_embeddings=True,
                show_progress_bar=False,
            ).tolist()

            sparse_raw = list(embedding_service.sparse_model.embed([query]))[0]
            sparse_query = models.SparseVector(
                indices=sparse_raw.indices.tolist(),
                values=sparse_raw.values.tolist(),
            )

            # Security filter: ensure points belong to the conversation & user
            query_filter = models.Filter(
                must=[
                    models.FieldCondition(
                        key="user_id",
                        match=models.MatchValue(value=user_id),
                    ),
                    models.FieldCondition(
                        key="conversation_id",
                        match=models.MatchValue(value=conversation_id),
                    ),
                ]
            )

            # Hybrid query using Prefetch with Dense and Sparse, fused via RRF
            response = self.client.query_points(
                collection_name=collection_name,
                prefetch=[
                    models.Prefetch(
                        query=dense_query,
                        using="dense",
                        filter=query_filter,
                        limit=top_k * 3,
                    ),
                    models.Prefetch(
                        query=sparse_query,
                        using="sparse",
                        filter=query_filter,
                        limit=top_k * 3,
                    ),
                ],
                query=models.FusionQuery(fusion=models.Fusion.RRF),
                limit=top_k * 2,
            )

            points = response.points if hasattr(response, "points") else []

            # Deduplicate by parent_id / chunk_id and filter by threshold
            seen_parent_ids = set()
            sources: list[ChunkSource] = []

            for point in points:
                payload = point.payload or {}
                parent_id = payload.get("parent_id")
                score = float(point.score) if point.score is not None else 0.0

                # In RRF, scores are typically 1 / (60 + rank), but if raw cosine is used or fused,
                # we preserve best matching chunks.
                # If we've already seen this parent, we can skip or keep if distinct enough
                if parent_id and parent_id in seen_parent_ids:
                    continue

                if parent_id:
                    seen_parent_ids.add(parent_id)

                sources.append(
                    ChunkSource(
                        chunk_id=payload.get("chunk_id"),
                        parent_id=parent_id,
                        file_id=payload.get("file_id"),
                        filename=payload.get("filename"),
                        heading_path=payload.get("heading_path"),
                        content=payload.get("content", ""),
                        parent_content=payload.get("parent_content"),
                        score=round(score, 4),
                    )
                )

                if len(sources) >= top_k:
                    break

            return sources

        except Exception as e:
            logger.error("Error retrieving context from Qdrant: %s", str(e), exc_info=True)
            return []


retrieval_service = RetrievalService()
