from sentence_transformers import SentenceTransformer
from fastembed import SparseTextEmbedding

from core.settings import settings


class EmbeddingService:
    def __init__(self):
        # Dense semantic embedding
        self.dense_model = SentenceTransformer(
            settings.embedding_model
        )

        # Sparse BM25 embedding
        self.sparse_model = SparseTextEmbedding(
            model_name="Qdrant/bm25"
        )

    # -----------------------------------------
    # Dense embeddings
    # -----------------------------------------

    def embed_dense(
        self,
        texts: list[str],
    ) -> list[list[float]]:

        passages = [
            f"passage: {text}"
            for text in texts
        ]

        embeddings = self.dense_model.encode(
            passages,
            batch_size=32,
            normalize_embeddings=True,
            show_progress_bar=False,
        )

        return embeddings.tolist()

    # -----------------------------------------
    # Sparse embeddings
    # -----------------------------------------

    def embed_sparse(
        self,
        texts: list[str],
    ):
        return list(
            self.sparse_model.embed(texts)
        )

    # -----------------------------------------
    # Dense + Sparse
    # -----------------------------------------

    def embed(
        self,
        texts: list[str],
    ):
        dense_embeddings = self.embed_dense(
            texts
        )

        sparse_embeddings = self.embed_sparse(
            texts
        )

        return (
            dense_embeddings,
            sparse_embeddings,
        )


embedding_service = EmbeddingService()