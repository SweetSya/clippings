import os
import re
import uuid
from typing import Optional
import aiofiles
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, Response, status, Form
from fastapi.responses import FileResponse
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import SourceVideo, Transcript, ClipCandidate, RenderedShort, AppJob, AppSetting
from app.schemas import (
    VideoUploadResponse,
    VideoListItem,
    VideoStatusResponse,
    TranscriptResponse,
    ClipCandidateResponse,
    PaginatedResponse,
    YouTubeInfoRequest,
    YouTubeInfoResponse,
    YouTubeDownloadRequest,
    BatchDeleteRequest,
    BatchActionResponse
)
from app.core.security import get_current_session, get_media_session
from app.config import settings
from app.services.storage_service import resolve_path, delete_video_artifacts
from app.services.ffmpeg_service import probe_video, generate_thumbnail
from app.services.youtube_service import get_youtube_info, download_youtube_video
from app.services.pipeline import default_render_settings

router = APIRouter(prefix="/videos", tags=["Videos"])

ALLOWED_EXTENSIONS = {".mp4", ".mkv", ".mov", ".avi", ".webm"}

@router.post("/upload", response_model=VideoUploadResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(get_current_session)])
async def upload_video(
    file: UploadFile = File(...),
    auto_generate: bool = Form(False),
    description: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db)
):
    original_name = file.filename or "video.mp4"
    ext = os.path.splitext(original_name)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=422,
            detail={"error": {"code": "INVALID_FORMAT", "message": f"Format berkas {ext} tidak didukung. Gunakan: {', '.join(ALLOWED_EXTENSIONS)}"}}
        )

    video_id = uuid.uuid4().hex
    saved_filename = f"{video_id}{ext}"
    rel_path = f"uploads/{saved_filename}"
    abs_path = resolve_path(rel_path)

    # 1. Stream file to disk
    total_bytes = 0
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    async with aiofiles.open(abs_path, "wb") as out_file:
        while chunk := await file.read(1024 * 1024):  # 1MB chunks
            total_bytes += len(chunk)
            if total_bytes > max_bytes:
                os.remove(abs_path)
                raise HTTPException(
                    status_code=413,
                    detail={"error": {"code": "PAYLOAD_TOO_LARGE", "message": f"Ukuran berkas melebihi batas {settings.MAX_UPLOAD_SIZE_MB}MB."}}
                )
            await out_file.write(chunk)

    # 2. Probe video metadata
    duration = 0.0
    try:
        probe_res = await probe_video(abs_path)
        duration = probe_res.get("duration", 0.0)
    except Exception as e:
        # Keep duration as 0 if ffprobe cannot parse immediately
        pass

    # 3. Generate thumbnail
    thumb_rel = f"thumbnails/{video_id}.jpg"
    thumb_path = resolve_path(thumb_rel)
    try:
        await generate_thumbnail(abs_path, thumb_path, seek_seconds=1.0)
    except Exception:
        pass

    # 4. Insert into database
    video_record = SourceVideo(
        id=video_id,
        filename=saved_filename,
        original_name=original_name,
        local_file_path=rel_path,
        file_size_bytes=total_bytes,
        duration_seconds=duration,
        status="UPLOADED",
        description=description.strip() if description else None,
        auto_generate_shorts=auto_generate
    )
    db.add(video_record)

    # 5. Automatically enqueue AUDIO_EXTRACT job
    job = AppJob(
        id=uuid.uuid4().hex,
        job_type="AUDIO_EXTRACT",
        ref_id=video_id,
        status="QUEUED"
    )
    db.add(job)
    await db.commit()

    return VideoUploadResponse(
        video_id=video_id,
        filename=saved_filename,
        original_name=original_name,
        duration_seconds=duration,
        file_size_bytes=total_bytes,
        auto_generate_shorts=auto_generate
    )

