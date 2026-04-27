"""Upload router: accept files, store to MinIO, enqueue ingestion."""
from __future__ import annotations

import logging

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Response,
    UploadFile,
    status,
)
from sqlalchemy import select

from app.core.rbac import DB, CurrentUser, CurrentWorkspace, require_role
from app.ingestion.parsers import guess_mime
from app.models.db import AuditLog, Document, Folder, Role
from app.models.schemas import DocumentOut

router = APIRouter(prefix="/api/upload", tags=["upload"])

logger = logging.getLogger(__name__)

MAX_FILE_BYTES = 100 * 1024 * 1024  # 100 MB default cap per file


async def _run_pipeline(
    *,
    workspace_id: str,
    folder_id: str | None,
    document_id: str,
    filename: str,
    mime: str,
    storage_key: str,
    data: bytes,
    model_prefs: dict,
) -> None:
    """Background task runner — opens its own DB session."""
    from app.core.db import SessionLocal
    from app.ingestion.pipeline import ingest_bytes

    async with SessionLocal() as db:
        try:
            await ingest_bytes(
                db=db,
                workspace_id=workspace_id,
                folder_id=folder_id,
                document_id=document_id,
                filename=filename,
                mime=mime,
                data=data,
                storage_key=storage_key,
                model_prefs=model_prefs,
            )
        except Exception:
            logger.exception("background ingestion failed for document %s", document_id)


@router.post(
    "",
    response_model=DocumentOut,
    status_code=201,
    dependencies=[Depends(require_role(Role.WORKSPACE_ADMIN.value, Role.WORKSPACE_EDITOR.value))],
)
async def upload_document(
    background: BackgroundTasks,
    ctx: CurrentWorkspace,
    user: CurrentUser,
    db: DB,
    file: UploadFile = File(...),
    folder_id: str | None = Form(default=None),
    skip_pipeline: bool = Form(default=False),
) -> Document:
    ws, _ = ctx

    data = await file.read()
    size = len(data)
    if size == 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "empty file")
    if size > MAX_FILE_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "file too large")
    if ws.used_bytes + size > ws.quota_bytes:
        raise HTTPException(status.HTTP_402_PAYMENT_REQUIRED, "workspace quota exceeded")

    # Validate folder ownership.
    folder: Folder | None = None
    if folder_id:
        folder = (
            await db.execute(
                select(Folder).where(Folder.id == folder_id, Folder.workspace_id == ws.id)
            )
        ).scalar_one_or_none()
        if not folder:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "folder not found")

    mime = guess_mime(file.filename or "file", file.content_type)
    filename = file.filename or "upload"

    doc = Document(
        workspace_id=ws.id,
        folder_id=folder.id if folder else None,
        filename=filename,
        mime_type=mime,
        size_bytes=size,
        storage_key="",
        status="pending",
    )
    db.add(doc)
    await db.flush()

    # Build storage key once doc.id is known.
    storage_key = f"{ws.id}/{doc.id}/{filename}"
    doc.storage_key = storage_key

    # Attempt MinIO upload; treat storage outage as a 503 rather than partial state.
    try:
        from app.services.minio import ensure_bucket, put_object

        await ensure_bucket()
        await put_object(storage_key, data, size=size, content_type=mime)
    except Exception as e:
        logger.warning("MinIO unavailable, storing metadata only: %s", e)
        doc.doc_metadata = {**(doc.doc_metadata or {}), "storage_error": str(e)[:200]}

    ws.used_bytes += size
    db.add(
        AuditLog(
            workspace_id=ws.id,
            user_id=user.id,
            action="document.upload",
            target_type="document",
            target_id=doc.id,
            payload={"filename": filename, "size": size, "mime": mime},
        )
    )
    await db.commit()
    await db.refresh(doc)

    if not skip_pipeline:
        background.add_task(
            _run_pipeline,
            workspace_id=ws.id,
            folder_id=folder.id if folder else None,
            document_id=doc.id,
            filename=filename,
            mime=mime,
            storage_key=storage_key,
            data=data,
            model_prefs=dict(ws.model_prefs or {}),
        )

    return doc


@router.get("", response_model=list[DocumentOut])
async def list_documents(
    ctx: CurrentWorkspace,
    db: DB,
    folder_id: str | None = None,
) -> list[Document]:
    ws, _ = ctx
    stmt = select(Document).where(Document.workspace_id == ws.id)
    if folder_id:
        stmt = stmt.where(Document.folder_id == folder_id)
    return list((await db.execute(stmt)).scalars().all())


@router.delete(
    "/{document_id}",
    status_code=204,
    response_class=Response,
    dependencies=[Depends(require_role(Role.WORKSPACE_ADMIN.value, Role.WORKSPACE_EDITOR.value))],
)
async def delete_document(
    document_id: str,
    ctx: CurrentWorkspace,
    user: CurrentUser,
    db: DB,
) -> None:
    ws, _ = ctx
    doc = (
        await db.execute(
            select(Document).where(Document.id == document_id, Document.workspace_id == ws.id)
        )
    ).scalar_one_or_none()
    if not doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "document not found")

    # Best-effort vector + object cleanup; failures are logged but non-fatal.
    try:
        from app.services.qdrant import delete_document as qdrant_delete

        await qdrant_delete(ws.id, doc.id)
    except Exception as e:
        logger.warning("qdrant delete failed for %s: %s", doc.id, e)

    ws.used_bytes = max(0, ws.used_bytes - doc.size_bytes)
    await db.delete(doc)
    db.add(
        AuditLog(
            workspace_id=ws.id,
            user_id=user.id,
            action="document.delete",
            target_type="document",
            target_id=document_id,
            payload={"filename": doc.filename},
        )
    )
    await db.commit()
