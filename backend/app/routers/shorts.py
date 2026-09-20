import os
import uuid
import logging
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy import select, func, desc, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import RenderedShort, ClipCandidate, GoogleDriveExport, AppJob, SourceVideo
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

    video_ids = {c.video_id for _, c in results if c and c.video_id}
    videos = {}
    if video_ids:
        vrows = (await db.execute(select(SourceVideo).where(SourceVideo.id.in_(video_ids)))).scalars().all()
        videos = {v.id: v for v in vrows}

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
            is_youtube_uploaded=bool(short.is_youtube_uploaded),
            source_url=(videos.get(clip.video_id).source_url if clip and clip.video_id in videos else None),
            source_title=(videos.get(clip.video_id).original_name if clip and clip.video_id in videos else None),
            download_url=f"/api/shorts/{short.id}/download",
            thumbnail_url=f"/api/shorts/{short.id}/thumbnail",
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
            logger.error(f"Gagal menghapus shorts {s_id}: {e}")
            continue

    await db.commit()
    return BatchActionResponse(
        success_count=success,
        failed_count=len(payload.ids) - success,
        message=f"{success} shorts berhasil dihapus."
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
    video = await db.get(SourceVideo, clip.video_id) if clip and clip.video_id else None
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
        is_youtube_uploaded=bool(short.is_youtube_uploaded),
        source_url=video.source_url if video else None,
        source_title=video.original_name if video else None,
        download_url=f"/api/shorts/{short.id}/download",
        thumbnail_url=f"/api/shorts/{short.id}/thumbnail",
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

@router.get("/{short_id}/thumbnail", dependencies=[Depends(get_media_session)])
async def get_short_thumbnail(short_id: str, db: AsyncSession = Depends(get_db)):
    short = await db.get(RenderedShort, short_id)
    if not short:
        raise HTTPException(status_code=404, detail="Shorts tidak ditemukan.")

    # 1. Cek thumbnails/{short.id}.jpg
    thumb_path = resolve_path(f"thumbnails/{short.id}.jpg")
    if os.path.exists(thumb_path):
        return FileResponse(thumb_path, media_type="image/jpeg")

    # 2. Cek short.thumbnail_path jika diset spesifik
    if getattr(short, "thumbnail_path", None):
        cand_path = resolve_path(short.thumbnail_path)
        if os.path.exists(cand_path):
            media_type = "image/png" if str(cand_path).lower().endswith(".png") else "image/jpeg"
            return FileResponse(cand_path, media_type=media_type)

    # 3. Generate on-the-fly jika render video sudah selesai
    video_abs = resolve_path(short.local_path)
    if os.path.exists(video_abs):
        try:
            os.makedirs(os.path.dirname(thumb_path), exist_ok=True)
            from app.services.ffmpeg_service import generate_thumbnail
            await generate_thumbnail(video_abs, thumb_path, seek_seconds=1.0, smart=True)
            if os.path.exists(thumb_path):
                short.thumbnail_path = f"thumbnails/{short.id}.jpg"
                await db.commit()
                return FileResponse(thumb_path, media_type="image/jpeg")
        except Exception as exc:
            logger.warning("Gagal membuat thumbnail on the fly untuk short %s: %s", short.id, exc)

    # 4. Fallback ke thumbnail source video
    clip = await db.get(ClipCandidate, short.clip_id) if short.clip_id else None
    if clip and clip.video_id:
        src_thumb = resolve_path(f"thumbnails/{clip.video_id}.jpg")
        if os.path.exists(src_thumb):
            return FileResponse(src_thumb, media_type="image/jpeg")

    raise HTTPException(status_code=404, detail="Thumbnail short belum tersedia.")

@router.post("/{short_id}/thumbnail", dependencies=[Depends(get_current_session)])
async def upload_short_thumbnail(short_id: str, file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    short = await db.get(RenderedShort, short_id)
    if not short:
        raise HTTPException(status_code=404, detail="Shorts tidak ditemukan.")

    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in (".jpg", ".jpeg", ".png", ".webp"):
        ext = ".jpg"

    thumb_rel = f"thumbnails/{short.id}{ext}"
    thumb_path = resolve_path(thumb_rel)
    os.makedirs(os.path.dirname(thumb_path), exist_ok=True)

    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Ukuran thumbnail maksimal 10MB.")

    with open(thumb_path, "wb") as f:
        f.write(content)

    short.thumbnail_path = thumb_rel
    await db.commit()

    return {
        "ok": True,
        "thumbnail_url": f"/api/shorts/{short.id}/thumbnail",
        "custom_thumbnail_path": thumb_rel,
        "message": "Thumbnail berhasil disimpan.",
    }

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
