import os
import uuid
from pathlib import Path
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File as FastAPIFile,
    HTTPException,
    UploadFile,
    status,
)
from sqlmodel import Session, select

from core.celery import celery_app
from core.minio import minio_client
from core.settings import settings

from core.database import get_session

from dependencies import auth_dependency

from models.conversation import Conversation
from models.file import File as FileModel
from models.ingestion import (
    IngestionJob,
    IngestionStatus,
)
from models.user import User

from workers.tasks import process_ingestion


file_router = APIRouter(
    prefix="/files",
    tags=["files"],
)


# =====================================================
# UPLOAD
# =====================================================

@file_router.post(
    "/{conversation_id}",
    status_code=status.HTTP_201_CREATED,
)
async def upload_file(
    conversation_id: int,
    file: Annotated[
        UploadFile,
        FastAPIFile(...),
    ],
    session: Session = Depends(get_session),
    user: Annotated[
        User,
        Depends(auth_dependency),
    ] = None,
):

    # -----------------------------------------------
    # Check conversation ownership
    # -----------------------------------------------

    conversation = session.exec(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == user.id,
        )
    ).first()

    if conversation is None:
        raise HTTPException(
            status_code=404,
            detail="Conversation not found",
        )

    # -----------------------------------------------
    # Filename
    # -----------------------------------------------

    extension = Path(
        file.filename or ""
    ).suffix

    filename = (
        f"{uuid.uuid4()}{extension}"
    )

    object_name = (
        f"conversations/"
        f"{conversation_id}/"
        f"{filename}"
    )

    # -----------------------------------------------
    # Size
    # -----------------------------------------------

    file.file.seek(0, os.SEEK_END)
    file_size = file.file.tell()
    file.file.seek(0)

    # -----------------------------------------------
    # MinIO
    # -----------------------------------------------

    try:
        minio_client.put_object(
            bucket_name=settings.minio_bucket,
            object_name=object_name,
            data=file.file,
            length=file_size,
            content_type=(
                file.content_type
                or "application/octet-stream"
            ),
        )

    except Exception as e:
        print(
            f"MINIO ERROR: {e}"
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to upload file",
        )

    # -----------------------------------------------
    # Database file
    # -----------------------------------------------

    db_file = FileModel(
        conversation_id=conversation_id,
        path=object_name,
        filename=filename,
        original_filename=(
            file.filename
            or filename
        ),
        size=file_size,
    )

    print(222, db_file)

    print("BEFORE:", db_file.model_dump())

    session.add(db_file)
    session.commit()

    # -----------------------------------------------
    # Create ingestion job
    # -----------------------------------------------

    job = IngestionJob(
        id=str(uuid.uuid4()),
        user_id=user.id,
        conversation_id=conversation_id,
        file_id=db_file.id,
        status=IngestionStatus.QUEUED,
        progress=0,
        current_stage="queued",
    )

    session.add(job)
    session.commit()

    session.refresh(job)
    session.refresh(db_file)

    # -----------------------------------------------
    # Queue Celery
    # -----------------------------------------------
    process_ingestion.apply_async(
        args=[job.id],
        task_id=job.id,
    )

    print(111, db_file)

    return {
        "file": db_file.model_dump(),
        "ingestion": {
            "id": job.id,
            "status": job.status,
            "progress": job.progress,
        },
    }


# =====================================================
# GET INGESTION STATUS
# =====================================================

@file_router.get(
    "/{file_id}/ingestion",
)
async def get_ingestion_status(
    file_id: int,

    session: Session = Depends(
        get_session
    ),

    user: Annotated[
        User,
        Depends(auth_dependency),
    ] = None,
):

    job = session.exec(
        select(IngestionJob)
        .where(
            IngestionJob.file_id == file_id,
            IngestionJob.user_id == user.id,
        )
        .order_by(
            IngestionJob.created_at.desc()
        )
    ).first()

    if job is None:
        raise HTTPException(
            status_code=404,
            detail="Ingestion not found",
        )

    return {
        "id": job.id,
        "file_id": job.file_id,
        "conversation_id":
            job.conversation_id,
        "status": job.status,
        "progress":
            job.progress,
        "stage":
            job.current_stage,
        "processed_chunks":
            job.processed_chunks,
        "total_chunks":
            job.total_chunks,
        "error":
            job.error,
        "created_at":
            job.created_at,
        "started_at":
            job.started_at,
        "completed_at":
            job.completed_at,
    }


# =====================================================
# CANCEL INGESTION
# =====================================================

