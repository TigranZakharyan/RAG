import asyncio
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile
from sqlmodel import Session

from core.database import engine
from core.minio import minio_client
from services.qdrant_service import qdrant_service
from core.settings import settings

from models.file import File
from models.ingestion import (
    IngestionJob,
    IngestionStatus,
)

from pipelines.file_processor import file_processor
from pipelines.chunking import chunk_markdown

from services.embedding_service import embedding_service


class IngestionService:

    def __init__(
        self,
        job_id: str,
    ):
        self.job_id = job_id

    # -----------------------------------------
    # Get job
    # -----------------------------------------

    def get_job(
        self,
        session: Session,
    ) -> IngestionJob | None:

        return session.get(
            IngestionJob,
            self.job_id,
        )

    # -----------------------------------------
    # Check cancellation
    # -----------------------------------------

    def is_cancelled(
        self,
        session: Session,
    ) -> bool:

        job = self.get_job(session)

        if not job:
            return True

        return job.status == IngestionStatus.CANCELLING

    # -----------------------------------------
    # Update progress
    # -----------------------------------------

    def update_progress(
        self,
        session: Session,
        *,
        progress: int,
        stage: str,
        processed_chunks: int | None = None,
        total_chunks: int | None = None,
    ):

        job = self.get_job(session)

        if not job:
            return

        job.progress = max(
            0,
            min(100, progress),
        )

        job.current_stage = stage

        if processed_chunks is not None:
            job.processed_chunks = processed_chunks

        if total_chunks is not None:
            job.total_chunks = total_chunks

        session.add(job)
        session.commit()

    # -----------------------------------------
    # Cancel + rollback
    # -----------------------------------------

    def cancel_and_rollback(
        self,
        session: Session,
    ):

        job = self.get_job(session)

        if not job:
            return

        qdrant_service.delete_ingestion(
            conversation_id=job.conversation_id,
            ingestion_id=job.id,
        )

        job.status = IngestionStatus.CANCELLED
        job.current_stage = "cancelled"
        job.progress = 0
        job.completed_at = datetime.now(timezone.utc)

        session.add(job)
        session.commit()

    # -----------------------------------------
    # Process document with FileProcessor
    # -----------------------------------------

    def process_document(
        self,
        temp_path: str,
        filename: str,
    ) -> str:

        async def _process() -> str:

            with open(
                temp_path,
                "rb",
            ) as file:

                upload_file = UploadFile(
                    file=file,
                    filename=filename,
                )

                try:
                    return await file_processor.process(
                        upload_file
                    )

                finally:
                    await upload_file.close()

        return asyncio.run(_process())

    # -----------------------------------------
    # Process
    # -----------------------------------------

    def process(self):

        temp_path: str | None = None

        with Session(engine) as session:

            job = self.get_job(session)

            if not job:
                return

            # ---------------------------------
            # Already in a terminal state
            # (stale/duplicate task delivery)
            # ---------------------------------

            if job.status in (
                IngestionStatus.COMPLETED,
                IngestionStatus.FAILED,
                IngestionStatus.CANCELLED,
            ):
                return

            # ---------------------------------
            # Already cancelled
            # ---------------------------------

            if job.status == IngestionStatus.CANCELLING:
                self.cancel_and_rollback(session)
                return

            # ---------------------------------
            # Start
            # ---------------------------------

            job.status = IngestionStatus.PROCESSING

            job.started_at = datetime.now(
                timezone.utc
            )

            job.current_stage = "starting"

            session.add(job)
            session.commit()

            try:

                # =============================
                # Get file
                # =============================

                db_file = session.get(
                    File,
                    job.file_id,
                )

                if not db_file:
                    raise RuntimeError(
                        "File not found"
                    )

                # =============================
                # Download from MinIO
                # =============================

                self.update_progress(
                    session,
                    progress=5,
                    stage="downloading",
                )

                if self.is_cancelled(session):
                    self.cancel_and_rollback(session)
                    return

                response = minio_client.get_object(
                    settings.minio_bucket,
                    db_file.path,
                )

                suffix = Path(
                    db_file.original_filename or ""
                ).suffix

                temp_file = tempfile.NamedTemporaryFile(
                    mode="wb",
                    delete=False,
                    suffix=suffix,
                )

                temp_path = temp_file.name

                try:

                    for data in response.stream(
                        1024 * 1024
                    ):
                        temp_file.write(data)

                finally:

                    response.close()
                    response.release_conn()
                    temp_file.close()

                # =============================
                # Process document
                # =============================

                self.update_progress(
                    session,
                    progress=15,
                    stage="processing_document",
                )

                if self.is_cancelled(session):
                    self.cancel_and_rollback(session)
                    return

                markdown = self.process_document(
                    temp_path=temp_path,
                    filename=db_file.original_filename,
                )

                # =============================
                # Chunk
                #
                # chunk_markdown() returns:
                #   {"summary": str, "parents": List[ParentChunk]}
                # Each ParentChunk has .children: List[ChildChunk].
                # Neither dataclass has a "chunk_type" field, so we
                # flatten explicitly instead of filtering on it.
                # =============================

                self.update_progress(
                    session,
                    progress=30,
                    stage="chunking",
                )

                if self.is_cancelled(session):
                    self.cancel_and_rollback(session)
                    return

                chunk_result = chunk_markdown(
                    markdown
                )

                parent_chunks = chunk_result["parents"]

                parents = {
                    parent.id: parent
                    for parent in parent_chunks
                }

                children = [
                    child
                    for parent in parent_chunks
                    for child in parent.children
                ]

                if not children:
                    raise RuntimeError(
                        "No chunks generated"
                    )

                total = len(children)

                job.total_chunks = total

                session.add(job)
                session.commit()

                # =============================
                # Qdrant collection
                # =============================

                collection_name = (
                    qdrant_service
                    .get_or_create_collection(
                        job.conversation_id
                    )
                )

                # =============================
                # Embedding
                # =============================

                batch_size = 32

                for start in range(
                    0,
                    total,
                    batch_size,
                ):

                    # -------------------------
                    # Check cancellation
                    # -------------------------

                    if self.is_cancelled(
                        session
                    ):
                        self.cancel_and_rollback(
                            session
                        )
                        return

                    batch = children[
                        start:start + batch_size
                    ]

                    # Embed using embedding_text (summary-prefixed)
                    # for better retrieval quality.
                    texts = [
                        child.embedding_text
                        for child in batch
                    ]

                    self.update_progress(
                        session,
                        progress=35 + int(
                            (start / total) * 55
                        ),
                        stage="embedding",
                        processed_chunks=start,
                        total_chunks=total,
                    )

                    dense_embeddings, sparse_embeddings = (
                        embedding_service
                        .embed(texts)
                    )

                    # =========================
                    # Build Qdrant points
                    # =========================

                    from qdrant_client import models

                    points = []

                    for child, dense_emb, sparse_emb in zip(
                        batch,
                        dense_embeddings,
                        sparse_embeddings,
                    ):

                        parent = parents.get(
                            child.parent_id
                        )

                        # Convert FastEmbed sparse output to Qdrant SparseVector model
                        sparse_vector = models.SparseVector(
                            indices=sparse_emb.indices.tolist(),
                            values=sparse_emb.values.tolist(),
                        )

                        points.append(
                            models.PointStruct(
                                id=str(uuid4()),
                                # Pass vectors as a dictionary for hybrid collections
                                vector={
                                    "dense": dense_emb,
                                    "sparse": sparse_vector,
                                },
                                payload={
                                    # Ownership
                                    "user_id": job.user_id,

                                    # Relations
                                    "conversation_id":
                                        job.conversation_id,

                                    "file_id":
                                        job.file_id,

                                    "ingestion_id":
                                        job.id,

                                    # Chunk
                                    "chunk_id":
                                        child.id,

                                    "parent_id":
                                        child.parent_id,

                                    # Content
                                    "content":
                                        child.text,

                                    "parent_content": (
                                        parent.text
                                        if parent
                                        else None
                                    ),

                                    "chunk_type":
                                        "child",

                                    "token_count":
                                        child.tokens,

                                    "metadata": {
                                        "heading_path":
                                            child.heading_path,
                                        "index_in_parent":
                                            child.index_in_parent,
                                        "doc_summary":
                                            chunk_result["summary"],
                                    },
                                },
                            )
                        )
                        
                    # =========================
                    # Upload
                    # =========================

                    qdrant_service.client.upsert(
                        collection_name=collection_name,
                        points=points,
                        wait=True
                    )

                    processed = min(
                        start + len(batch),
                        total,
                    )

                    progress = (
                        35
                        + int(
                            (processed / total) * 60
                        )
                    )

                    self.update_progress(
                        session,
                        progress=progress,
                        stage="indexing",
                        processed_chunks=processed,
                        total_chunks=total,
                    )

                # =============================
                # Final cancellation check
                # =============================

                if self.is_cancelled(session):
                    self.cancel_and_rollback(
                        session
                    )
                    return

                # =============================
                # Completed
                # =============================

                job.status = (
                    IngestionStatus.COMPLETED
                )

                job.progress = 100
                job.current_stage = "completed"
                job.processed_chunks = total
                job.completed_at = (
                    datetime.now(timezone.utc)
                )

                session.add(job)
                session.commit()

            except Exception as e:

                session.rollback()

                print(
                    f"INGESTION ERROR "
                    f"{self.job_id}: {e}"
                )

                # -----------------------------
                # Rollback Qdrant
                # -----------------------------

                try:
                    qdrant_service.delete_ingestion(
                        conversation_id=job.conversation_id,
                        ingestion_id=job.id,
                    )
                except Exception as rollback_error:
                    print(
                        f"QDRANT ROLLBACK ERROR "
                        f"{self.job_id}: "
                        f"{rollback_error}"
                    )

                # -----------------------------
                # Mark failed
                # -----------------------------

                job = self.get_job(session)

                if job:

                    job.status = (
                        IngestionStatus.FAILED
                    )

                    job.current_stage = "failed"

                    job.error = str(e)

                    job.completed_at = (
                        datetime.now(timezone.utc)
                    )

                    session.add(job)
                    session.commit()

                # -----------------------------
                # Let Celery see the failure
                # -----------------------------

                raise

            finally:

                if temp_path:

                    try:
                        os.unlink(temp_path)
                    except FileNotFoundError:
                        pass
                    except Exception as cleanup_error:
                        print(
                            f"TEMP FILE CLEANUP ERROR "
                            f"{self.job_id}: "
                            f"{cleanup_error}"
                        )