@router.post("/youtube/info", response_model=YouTubeInfoResponse, dependencies=[Depends(get_current_session)])
async def get_yt_info(payload: YouTubeInfoRequest):
    url = payload.url.strip() if payload.url else ""
    if not url:
        raise HTTPException(
            status_code=422,
            detail={"error": {"code": "INVALID_URL", "message": "URL YouTube tidak boleh kosong."}}
        )
    try:
        info = await get_youtube_info(url)
        return YouTubeInfoResponse(
            id=info.get("id"),
            title=info.get("title") or "YouTube Video",
            duration_seconds=info.get("duration_seconds") or 0.0,
            thumbnail_url=info.get("thumbnail_url"),
            channel=info.get("channel"),
            webpage_url=info.get("webpage_url") or url
        )
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": "YOUTUBE_INFO_FAILED", "message": str(e)}}
        )

@router.post("/youtube/download", response_model=VideoUploadResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(get_current_session)])
async def download_yt_video(
    payload: YouTubeDownloadRequest,
    db: AsyncSession = Depends(get_db)
):
    url = payload.url.strip() if payload.url else ""
    if not url:
        raise HTTPException(
            status_code=422,
            detail={"error": {"code": "INVALID_URL", "message": "URL YouTube tidak boleh kosong."}}
        )

    # Resolve quality preference (fallback to db setting or default '1080p')
    quality = payload.quality
    if not quality:
        setting = await db.get(AppSetting, "yt_quality")
        quality = setting.setting_value if setting and setting.setting_value else "1080p"

    video_id = uuid.uuid4().hex
    saved_filename = f"{video_id}.mp4"
    rel_path = f"uploads/{saved_filename}"
    abs_path = resolve_path(rel_path)

    # 1. Fetch info for metadata
    try:
        info = await get_youtube_info(url)
    except Exception:
        info = {"title": "YouTube Video", "duration_seconds": 0.0}

    title = info.get("title") or "YouTube Video"
    clean_title = re.sub(r'[\\/*?:"<>|]', "", title).strip() or "youtube_video"
    original_name = f"{clean_title}.mp4"

    # 2. Download via yt-dlp
    try:
        await download_youtube_video(url, abs_path, quality_pref=quality)
    except Exception as e:
        if os.path.exists(abs_path):
            try:
                os.remove(abs_path)
            except Exception:
                pass
        raise HTTPException(
            status_code=500,
            detail={"error": {"code": "DOWNLOAD_FAILED", "message": f"Gagal mengunduh video YouTube: {str(e)}"}}
        )

    if not os.path.exists(abs_path):
        raise HTTPException(
            status_code=500,
            detail={"error": {"code": "DOWNLOAD_FAILED", "message": "Berkas video hasil download tidak ditemukan."}}
        )

    total_bytes = os.path.getsize(abs_path)

    # 3. Probe video metadata
    duration = info.get("duration_seconds") or 0.0
    try:
        probe_res = await probe_video(abs_path)
        if probe_res.get("duration"):
            duration = probe_res["duration"]
    except Exception:
        pass

    # 4. Generate thumbnail
    thumb_rel = f"thumbnails/{video_id}.jpg"
    thumb_path = resolve_path(thumb_rel)
    try:
        seek_sec = min(2.0, duration / 2.0) if duration > 0 else 1.0
        await generate_thumbnail(abs_path, thumb_path, seek_seconds=seek_sec)
    except Exception:
        pass

    # 5. Insert into database
    video_record = SourceVideo(
        id=video_id,
        filename=saved_filename,
        original_name=original_name,
        local_file_path=rel_path,
        file_size_bytes=total_bytes,
        duration_seconds=duration,
        status="UPLOADED",
        description=info.get("description") or None,
        auto_generate_shorts=bool(payload.auto_generate)
    )
    db.add(video_record)

    # 6. Automatically enqueue AUDIO_EXTRACT job
    job = AppJob(
        id=uuid.uuid4().hex,
        job_type="AUDIO_EXTRACT",
        ref_id=video_id,
        status="QUEUED"
    )
    db.add(job)
    await db.commit()

    return VideoUploadResponse(
        video_id=video_id,
        filename=saved_filename,
        original_name=original_name,
        duration_seconds=duration,
        file_size_bytes=total_bytes,
        auto_generate_shorts=bool(payload.auto_generate)
    )