@file_router.post(
    "/{file_id}/ingestion/cancel",
)
async def cancel_ingestion(
    file_id: int,

    session: Session = Depends(
        get_session
    ),

    user: Annotated[
        User,
        Depends(auth_dependency),
    ] = None,
):

    job = session.exec(
        select(IngestionJob)
        .where(
            IngestionJob.file_id == file_id,
            IngestionJob.user_id == user.id,
        )
        .order_by(
            IngestionJob.created_at.desc()
        )
    ).first()

    if job is None:

        raise HTTPException(
            status_code=404,
            detail="Ingestion not found",
        )

    if job.status in (
        IngestionStatus.COMPLETED,
        IngestionStatus.FAILED,
        IngestionStatus.CANCELLED,
    ):

        raise HTTPException(
            status_code=400,
            detail=(
                f"Cannot cancel ingestion "
                f"with status '{job.status}'"
            ),
        )

    # -----------------------------------------------
    # Mark cancellation requested
    # -----------------------------------------------

    job.status = (
        IngestionStatus.CANCELLING
    )

    job.current_stage = (
        "cancellation_requested"
    )

    session.add(job)
    session.commit()

    return {
        "id": job.id,
        "status": job.status,
    }


# =====================================================
# GET FILE
# =====================================================

@file_router.get(
    "/{file_id}",
)
async def get_file(
    file_id: int,

    session: Session = Depends(
        get_session
    ),

    user: Annotated[
        User,
        Depends(auth_dependency),
    ] = None,
):

    file = session.exec(
        select(FileModel)
        .join(
            Conversation,
            Conversation.id
            == FileModel.conversation_id,
        )
        .where(
            FileModel.id == file_id,
            Conversation.user_id == user.id,
        )
    ).first()

    if file is None:

        raise HTTPException(
            status_code=404,
            detail="File not found",
        )

    return file


# =====================================================
# GET FILES BY CONVERSATION
# =====================================================

@file_router.get(
    "/conversation/{conversation_id}",
)
async def get_conversation_files(
    conversation_id: int,

    session: Session = Depends(
        get_session
    ),

    user: Annotated[
        User,
        Depends(auth_dependency),
    ] = None,
):

    # -----------------------------------------------
    # Check ownership
    # -----------------------------------------------

    conversation = session.exec(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == user.id,
        )
    ).first()

    if conversation is None:

        raise HTTPException(
            status_code=404,
            detail="Conversation not found",
        )

    files = session.exec(
        select(FileModel)
        .where(
            FileModel.conversation_id
            == conversation_id
        )
    ).all()

    return {
        "files": files,
    }


# =====================================================
# DELETE FILE
# =====================================================

@file_router.delete(
    "/{file_id}",
)
async def delete_file(
    file_id: int,

    session: Session = Depends(
        get_session
    ),

    user: Annotated[
        User,
        Depends(auth_dependency),
    ] = None,
):

    file = session.exec(
        select(FileModel)
        .join(
            Conversation,
            Conversation.id
            == FileModel.conversation_id,
        )
        .where(
            FileModel.id == file_id,
            Conversation.user_id == user.id,
        )
    ).first()

    if file is None:

        raise HTTPException(
            status_code=404,
            detail="File not found",
        )

    # -----------------------------------------------
    # Find running ingestion
    # -----------------------------------------------

    jobs = session.exec(
        select(IngestionJob)
        .where(
            IngestionJob.file_id == file_id,
            IngestionJob.user_id == user.id,
        )
    ).all()

    for job in jobs:

        if job.status in (
            IngestionStatus.QUEUED,
            IngestionStatus.PROCESSING,
            IngestionStatus.CANCELLING,
        ):

            job.status = (
                IngestionStatus.CANCELLING
            )

            session.add(job)

    session.commit()

    # -----------------------------------------------
    # Delete Qdrant data
    # -----------------------------------------------

    from core.qdrant import qdrant_service

    for job in jobs:

        qdrant_service.delete_ingestion(
            conversation_id=
                job.conversation_id,

            ingestion_id=
                job.id,
        )

    # -----------------------------------------------
    # Delete MinIO object
    # -----------------------------------------------

    try:

        minio_client.remove_object(
            settings.minio_bucket,
            file.path,
        )

    except Exception as e:

        print(
            f"MINIO DELETE ERROR: {e}"
        )

    # -----------------------------------------------
    # Delete DB
    # -----------------------------------------------

    session.delete(file)

    session.commit()

    return {
        "message": "File deleted successfully",
    }