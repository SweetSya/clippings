import os
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import TTSGeneration
from app.schemas import TTSGenerateRequest, TTSResponse
from app.core.security import get_current_session, get_media_session
from app.services.storage_service import resolve_path
from app.services.tts_service import generate_speech, get_available_voices

router = APIRouter(prefix="/tts", tags=["Text-to-Speech"])

@router.get("/voices", dependencies=[Depends(get_current_session)])
async def list_voices():
    """
    Get list of available high-quality voices (Indonesian & English).
    """
    return get_available_voices()

@router.post("/generate", response_model=TTSResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(get_current_session)])
async def generate_tts(payload: TTSGenerateRequest, db: AsyncSession = Depends(get_db)):
    """
    Generate speech audio narration from text using edge-tts.
    """
    tts_id = uuid.uuid4().hex
    rel_path = f"tts/{tts_id}.mp3"
    abs_path = resolve_path(rel_path)

    try:
        duration = await generate_speech(
            text=payload.text,
            output_path=abs_path,
            voice=payload.voice,
            rate=payload.rate,
            pitch=payload.pitch
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"error": {"code": "TTS_FAILED", "message": f"Gagal membuat audio Text-to-Speech: {e}"}}
        )

    file_size = os.path.getsize(abs_path) if os.path.exists(abs_path) else 0

    record = TTSGeneration(
        id=tts_id,
        text=payload.text,
        voice=payload.voice,
        local_path=rel_path,
        file_size_bytes=file_size,
        duration_seconds=duration,
        status="COMPLETED"
    )
    db.add(record)
    await db.commit()

    return TTSResponse(
        id=tts_id,
        text=payload.text,
        voice=payload.voice,
        audio_url=f"/api/tts/{tts_id}/audio",
        file_size_bytes=file_size,
        duration_seconds=duration,
        created_at=record.created_at.isoformat() if record.created_at else ""
    )

@router.get("/{tts_id}/audio", dependencies=[Depends(get_media_session)])
async def get_tts_audio(tts_id: str, db: AsyncSession = Depends(get_db)):
    record = await db.get(TTSGeneration, tts_id)
    if not record:
        raise HTTPException(status_code=404, detail="Audio TTS tidak ditemukan.")

    abs_path = resolve_path(record.local_path)
    if not os.path.exists(abs_path):
        raise HTTPException(status_code=404, detail="Berkas audio fisik tidak ditemukan.")

    return FileResponse(abs_path, media_type="audio/mpeg", filename=f"tts_{tts_id}.mp3")

@router.get("/history", response_model=list[TTSResponse], dependencies=[Depends(get_current_session)])
async def list_tts_history(
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(TTSGeneration).order_by(desc(TTSGeneration.created_at)).limit(limit)
    rows = (await db.execute(stmt)).scalars().all()
    return [
        TTSResponse(
            id=r.id,
            text=r.text,
            voice=r.voice,
            audio_url=f"/api/tts/{r.id}/audio",
            file_size_bytes=r.file_size_bytes,
            duration_seconds=r.duration_seconds,
            created_at=r.created_at.isoformat() if r.created_at else ""
        )
        for r in rows
    ]