@router.get("", response_model=PaginatedResponse[VideoListItem], dependencies=[Depends(get_current_session)])
async def list_videos(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status_filter: str = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(SourceVideo)
    count_stmt = select(func.count()).select_from(SourceVideo)

    if status_filter:
        stmt = stmt.where(SourceVideo.status == status_filter.upper())
        count_stmt = count_stmt.where(SourceVideo.status == status_filter.upper())

    total = await db.scalar(count_stmt) or 0
    stmt = stmt.order_by(desc(SourceVideo.created_at)).offset((page - 1) * limit).limit(limit)
    rows = (await db.execute(stmt)).scalars().all()

    items = []
    for r in rows:
        thumb_url = f"/api/videos/{r.id}/thumbnail"
        # Count candidate clips
        clips_count = await db.scalar(
            select(func.count(ClipCandidate.id)).where(ClipCandidate.video_id == r.id)
        ) or 0

        # Count completed rendered shorts
        rendered_count = await db.scalar(
            select(func.count(RenderedShort.id))
            .join(ClipCandidate, RenderedShort.clip_id == ClipCandidate.id)
            .where(ClipCandidate.video_id == r.id, RenderedShort.render_status == "COMPLETED")
        ) or 0

        items.append(VideoListItem(
            id=r.id,
            original_name=r.original_name,
            status=r.status,
            duration_seconds=r.duration_seconds,
            file_size_bytes=r.file_size_bytes,
            language=r.language,
            thumbnail_url=thumb_url,
            created_at=r.created_at.isoformat() if r.created_at else "",
            description=r.description,
            clips_count=clips_count,
            rendered_count=rendered_count,
            auto_generate_shorts=bool(r.auto_generate_shorts)
        ))

    return PaginatedResponse(
        items=items,
        page=page,
        limit=limit,
        total=total
    )

@router.post("/{video_id}/auto-generate", status_code=status.HTTP_202_ACCEPTED, dependencies=[Depends(get_current_session)])
async def trigger_auto_generate(video_id: str, db: AsyncSession = Depends(get_db)):
    video = await db.get(SourceVideo, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video tidak ditemukan.")

    video.auto_generate_shorts = True

    # Check existing clips
    clips_stmt = select(ClipCandidate).where(ClipCandidate.video_id == video_id)
    clips = (await db.execute(clips_stmt)).scalars().all()

    queued_count = 0
    if clips:
        for clip in clips:
            existing_short = await db.scalar(
                select(RenderedShort).where(RenderedShort.clip_id == clip.id)
            )
            if existing_short and existing_short.render_status in ["COMPLETED", "RENDERING", "PENDING"]:
                continue

            short_id = uuid.uuid4().hex
            out_filename = f"{short_id}_9x16.mp4"
            rel_path = f"exports/{out_filename}"
            settings_dict = default_render_settings()
            short = RenderedShort(
                id=short_id,
                clip_id=clip.id,
                output_filename=out_filename,
                local_path=rel_path,
                render_settings=settings_dict,
                render_status="PENDING",
                render_progress=0
            )
            db.add(short)
            job = AppJob(
                id=uuid.uuid4().hex,
                job_type="RENDER",
                ref_id=short_id,
                status="QUEUED",
                payload=settings_dict
            )
            db.add(job)
            queued_count += 1
    else:
        if video.status in ["UPLOADED", "FAILED"]:
            video.status = "UPLOADED"
            job = AppJob(
                id=uuid.uuid4().hex,
                job_type="AUDIO_EXTRACT",
                ref_id=video_id,
                status="QUEUED"
            )
            db.add(job)

    await db.commit()
    return {
        "status": "QUEUED",
        "video_id": video_id,
        "auto_generate_shorts": True,
        "queued_renders": queued_count,
        "message": f"Auto-generate aktif. {queued_count} video shorts telah dimasukkan ke antrean render." if queued_count > 0 else "Auto-generate aktif. Semua klip akan otomatis dirender setelah analisis video selesai."
    }

@router.post("/{video_id}/process", status_code=status.HTTP_202_ACCEPTED, dependencies=[Depends(get_current_session)])
async def process_video(video_id: str, db: AsyncSession = Depends(get_db)):
    video = await db.get(SourceVideo, video_id)
    if not video:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "VIDEO_NOT_FOUND", "message": "Video tidak ditemukan."}}
        )

    if video.status in ["EXTRACTING_AUDIO", "TRANSCRIBING", "ANALYZING"]:
        raise HTTPException(
            status_code=409,
            detail={"error": {"code": "ALREADY_PROCESSING", "message": "Video sedang dalam proses antrean."}}
        )

    video.status = "UPLOADED"
    video.error_message = None

    job = AppJob(
        id=uuid.uuid4().hex,
        job_type="AUDIO_EXTRACT",
        ref_id=video_id,
        status="QUEUED"
    )
    db.add(job)
    await db.commit()

    return {"status": "QUEUED", "video_id": video_id}

