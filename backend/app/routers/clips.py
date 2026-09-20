import os
import json
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import ClipCandidate, RenderedShort, SourceVideo, AppJob, AppSetting, TextPreset
from app.schemas import (
    ClipCandidateResponse,
    ClipUpdateRequest,
    ClipRenderRequest,
    BatchClipRenderRequest,
    BatchActionResponse,
    ReframePreviewResponse,
    FaceAnchorResponse,
    GenerateNarrationRequest,
    GenerateNarrationResponse,
    SEOGenerateRequest,
    SEOGenerateResponse,
    SynthesizeVoiceRequest,
    SynthesizeVoiceResponse,
)
from app.core.security import get_current_session, get_media_session
from app.core.crypto import decrypt_setting
from app.config import settings
from app.services.storage_service import resolve_path
from app.services.ffmpeg_service import probe_video
from app.services.llm_service import generate_clip_narration
from app.services.tts_service import generate_speech
from app.services.pipeline import default_render_settings
from app.services.reframe_service import (
    build_preview,
    get_head_samples,
    analyze_face_anchor,
    FACE_ANCHOR_LOW_COVERAGE,
    DEFAULT_DEADZONE,
    DEFAULT_PAN_SECONDS,
)

router = APIRouter(prefix="/clips", tags=["Clips"])


def _to_clip_response(clip: ClipCandidate) -> ClipCandidateResponse:
    return ClipCandidateResponse(
        id=clip.id,
        video_id=clip.video_id,
        title=clip.title,
        start_time_seconds=clip.start_time_seconds,
        end_time_seconds=clip.end_time_seconds,
        duration_seconds=clip.duration_seconds,
        hook_score=clip.hook_score,
        composite_score=clip.composite_score or 0,
        speech_rate=clip.speech_rate or 0.0,
        keyword_density=clip.keyword_density or 0.0,
        face_coverage=clip.face_coverage or 0.0,
        virality_reason=clip.virality_reason,
        is_selected=clip.is_selected,
        narration_text=clip.narration_text,
        narration_voice=clip.narration_voice,
        narration_audio_path=clip.narration_audio_path,
        seo_titles=list(clip.seo_titles or []) or None,
        seo_description=clip.seo_description,
        seo_tags=list(clip.seo_tags or []) or None,
        seo_hashtags=list(clip.seo_hashtags or []) or None,
        created_at=clip.created_at.isoformat() if clip.created_at else ""
    )


@router.patch("/{clip_id}", response_model=ClipCandidateResponse, dependencies=[Depends(get_current_session)])
async def update_clip(
    clip_id: str,
    payload: ClipUpdateRequest,
    db: AsyncSession = Depends(get_db)
):
    clip = await db.get(ClipCandidate, clip_id)
    if not clip:
        raise HTTPException(status_code=404, detail="Kandidat klip tidak ditemukan.")

    if payload.is_selected is not None:
        clip.is_selected = payload.is_selected
    if payload.title is not None:
        clip.title = payload.title.strip()
    if payload.start_time_seconds is not None:
        clip.start_time_seconds = payload.start_time_seconds
    if payload.end_time_seconds is not None:
        clip.end_time_seconds = payload.end_time_seconds
    if payload.start_time_seconds is not None or payload.end_time_seconds is not None:
        clip.duration_seconds = max(1.0, clip.end_time_seconds - clip.start_time_seconds)
    if payload.narration_text is not None:
        clip.narration_text = payload.narration_text
    if payload.narration_voice is not None:
        clip.narration_voice = payload.narration_voice

    await db.commit()
    await db.refresh(clip)

    return _to_clip_response(clip)


