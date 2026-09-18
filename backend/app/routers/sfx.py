import os
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from fastapi.responses import FileResponse
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import SFXTrack
from app.schemas import SFXTrackResponse
from app.core.security import get_current_session, get_media_session
from app.services.storage_service import resolve_path
from app.services.ffmpeg_service import probe_video

router = APIRouter(prefix="/sfx", tags=["Sound Effects"])

ALLOWED_EXTENSIONS = {".mp3", ".wav", ".ogg", ".m4a", ".aac"}
MAX_BYTES = 5 * 1024 * 1024


def _to_response(track: SFXTrack) -> SFXTrackResponse:
    return SFXTrackResponse(
        id=track.id,
        title=track.title,
        duration_seconds=round(track.duration_seconds or 0.0, 2),
        file_size_bytes=track.file_size_bytes or 0,
        is_builtin=bool(track.is_builtin),
        stream_url=f"/api/sfx/{track.id}/stream",
        created_at=track.created_at.isoformat() if track.created_at else ""
    )


@router.get("", response_model=List[SFXTrackResponse], dependencies=[Depends(get_current_session)])
async def list_sfx_tracks(db: AsyncSession = Depends(get_db)):
    """List semua sound effect di library."""
    stmt = select(SFXTrack).order_by(desc(SFXTrack.is_builtin), desc(SFXTrack.created_at))
    rows = (await db.execute(stmt)).scalars().all()
    return [_to_response(r) for r in rows]


@router.post("/upload", response_model=SFXTrackResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(get_current_session)])
async def upload_sfx_track(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db)
):
    """Unggah sound effect pendek (maks 5MB)."""
    filename = file.filename or "sfx.mp3"
    _, ext = os.path.splitext(filename.lower())
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Format berkas tidak didukung. Format yang didukung: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )

    content = await file.read()
    if len(content) > MAX_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Ukuran berkas melebihi 5MB."
        )
    if not content:
        raise HTTPException(status_code=400, detail="Berkas kosong.")

    track_id = uuid.uuid4().hex
    rel_path = f"sfx/{track_id}{ext}"
    abs_path = resolve_path(rel_path)
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
    with open(abs_path, "wb") as f:
        f.write(content)

    duration = 0.0
    try:
        probe = await probe_video(abs_path)
        duration = float(probe.get("duration", 0.0))
    except Exception:
        pass

    record = SFXTrack(
        id=track_id,
        title=(title or "").strip() or os.path.splitext(filename)[0],
        local_path=rel_path,
        duration_seconds=duration,
        file_size_bytes=len(content),
        is_builtin=False
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return _to_response(record)


@router.get("/{sfx_id}/stream", dependencies=[Depends(get_media_session)])
async def stream_sfx_track(sfx_id: str, db: AsyncSession = Depends(get_db)):
    """Preview/stream sound effect."""
    track = await db.get(SFXTrack, sfx_id)
    if not track:
        raise HTTPException(status_code=404, detail="SFX tidak ditemukan.")
    abs_path = resolve_path(track.local_path)
    if not os.path.exists(abs_path):
        raise HTTPException(status_code=404, detail="Berkas fisik SFX tidak ditemukan.")
    media_type = "audio/mpeg"
    if track.local_path.endswith(".wav"):
        media_type = "audio/wav"
    elif track.local_path.endswith(".ogg"):
        media_type = "audio/ogg"
    elif track.local_path.endswith((".m4a", ".aac")):
        media_type = "audio/mp4"
    return FileResponse(abs_path, media_type=media_type, filename=f"{track.title}{os.path.splitext(track.local_path)[1]}")


@router.delete("/{sfx_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(get_current_session)])
async def delete_sfx_track(sfx_id: str, db: AsyncSession = Depends(get_db)):
    """Hapus SFX dari library dan disk."""
    track = await db.get(SFXTrack, sfx_id)
    if not track:
        raise HTTPException(status_code=404, detail="SFX tidak ditemukan.")
    abs_path = resolve_path(track.local_path)
    if os.path.exists(abs_path):
        try:
            os.remove(abs_path)
        except Exception:
            pass
    await db.delete(track)
    await db.commit()
    return None
