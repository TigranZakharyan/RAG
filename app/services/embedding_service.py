from sentence_transformers import SentenceTransformer
from fastembed import SparseTextEmbedding

from core.settings import settings


class EmbeddingService:

    def __init__(self):
        # Dense semantic embedding
        self.dense_model = SentenceTransformer(
            settings.embedding_model
        )

        # Sparse BM25
        self.sparse_model = SparseTextEmbedding(
            model_name="Qdrant/bm25"
        )

    def embed_dense(
        self,
        texts: list[str],
    ) -> list[list[float]]:

        texts = [
            f"passage: {text}"
            for text in texts
        ]

        embeddings = self.dense_model.encode(
            texts,
            batch_size=32,
            normalize_embeddings=True,
            show_progress_bar=False,
        )

        return embeddings.tolist()

    def embed_sparse(
        self,
        texts: list[str],
    ):
        return list(
            self.sparse_model.embed(texts)
        )


embedding_service = EmbeddingService()