@router.post("/batch-render", response_model=BatchActionResponse, status_code=status.HTTP_202_ACCEPTED, dependencies=[Depends(get_current_session)])
async def batch_render_clips(
    payload: BatchClipRenderRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Queue rendering for multiple candidate clips at once in the background.
    """
    if not payload.clip_ids:
        raise HTTPException(
            status_code=422,
            detail={"error": {"code": "EMPTY_LIST", "message": "Daftar ID klip tidak boleh kosong."}}
        )

    common_settings = payload.render_settings.model_dump() if payload.render_settings else default_render_settings()
    success_count = 0

    for clip_id in payload.clip_ids:
        clip = await db.get(ClipCandidate, clip_id)
        if not clip:
            continue

        short_id = uuid.uuid4().hex
        out_filename = f"{short_id}_9x16.mp4"
        rel_path = f"exports/{out_filename}"

        clip_settings = dict(common_settings)
        if clip.narration_text and not clip_settings.get("narration_text"):
            clip_settings["narration_text"] = clip.narration_text
            clip_settings["narration_voice"] = clip.narration_voice
            clip_settings["use_voiceover"] = True

        short = RenderedShort(
            id=short_id,
            clip_id=clip_id,
            output_filename=out_filename,
            local_path=rel_path,
            render_settings=clip_settings,
            render_status="PENDING",
            render_progress=0
        )
        db.add(short)

        job = AppJob(
            id=uuid.uuid4().hex,
            job_type="RENDER",
            ref_id=short_id,
            status="QUEUED",
            payload=clip_settings
        )
        db.add(job)
        success_count += 1

    await db.commit()
    return BatchActionResponse(
        success_count=success_count,
        failed_count=len(payload.clip_ids) - success_count,
        message=f"{success_count} klip berhasil dimasukkan ke antrean render background."
    )


@router.post("/{clip_id}/render", status_code=status.HTTP_202_ACCEPTED, dependencies=[Depends(get_current_session)])
async def trigger_render_clip(
    clip_id: str,
    payload: ClipRenderRequest,
    db: AsyncSession = Depends(get_db)
):
    clip = await db.get(ClipCandidate, clip_id)
    if not clip:
        raise HTTPException(status_code=404, detail="Kandidat klip tidak ditemukan.")

    short_id = uuid.uuid4().hex
    out_filename = f"{short_id}_9x16.mp4"
    rel_path = f"exports/{out_filename}"

    settings_dict = payload.model_dump()

    short = RenderedShort(
        id=short_id,
        clip_id=clip_id,
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

    await db.commit()

    return {"short_id": short_id, "status": "PENDING"}


@router.post("/{clip_id}/generate-narration", response_model=GenerateNarrationResponse, dependencies=[Depends(get_current_session)])
async def generate_clip_narration_endpoint(
    clip_id: str,
    payload: GenerateNarrationRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Generate voiceover narration script by comparing Macro-Context
    (video title, description, full extracted transcript) with Micro-Context
    (exact spoken words in clip timestamp range).
    """
    clip = await db.get(ClipCandidate, clip_id)
    if not clip:
        raise HTTPException(status_code=404, detail="Kandidat klip tidak ditemukan.")

    video = await db.get(SourceVideo, clip.video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video sumber tidak ditemukan.")

    # Retrieve LLM settings from DB
    connected_s = await db.get(AppSetting, "llm_connected")
    is_connected = bool(connected_s and connected_s.setting_value.lower() == "true")
    if not is_connected:
        raise HTTPException(
            status_code=400,
            detail="AI belum terhubung. Silakan uji dan hubungkan koneksi AI pada menu Pengaturan."
        )

    api_key_s = await db.get(AppSetting, "llm_api_key")
    base_url_s = await db.get(AppSetting, "llm_base_url")
    model_s = await db.get(AppSetting, "llm_model")

    llm_api_key = None
    if api_key_s and api_key_s.setting_value:
        try:
            llm_api_key = decrypt_setting(api_key_s.setting_value)
        except Exception:
            llm_api_key = None
    llm_base_url = base_url_s.setting_value if base_url_s else "https://api.openai.com/v1"
    llm_model = model_s.setting_value if model_s else "gpt-4o-mini"

    # Read transcript file
    transcript_path = resolve_path(f"transcripts/{video.id}.json")
    full_text = ""
    clip_segments = []
    if os.path.exists(transcript_path):
        with open(transcript_path, "r", encoding="utf-8") as f:
            t_data = json.load(f)
            full_text = t_data.get("full_text") or t_data.get("text") or ""
            segments = t_data.get("segments", [])
            for seg in segments:
                s_start = float(seg.get("start", 0.0))
                s_end = float(seg.get("end", 0.0))
                if s_end >= clip.start_time_seconds and s_start <= clip.end_time_seconds:
                    clip_segments.append(seg)

    clip_text = " ".join(
        (seg.get("text") or "").strip() for seg in clip_segments
    ).strip()

    try:
        narration = await generate_clip_narration(
            macro_title=video.original_name,
            macro_description=getattr(video, "description", None),
            macro_full_text=full_text,
            clip_text=clip_text,
            clip_duration_seconds=clip.duration_seconds,
            llm_base_url=llm_base_url,
            llm_api_key=llm_api_key,
            llm_model=llm_model,
            style=payload.style or "hook_story"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal generate narasi AI: {e}")

    clip.narration_text = narration
    await db.commit()

    word_count = len(narration.split())
    estimated_dur = round(word_count / 2.5, 1)

    return GenerateNarrationResponse(
        clip_id=clip.id,
        narration_text=narration,
        estimated_duration_seconds=estimated_dur
    )


@router.post("/{clip_id}/generate-seo", response_model=SEOGenerateResponse, dependencies=[Depends(get_current_session)])
async def generate_clip_seo_endpoint(
    clip_id: str,
    payload: SEOGenerateRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Generate metadata SEO siap-publish (judul, deskripsi, tags, hashtags).
    LLM bila connected, else template heuristik — tak pernah 400 karena AI mati.
    Hasil disimpan ke klip agar modal upload bisa preload.
    """
    from app.services.seo_service import generate_youtube_seo, generate_tiktok_seo

    clip = await db.get(ClipCandidate, clip_id)
    if not clip:
        raise HTTPException(status_code=404, detail="Kandidat klip tidak ditemukan.")

    video = await db.get(SourceVideo, clip.video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video sumber tidak ditemukan.")

    platform = (payload.platform or "youtube_shorts").strip().lower()
    if platform not in ("youtube_shorts", "tiktok", "instagram_reels"):
        platform = "youtube_shorts"

    # LLM settings (opsional — kosong berarti heuristik)
    connected_s = await db.get(AppSetting, "llm_connected")
    is_connected = bool(connected_s and connected_s.setting_value.lower() == "true")
    llm_base_url = llm_api_key = llm_model = None
    if is_connected:
        base_url_s = await db.get(AppSetting, "llm_base_url")
        api_key_s = await db.get(AppSetting, "llm_api_key")
        model_s = await db.get(AppSetting, "llm_model")
        llm_base_url = base_url_s.setting_value if base_url_s else None
        llm_model = model_s.setting_value if model_s else "gpt-4o-mini"
        if api_key_s and api_key_s.setting_value:
            try:
                llm_api_key = decrypt_setting(api_key_s.setting_value) if api_key_s.is_encrypted else api_key_s.setting_value
            except Exception:
                llm_api_key = None

    # Teks transkrip rentang klip
    transcript_path = resolve_path(f"transcripts/{video.id}.json")
    clip_text = ""
    if os.path.exists(transcript_path):
        try:
            with open(transcript_path, "r", encoding="utf-8") as f:
                t_data = json.load(f)
            parts = []
            for seg in t_data.get("segments", []):
                try:
                    s_start, s_end = float(seg.get("start", 0.0)), float(seg.get("end", 0.0))
                except (TypeError, ValueError):
                    continue
                if s_end >= clip.start_time_seconds and s_start <= clip.end_time_seconds:
                    parts.append(str(seg.get("text") or "").strip())
            clip_text = " ".join(p for p in parts if p)
        except Exception:
            clip_text = ""

    language = (payload.language or "id").strip() or "id"
    if platform == "tiktok":
        seo = await generate_tiktok_seo(
            clip_title=clip.title, clip_text=clip_text, video_title=video.original_name,
            language=language, llm_base_url=llm_base_url or "",
            llm_api_key=llm_api_key, llm_model=llm_model)
    else:
        seo = await generate_youtube_seo(
            clip_title=clip.title, clip_text=clip_text, video_title=video.original_name,
            video_description=getattr(video, "description", None) or "",
            video_type=getattr(video, "video_type", None) or "umum",
            clip_duration=clip.duration_seconds or 30.0, language=language,
            llm_base_url=llm_base_url or "", llm_api_key=llm_api_key, llm_model=llm_model)
        if platform == "instagram_reels":
            from app.services.seo_service import apply_platform_rules
            seo = apply_platform_rules("instagram_reels", seo)

    clip.seo_titles = seo.get("titles", [])
    clip.seo_description = seo.get("description", "")
    clip.seo_tags = seo.get("tags", [])
    clip.seo_hashtags = seo.get("hashtags", [])
    await db.commit()

    return SEOGenerateResponse(
        clip_id=clip.id,
        titles=seo.get("titles", [])[:3],
        description=seo.get("description", ""),
        tags=seo.get("tags", []),
        hashtags=seo.get("hashtags", []),
        category_suggestion=str(seo.get("category_suggestion") or "22"),
        best_upload_time=seo.get("best_upload_time"),
        estimated_reach=seo.get("estimated_reach"),
        caption=seo.get("caption"),
    )


@router.post("/{clip_id}/synthesize-voice", response_model=SynthesizeVoiceResponse, dependencies=[Depends(get_current_session)])
async def synthesize_clip_voice_endpoint(
    clip_id: str,
    payload: SynthesizeVoiceRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Synthesize narration voiceover audio using edge-tts and save to clip.
    """
    clip = await db.get(ClipCandidate, clip_id)
    if not clip:
        raise HTTPException(status_code=404, detail="Kandidat klip tidak ditemukan.")

    voice_rel = f"tts/{clip.id}_narration.mp3"
    voice_abs = resolve_path(voice_rel)
    os.makedirs(os.path.dirname(voice_abs), exist_ok=True)

    try:
        duration = await generate_speech(
            text=payload.text,
            output_path=voice_abs,
            voice=payload.voice,
            rate=payload.rate,
            pitch=payload.pitch
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal membuat audio voiceover: {e}")

    clip.narration_text = payload.text
    clip.narration_voice = payload.voice
    clip.narration_audio_path = voice_rel
    await db.commit()

    return SynthesizeVoiceResponse(
        clip_id=clip.id,
        audio_url=f"/api/clips/{clip.id}/narration-audio",
        duration_seconds=round(duration, 2)
    )


@router.get("/{clip_id}/narration-audio", dependencies=[Depends(get_media_session)])
async def get_clip_narration_audio(clip_id: str, db: AsyncSession = Depends(get_db)):
    """
    Stream the voiceover narration audio file.
    """
    clip = await db.get(ClipCandidate, clip_id)
    if not clip or not clip.narration_audio_path:
        raise HTTPException(status_code=404, detail="Audio narasi belum dibuat.")

    abs_path = resolve_path(clip.narration_audio_path)
    if not os.path.exists(abs_path):
        raise HTTPException(status_code=404, detail="Berkas audio narasi tidak ditemukan.")

    return FileResponse(abs_path, media_type="audio/mpeg", filename=f"narration_{clip_id}.mp3")


@router.get("/{clip_id}/reframe-preview", response_model=ReframePreviewResponse, dependencies=[Depends(get_current_session)])
async def get_reframe_preview(
    clip_id: str,
    deadzone: float = Query(DEFAULT_DEADZONE, ge=0.1, le=0.9),
    pan_seconds: float = Query(DEFAULT_PAN_SECONDS, ge=0.0, le=2.0),
    snap: bool = Query(False),
    db: AsyncSession = Depends(get_db)
):
    """
    Pratinjau lintasan smart reframe: posisi kepala dan timeline offset crop untuk klip ini.
    Hasil deteksi di-cache, sehingga menggeser slider deadzone tidak mengulang deteksi wajah.
    """
    clip = await db.get(ClipCandidate, clip_id)
    if not clip:
        raise HTTPException(status_code=404, detail="Kandidat klip tidak ditemukan.")

    video = await db.get(SourceVideo, clip.video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video sumber tidak ditemukan.")

    video_path = resolve_path(video.local_file_path)
    try:
        probe_info = await probe_video(video_path)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Gagal membaca video sumber: {exc}")

    src_w = int(probe_info["width"])
    src_h = int(probe_info["height"])

    samples = await get_head_samples(
        video_path,
        clip.start_time_seconds,
        clip.end_time_seconds,
        src_w,
        video_id=video.id,
        clip_id=clip.id
    )

    return ReframePreviewResponse(**build_preview(
        samples,
        clip_start=clip.start_time_seconds,
        clip_end=clip.end_time_seconds,
        src_w=src_w,
        src_h=src_h,
        deadzone=deadzone,
        pan_seconds=pan_seconds,
        snap=snap
    ))


@router.post("/{clip_id}/analyze-face-anchor", response_model=FaceAnchorResponse, dependencies=[Depends(get_current_session)])
async def analyze_clip_face_anchor(clip_id: str, db: AsyncSession = Depends(get_db)):
    """
    Analisis posisi wajah (Face Anchor) untuk klip ini: zona dominan + coverage
    + rekomendasi layout/preset streamer. Coverage disimpan ke klip untuk badge.
    Tak pernah 500 untuk kasus degradasi (model hilang/tanpa wajah → coverage 0 + warning).
    """
    clip = await db.get(ClipCandidate, clip_id)
    if not clip:
        raise HTTPException(status_code=404, detail="Kandidat klip tidak ditemukan.")

    video = await db.get(SourceVideo, clip.video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video sumber tidak ditemukan.")

    video_path = resolve_path(video.local_file_path)
    if not os.path.exists(video_path):
        raise HTTPException(status_code=404, detail="Berkas video tidak ditemukan di storage.")

    analysis = await analyze_face_anchor(
        video_path, clip.start_time_seconds, clip.end_time_seconds
    )
    coverage = float(analysis.get("face_coverage") or 0.0)
    clip.face_coverage = coverage
    await db.commit()

    zone = str(analysis.get("dominant_zone") or "center")
    # Rekomendasi layout streamer sadar zona (Phase 3 — 5.2).
    streamer_layout = {"top": "streamer_face_top", "bottom": "streamer_face_bottom"}.get(zone, "single")

    preset_id = await db.scalar(
        select(TextPreset.id)
        .where(TextPreset.is_builtin.is_(True), TextPreset.id.like("%streamer%"))
        .order_by(TextPreset.id)
    )

    warning = None
    if coverage < FACE_ANCHOR_LOW_COVERAGE:
        warning = "Wajah jarang terdeteksi, smart crop mungkin kurang optimal. Pertimbangkan center crop."

    return FaceAnchorResponse(
        clip_id=clip.id,
        dominant_zone=zone,
        avg_cx=float(analysis.get("avg_cx") or 0.5),
        avg_cy=float(analysis.get("avg_cy") or 0.5),
        face_coverage=coverage,
        recommended_layout=streamer_layout,
        recommended_preset_id=preset_id,
        warning=warning,
    )
