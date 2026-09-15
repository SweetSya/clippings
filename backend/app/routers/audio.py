import os
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from fastapi.responses import FileResponse
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import AudioTrack
from app.schemas import AudioTrackResponse, YouTubeAudioDownloadRequest
from app.core.security import get_current_session, get_media_session
from app.services.storage_service import resolve_path
from app.services.ffmpeg_service import probe_video
from app.services.youtube_service import download_youtube_audio

router = APIRouter(prefix="/audio", tags=["Audio Library"])

ALLOWED_EXTENSIONS = {".mp3", ".wav", ".m4a", ".aac", ".ogg"}


def _to_response(track: AudioTrack) -> AudioTrackResponse:
    return AudioTrackResponse(
        id=track.id,
        title=track.title,
        source_type=track.source_type,
        source_url=track.source_url,
        duration_seconds=round(track.duration_seconds or 0.0, 2),
        file_size_bytes=track.file_size_bytes or 0,
        stream_url=f"/api/audio/{track.id}/stream",
        created_at=track.created_at.isoformat() if track.created_at else ""
    )


@router.get("", response_model=List[AudioTrackResponse], dependencies=[Depends(get_current_session)])
async def list_audio_tracks(db: AsyncSession = Depends(get_db)):
    """
    List all uploaded and downloaded audio tracks for background music (BGM).
    """
    stmt = select(AudioTrack).order_by(desc(AudioTrack.created_at))
    rows = (await db.execute(stmt)).scalars().all()
    return [_to_response(r) for r in rows]


@router.post("/upload", response_model=AudioTrackResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(get_current_session)])
async def upload_audio_track(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db)
):
    """
    Upload an audio file (MP3, WAV, M4A, AAC, OGG) to the audio library.
    """
    filename = file.filename or "audio.mp3"
    _, ext = os.path.splitext(filename.lower())
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Format berkas tidak didukung. Format yang didukung: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    track_id = uuid.uuid4().hex
    rel_path = f"audio_library/{track_id}{ext}"
    abs_path = resolve_path(rel_path)
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)

    content = await file.read()
    with open(abs_path, "wb") as f:
        f.write(content)

    file_size = len(content)

    duration = 0.0
    try:
        probe = await probe_video(abs_path)
        duration = float(probe.get("duration", 0.0))
    except Exception:
        pass

    track_title = (title or "").strip() or os.path.splitext(filename)[0]

    record = AudioTrack(
        id=track_id,
        title=track_title,
        source_type="upload",
        source_url=None,
        local_path=rel_path,
        duration_seconds=duration,
        file_size_bytes=file_size
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)

    return _to_response(record)


@router.post("/download-youtube", response_model=AudioTrackResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(get_current_session)])
async def download_yt_audio(
    payload: YouTubeAudioDownloadRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Download audio track from a YouTube video and convert directly to MP3.
    """
    url = payload.url.strip()
    if not url.startswith("http://") and not url.startswith("https://"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="URL YouTube tidak valid.")

    track_id = uuid.uuid4().hex
    rel_path = f"audio_library/{track_id}.mp3"
    abs_path = resolve_path(rel_path)

    try:
        info = await download_youtube_audio(url, abs_path)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gagal mengunduh audio dari YouTube: {e}"
        )

    record = AudioTrack(
        id=track_id,
        title=info.get("title") or "YouTube Audio",
        source_type="youtube",
        source_url=url,
        local_path=rel_path,
        duration_seconds=info.get("duration_seconds") or 0.0,
        file_size_bytes=info.get("file_size_bytes") or 0
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)

    return _to_response(record)


@router.get("/{track_id}/stream", dependencies=[Depends(get_media_session)])
async def stream_audio_track(track_id: str, db: AsyncSession = Depends(get_db)):
    """
    Stream or download the audio track.
    """
    track = await db.get(AudioTrack, track_id)
    if not track:
        raise HTTPException(status_code=404, detail="Track audio tidak ditemukan.")

    abs_path = resolve_path(track.local_path)
    if not os.path.exists(abs_path):
        raise HTTPException(status_code=404, detail="Berkas fisik audio tidak ditemukan.")

    media_type = "audio/mpeg"
    if track.local_path.endswith(".wav"):
        media_type = "audio/wav"
    elif track.local_path.endswith(".ogg"):
        media_type = "audio/ogg"
    elif track.local_path.endswith(".m4a") or track.local_path.endswith(".aac"):
        media_type = "audio/mp4"

    return FileResponse(abs_path, media_type=media_type, filename=f"{track.title}{os.path.splitext(track.local_path)[1]}")


@router.delete("/{track_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(get_current_session)])
async def delete_audio_track(track_id: str, db: AsyncSession = Depends(get_db)):
    """
    Delete an audio track from library and disk.
    """
    track = await db.get(AudioTrack, track_id)
    if not track:
        raise HTTPException(status_code=404, detail="Track audio tidak ditemukan.")

    abs_path = resolve_path(track.local_path)
    if os.path.exists(abs_path):
        try:
            os.remove(abs_path)
        except Exception:
            pass

    await db.delete(track)
    await db.commit()
    return None