@router.get("/{video_id}/status", response_model=VideoStatusResponse, dependencies=[Depends(get_current_session)])
async def get_video_status(video_id: str, db: AsyncSession = Depends(get_db)):
    video = await db.get(SourceVideo, video_id)
    if not video:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "VIDEO_NOT_FOUND", "message": "Video tidak ditemukan."}}
        )

    # Calculate sub-job progress
    progress_map = {"audio_extract": 0, "transcribe": 0, "analyze": 0}
    if video.status == "EXTRACTING_AUDIO":
        progress_map["audio_extract"] = 50
    elif video.status == "TRANSCRIBING":
        progress_map["audio_extract"] = 100
        progress_map["transcribe"] = 50
    elif video.status == "ANALYZING":
        progress_map["audio_extract"] = 100
        progress_map["transcribe"] = 100
        progress_map["analyze"] = 50
    elif video.status == "READY":
        progress_map["audio_extract"] = 100
        progress_map["transcribe"] = 100
        progress_map["analyze"] = 100

    return VideoStatusResponse(
        video_id=video.id,
        status=video.status,
        error_message=video.error_message,
        job_progress=progress_map
    )

@router.get("/{video_id}/transcript", response_model=TranscriptResponse, dependencies=[Depends(get_current_session)])
async def get_video_transcript(video_id: str, db: AsyncSession = Depends(get_db)):
    video = await db.get(SourceVideo, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    transcript = await db.scalar(select(Transcript).where(Transcript.video_id == video_id))
    if not transcript:
        raise HTTPException(status_code=404, detail="Transkrip belum tersedia.")

    return TranscriptResponse(
        video_id=video_id,
        full_text=transcript.full_text,
        language=video.language,
        json_url=f"/api/videos/{video_id}/transcript/json"
    )

@router.get("/{video_id}/transcript/json", dependencies=[Depends(get_current_session)])
async def download_transcript_json(video_id: str, db: AsyncSession = Depends(get_db)):
    t_path = resolve_path(f"transcripts/{video_id}.json")
    if not os.path.exists(t_path):
        raise HTTPException(status_code=404, detail="Berkas transcript JSON tidak ditemukan.")
    return FileResponse(t_path, media_type="application/json", filename=f"transcript_{video_id}.json")

@router.get("/{video_id}/clips", response_model=list[ClipCandidateResponse], dependencies=[Depends(get_current_session)])
async def get_video_clips(video_id: str, db: AsyncSession = Depends(get_db)):
    stmt = select(ClipCandidate).where(ClipCandidate.video_id == video_id).order_by(desc(ClipCandidate.hook_score))
    clips = (await db.execute(stmt)).scalars().all()

    return [
        ClipCandidateResponse(
            id=c.id,
            video_id=c.video_id,
            title=c.title,
            start_time_seconds=c.start_time_seconds,
            end_time_seconds=c.end_time_seconds,
            duration_seconds=c.duration_seconds,
            hook_score=c.hook_score,
            virality_reason=c.virality_reason,
            is_selected=c.is_selected,
            created_at=c.created_at.isoformat() if c.created_at else ""
        )
        for c in clips
    ]

@router.get("/{video_id}/thumbnail", dependencies=[Depends(get_media_session)])
async def get_video_thumbnail(video_id: str):
    thumb_path = resolve_path(f"thumbnails/{video_id}.jpg")
    if not os.path.exists(thumb_path):
        raise HTTPException(status_code=404, detail="Thumbnail tidak ditemukan.")
    return FileResponse(thumb_path, media_type="image/jpeg")

@router.get("/{video_id}/stream", dependencies=[Depends(get_media_session)])
async def stream_video(video_id: str, db: AsyncSession = Depends(get_db)):
    video = await db.get(SourceVideo, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video tidak ditemukan.")

    abs_path = resolve_path(video.local_file_path)
    if not os.path.exists(abs_path):
        raise HTTPException(status_code=404, detail="Berkas video tidak ditemukan di storage.")

    return FileResponse(abs_path, media_type="video/mp4")

@router.delete("/{video_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(get_current_session)])
async def delete_video(video_id: str, db: AsyncSession = Depends(get_db)):
    video = await db.get(SourceVideo, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video tidak ditemukan.")

    # Remove physical files from storage
    delete_video_artifacts(video_id)

    # Cascade delete in database
    await db.delete(video)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

@router.post("/batch-delete", response_model=BatchActionResponse, dependencies=[Depends(get_current_session)])
async def batch_delete_videos(payload: BatchDeleteRequest, db: AsyncSession = Depends(get_db)):
    success = 0
    for v_id in payload.ids:
        video = await db.get(SourceVideo, v_id)
        if video:
            delete_video_artifacts(v_id)
            await db.delete(video)
            success += 1
    await db.commit()
    return BatchActionResponse(
        success_count=success,
        failed_count=len(payload.ids) - success,
        message=f"{success} video sumber berhasil dihapus."
    )

@router.post("/batch-auto-generate", response_model=BatchActionResponse, dependencies=[Depends(get_current_session)])
async def batch_auto_generate_videos(payload: BatchDeleteRequest, db: AsyncSession = Depends(get_db)):
    total_queued = 0
    success_videos = 0
    for v_id in payload.ids:
        video = await db.get(SourceVideo, v_id)
        if not video:
            continue

        video.auto_generate_shorts = True
        success_videos += 1

        clips = (await db.execute(
            select(ClipCandidate).where(ClipCandidate.video_id == v_id)
        )).scalars().all()

        for c in clips:
            existing_short = await db.scalar(
                select(RenderedShort).where(RenderedShort.clip_id == c.id)
            )
            if not existing_short:
                short_id = uuid.uuid4().hex
                new_short = RenderedShort(
                    id=short_id,
                    clip_id=c.id,
                    output_filename=f"short_{c.id[:8]}.mp4",
                    local_path=f"exports/short_{c.id[:8]}.mp4",
                    file_size_bytes=0,
                    render_status="PENDING",
                    render_progress=0,
                    is_drive_uploaded=False
                )
                db.add(new_short)

                render_job = AppJob(
                    id=uuid.uuid4().hex,
                    job_type="RENDER",
                    ref_id=c.id,
                    status="QUEUED"
                )
                db.add(render_job)
                total_queued += 1

    await db.commit()
    return BatchActionResponse(
        success_count=success_videos,
        failed_count=len(payload.ids) - success_videos,
        message=f"{total_queued} klip dari {success_videos} video dimasukkan ke antrean render otomatis."
    )
