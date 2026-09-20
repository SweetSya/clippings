"""Daftar antrean background jobs untuk Queue view (apa sedang diproses & statusnya)."""

from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import AppJob, SourceVideo, ClipCandidate, RenderedShort, GoogleDriveExport, YouTubeExport
from app.schemas import JobItem
from app.core.security import get_current_session

router = APIRouter(prefix="/jobs", tags=["Jobs"])

VIDEO_JOB_TYPES = {"YOUTUBE_DOWNLOAD", "AUDIO_EXTRACT", "TRANSCRIBE", "LLM_ANALYZE"}


def _iso(dt) -> Optional[str]:
    try:
        return dt.isoformat() if dt else None
    except Exception:
        return None


@router.get("", response_model=List[JobItem], dependencies=[Depends(get_current_session)])
async def list_jobs(
    status: Optional[str] = Query(None, description="Filter: QUEUED, RUNNING, COMPLETED, FAILED, CANCELLED"),
    job_type: Optional[str] = Query(None, description="Filter tipe job, mis. RENDER"),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """Antrean terbaru dulu. Sertakan label manusiawi untuk tiap ref_id (batch query)."""
    stmt = select(AppJob).order_by(desc(AppJob.created_at)).limit(limit)
    if status:
        stmt = stmt.where(AppJob.status == status.strip().upper())
    if job_type:
        stmt = stmt.where(AppJob.job_type == job_type.strip().upper())
    jobs = (await db.execute(stmt)).scalars().all()

    video_ids = {j.ref_id for j in jobs if j.job_type in VIDEO_JOB_TYPES}
    short_ids = {j.ref_id for j in jobs if j.job_type == "RENDER"}
    export_ids = {j.ref_id for j in jobs if j.job_type == "GDRIVE_UPLOAD"}
    yt_export_ids = {j.ref_id for j in jobs if j.job_type == "YOUTUBE_UPLOAD"}

    videos = {}
    if video_ids:
        rows = (await db.execute(select(SourceVideo).where(SourceVideo.id.in_(video_ids)))).scalars().all()
        videos = {v.id: v for v in rows}
    shorts = {}
    if short_ids:
        rows = (await db.execute(select(RenderedShort).where(RenderedShort.id.in_(short_ids)))).scalars().all()
        shorts = {s.id: s for s in rows}
    exports = {}
    if export_ids:
        rows = (await db.execute(select(GoogleDriveExport).where(GoogleDriveExport.id.in_(export_ids)))).scalars().all()
        exports = {e.id: e for e in rows}
    yt_exports = {}
    if yt_export_ids:
        rows = (await db.execute(select(YouTubeExport).where(YouTubeExport.id.in_(yt_export_ids)))).scalars().all()
        yt_exports = {y.id: y for y in rows}

    clip_ids = {s.clip_id for s in shorts.values() if s.clip_id}
    clip_ids |= {e.short_id for e in exports.values() if e.short_id}
    if yt_exports:
        yt_short_ids = [y.short_id for y in yt_exports.values() if y.short_id]
        if yt_short_ids:
            srows = (await db.execute(select(RenderedShort).where(RenderedShort.id.in_(yt_short_ids)))).scalars().all()
            shorts.update({s.id: s for s in srows})
            clip_ids |= {s.clip_id for s in srows if s.clip_id}

    clips = {}
    if clip_ids:
        # short_id dari export perlu dipetakan dulu
        if export_ids:
            srows = (await db.execute(
                select(RenderedShort).where(RenderedShort.id.in_(
                    [e.short_id for e in exports.values() if e.short_id])))).scalars().all()
            shorts.update({s.id: s for s in srows})
            clip_ids |= {s.clip_id for s in shorts.values() if s.clip_id}
        crows = (await db.execute(select(ClipCandidate).where(ClipCandidate.id.in_(clip_ids)))).scalars().all()
        clips = {c.id: c for c in crows}

    video_names = {}
    need_video_ids = {c.video_id for c in clips.values() if c.video_id} - set(videos)
    if need_video_ids:
        vrows = (await db.execute(select(SourceVideo).where(SourceVideo.id.in_(need_video_ids)))).scalars().all()
        for v in vrows:
            videos[v.id] = v
    video_names = {vid: (v.original_name or vid[:8]) for vid, v in videos.items()}

    items = []
    for j in jobs:
        kind, label = "unknown", j.ref_id[:8]
        if j.job_type in VIDEO_JOB_TYPES:
            kind = "video"
            v = videos.get(j.ref_id)
            label = (v.original_name if v else None) or j.ref_id[:8]
        elif j.job_type == "RENDER":
            kind = "short"
            s = shorts.get(j.ref_id)
            c = clips.get(s.clip_id) if s and s.clip_id else None
            clip_title = c.title if c else None
            vname = video_names.get(c.video_id) if c and c.video_id else None
            label = f"{clip_title or j.ref_id[:8]}" + (f" — {vname}" if vname and clip_title else "")
        elif j.job_type == "GDRIVE_UPLOAD":
            kind = "export"
            e = exports.get(j.ref_id)
            s = shorts.get(e.short_id) if e and e.short_id else None
            c = clips.get(s.clip_id) if s and s.clip_id else None
            label = (c.title if c else None) or (e.gdrive_file_id if e and e.gdrive_file_id else None) or j.ref_id[:8]
        elif j.job_type == "YOUTUBE_UPLOAD":
            kind = "export"
            y = yt_exports.get(j.ref_id)
            s = shorts.get(y.short_id) if y and y.short_id else None
            c = clips.get(s.clip_id) if s and s.clip_id else None
            label = (y.title if y and y.title else None) or (c.title if c else None) or (y.youtube_video_id if y and y.youtube_video_id else None) or j.ref_id[:8]
        items.append(JobItem(
            id=j.id,
            job_type=j.job_type,
            ref_id=j.ref_id,
            ref_kind=kind,
            ref_label=label,
            status=j.status,
            progress=j.progress or 0,
            attempts=j.attempts or 0,
            max_attempts=j.max_attempts or 3,
            error_message=j.error_message,
            created_at=j.created_at.isoformat() if j.created_at else "",
            started_at=_iso(j.started_at),
            finished_at=_iso(j.finished_at),
        ))
    return items
