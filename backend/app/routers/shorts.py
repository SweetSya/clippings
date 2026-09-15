import os
import uuid
import logging
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import FileResponse
from sqlalchemy import select, func, desc, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import RenderedShort, ClipCandidate, GoogleDriveExport, AppJob
from app.schemas import (
    RenderedShortItem,
    PaginatedResponse,
    GDriveUploadResponse,
    GDriveUploadStatusResponse,
    BatchDeleteRequest,
    BatchActionResponse
)
from app.core.security import get_current_session, get_media_session
from app.services.storage_service import resolve_path, delete_short_artifacts

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/shorts", tags=["Shorts"])

@router.get("", response_model=PaginatedResponse[RenderedShortItem], dependencies=[Depends(get_current_session)])
async def list_shorts(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    count_stmt = select(func.count()).select_from(RenderedShort)
    total = await db.scalar(count_stmt) or 0

    stmt = select(RenderedShort, ClipCandidate).join(
        ClipCandidate, RenderedShort.clip_id == ClipCandidate.id
    ).order_by(desc(RenderedShort.created_at)).offset((page - 1) * limit).limit(limit)

    results = (await db.execute(stmt)).all()

    items = []
    for short, clip in results:
        # Check latest gdrive export
        export = await db.scalar(
            select(GoogleDriveExport).where(GoogleDriveExport.short_id == short.id).order_by(desc(GoogleDriveExport.created_at)).limit(1)
        )
        gd_info = None
        if export:
            gd_info = {
                "upload_status": export.upload_status,
                "gdrive_file_id": export.gdrive_file_id,
                "gdrive_web_view_link": export.gdrive_web_view_link
            }

        items.append(RenderedShortItem(
            id=short.id,
            clip_id=short.clip_id,
            video_id=clip.video_id if clip else None,
            title=clip.title if clip else None,
            output_filename=short.output_filename,
            file_size_bytes=short.file_size_bytes,
            render_status=short.render_status,
            render_progress=short.render_progress,
            is_drive_uploaded=short.is_drive_uploaded,
            download_url=f"/api/shorts/{short.id}/download",
            created_at=short.created_at.isoformat() if short.created_at else "",
            gdrive=gd_info
        ))

    return PaginatedResponse(
        items=items,
        page=page,
        limit=limit,
        total=total
    )

# ----------------- Static batch routes (must be declared BEFORE /{short_id}) -----------------

@router.post("/batch-delete", response_model=BatchActionResponse, dependencies=[Depends(get_current_session)])
async def batch_delete_shorts(payload: BatchDeleteRequest, db: AsyncSession = Depends(get_db)):
    success = 0
    for s_id in payload.ids:
        try:
            short = await db.get(RenderedShort, s_id)
            if short:
                delete_short_artifacts(short.id, short.clip_id, short.local_path)
                # Clean up associated jobs and exports
                export_ids = (await db.scalars(
                    select(GoogleDriveExport.id).where(GoogleDriveExport.short_id == short.id)
                )).all()
                if export_ids:
                    await db.execute(delete(AppJob).where(AppJob.ref_id.in_(export_ids)))
                await db.execute(delete(GoogleDriveExport).where(GoogleDriveExport.short_id == short.id))
                await db.delete(short)
                success += 1
        except Exception as e:
            logger.error(f"Failed to delete short {s_id}: {e}")

    await db.commit()
    return BatchActionResponse(
        success_count=success,
        failed_count=len(payload.ids) - success,
        message=f"{success} video shorts berhasil dihapus."
    )

@router.post("/batch-upload-gdrive", response_model=BatchActionResponse, dependencies=[Depends(get_current_session)])
async def batch_upload_shorts_to_gdrive(payload: BatchDeleteRequest, db: AsyncSession = Depends(get_db)):
    success = 0
    for s_id in payload.ids:
        try:
            short = await db.get(RenderedShort, s_id)
            if short and short.render_status == "COMPLETED" and not short.is_drive_uploaded:
                export_id = uuid.uuid4().hex
                export_record = GoogleDriveExport(
                    id=export_id,
                    short_id=short.id,
                    upload_status="QUEUED",
                    upload_progress=0
                )
                db.add(export_record)
                job = AppJob(
                    id=uuid.uuid4().hex,
                    job_type="GDRIVE_UPLOAD",
                    ref_id=export_id,
                    status="QUEUED"
                )
                db.add(job)
                success += 1
        except Exception as e:
            logger.error(f"Failed to queue gdrive upload for short {s_id}: {e}")

    await db.commit()
    return BatchActionResponse(
        success_count=success,
        failed_count=len(payload.ids) - success,
        message=f"{success} video shorts dimasukkan ke antrean upload Google Drive."
    )

# ----------------- Parameterized routes /{short_id} -----------------

@router.get("/{short_id}", response_model=RenderedShortItem, dependencies=[Depends(get_current_session)])
async def get_short_detail(short_id: str, db: AsyncSession = Depends(get_db)):
    short = await db.get(RenderedShort, short_id)
    if not short:
        raise HTTPException(status_code=404, detail="Shorts tidak ditemukan.")

    clip = await db.get(ClipCandidate, short.clip_id)
    export = await db.scalar(
        select(GoogleDriveExport).where(GoogleDriveExport.short_id == short.id).order_by(desc(GoogleDriveExport.created_at)).limit(1)
    )
    gd_info = None
    if export:
        gd_info = {
            "upload_status": export.upload_status,
            "gdrive_file_id": export.gdrive_file_id,
            "gdrive_web_view_link": export.gdrive_web_view_link
        }

    return RenderedShortItem(
        id=short.id,
        clip_id=short.clip_id,
        video_id=clip.video_id if clip else None,
        title=clip.title if clip else None,
        output_filename=short.output_filename,
        file_size_bytes=short.file_size_bytes,
        render_status=short.render_status,
        render_progress=short.render_progress,
        is_drive_uploaded=short.is_drive_uploaded,
        download_url=f"/api/shorts/{short.id}/download",
        created_at=short.created_at.isoformat() if short.created_at else "",
        gdrive=gd_info
    )

@router.delete("/{short_id}", dependencies=[Depends(get_current_session)])
async def delete_single_short(short_id: str, db: AsyncSession = Depends(get_db)):
    short = await db.get(RenderedShort, short_id)
    if not short:
        raise HTTPException(status_code=404, detail="Shorts tidak ditemukan.")

    delete_short_artifacts(short.id, short.clip_id, short.local_path)
    export_ids = (await db.scalars(
        select(GoogleDriveExport.id).where(GoogleDriveExport.short_id == short.id)
    )).all()
    if export_ids:
        await db.execute(delete(AppJob).where(AppJob.ref_id.in_(export_ids)))
    await db.execute(delete(GoogleDriveExport).where(GoogleDriveExport.short_id == short.id))
    await db.delete(short)
    await db.commit()
    return {"ok": True, "message": "Shorts berhasil dihapus."}

@router.get("/{short_id}/download", dependencies=[Depends(get_media_session)])
async def download_short(short_id: str, db: AsyncSession = Depends(get_db)):
    short = await db.get(RenderedShort, short_id)
    if not short:
        raise HTTPException(status_code=404, detail="Shorts tidak ditemukan.")

    abs_path = resolve_path(short.local_path)
    if not os.path.exists(abs_path):
        raise HTTPException(status_code=404, detail="Berkas video hasil render tidak ditemukan di storage.")

    return FileResponse(
        abs_path,
        media_type="video/mp4",
        filename=short.output_filename
    )

@router.post("/{short_id}/upload-gdrive", status_code=status.HTTP_202_ACCEPTED, dependencies=[Depends(get_current_session)])
async def upload_short_to_gdrive(short_id: str, db: AsyncSession = Depends(get_db)):
    short = await db.get(RenderedShort, short_id)
    if not short:
        raise HTTPException(status_code=404, detail="Shorts tidak ditemukan.")

    if short.render_status != "COMPLETED":
        raise HTTPException(status_code=400, detail="Video belum selesai dirender.")

    # 1. Anti-Double Upload Guard
    if short.is_drive_uploaded:
        existing_export = await db.scalar(
            select(GoogleDriveExport).where(
                GoogleDriveExport.short_id == short.id,
                GoogleDriveExport.upload_status == "SUCCESS"
            ).order_by(desc(GoogleDriveExport.created_at)).limit(1)
        )
        if existing_export:
            return {
                "export_id": existing_export.id,
                "status": "ALREADY_UPLOADED",
                "message": "Klip ini sudah berhasil diunggah sebelumnya. Double-upload dicegah.",
                "gdrive_file_id": existing_export.gdrive_file_id,
                "gdrive_web_view_link": existing_export.gdrive_web_view_link
            }

    # 2. Check if currently uploading or queued
    active_export = await db.scalar(
        select(GoogleDriveExport).where(
            GoogleDriveExport.short_id == short.id,
            GoogleDriveExport.upload_status.in_(["QUEUED", "UPLOADING"])
        ).order_by(desc(GoogleDriveExport.created_at)).limit(1)
    )
    if active_export:
        return {
            "export_id": active_export.id,
            "status": active_export.upload_status,
            "message": "Proses upload sedang berjalan di antrean."
        }

    # 3. Create new export job
    export_id = uuid.uuid4().hex
    export_record = GoogleDriveExport(
        id=export_id,
        short_id=short.id,
        upload_status="QUEUED",
        upload_progress=0
    )
    db.add(export_record)

    job = AppJob(
        id=uuid.uuid4().hex,
        job_type="GDRIVE_UPLOAD",
        ref_id=export_id,
        status="QUEUED"
    )
    db.add(job)

    await db.commit()

    return {"export_id": export_id, "status": "QUEUED"}

@router.get("/{short_id}/upload-gdrive/status", response_model=GDriveUploadStatusResponse, dependencies=[Depends(get_current_session)])
async def get_gdrive_upload_status(short_id: str, db: AsyncSession = Depends(get_db)):
    short = await db.get(RenderedShort, short_id)
    if not short:
        raise HTTPException(status_code=404, detail="Shorts tidak ditemukan.")

    export = await db.scalar(
        select(GoogleDriveExport).where(GoogleDriveExport.short_id == short.id).order_by(desc(GoogleDriveExport.created_at)).limit(1)
    )
    if not export:
        raise HTTPException(status_code=404, detail="Belum ada riwayat upload untuk video ini.")

    return GDriveUploadStatusResponse(
        export_id=export.id,
        upload_status=export.upload_status,
        upload_progress=export.upload_progress,
        gdrive_file_id=export.gdrive_file_id,
        gdrive_web_view_link=export.gdrive_web_view_link,
        error_message=export.error_message
    )
