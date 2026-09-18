import os
import json
import logging
import shutil
import uuid
from datetime import datetime, timezone
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import (
    SourceVideo,
    Transcript,
    ClipCandidate,
    RenderedShort,
    GoogleDriveExport,
    AppJob,
    AppSetting,
    AudioTrack,
    TextPreset
)
from app.services.storage_service import resolve_path, hash_file_head
from app.services.ffmpeg_service import probe_video, extract_audio, generate_thumbnail, render_vertical_clip
from app.services.ass_service import generate_karaoke_ass
from app.services.audio_dynamics_service import analyze_vocal_dynamics
from app.services.whisper_service import transcribe_audio
from app.services.llm_service import extract_highlights_with_llm, extract_highlights_two_pass, extract_highlights_chunked
from app.services.tts_service import generate_speech
from app.services.gdrive_service import upload_file_to_drive
from app.services.youtube_service import download_youtube_video
from app.services.reframe_service import (
    build_smart_crop_expression,
    DEFAULT_DEADZONE,
    DEFAULT_PAN_SECONDS,
)
from app.core.crypto import decrypt_setting
from app.config import settings

logger = logging.getLogger(__name__)


async def try_reuse_transcript(db: AsyncSession, video: SourceVideo) -> bool:
    """
    Reuse transkrip video lain ber-hash sama (Phase 4 — 7.2).
    Salin baris Transcript + file JSON, enqueue LLM_ANALYZE saja (skip audio/transcribe).
    Return True bila reuse berhasil. Batasan: file yang beda setelah 1MB pertama
    dianggap sama — didokumentasikan, dapat diterima untuk dedup praktis.
    """
    if not getattr(video, "file_hash", None):
        return False
    donor = await db.scalar(
        select(SourceVideo).where(
            SourceVideo.file_hash == video.file_hash,
            SourceVideo.id != video.id,
        ).order_by(SourceVideo.created_at.desc())
    )
    if not donor:
        return False
    donor_t = await db.scalar(select(Transcript).where(Transcript.video_id == donor.id))
    if not donor_t:
        return False
    src_json = resolve_path(donor_t.transcript_json_path)
    if not os.path.exists(src_json):
        return False
    dst_rel = f"transcripts/{video.id}.json"
    dst_abs = resolve_path(dst_rel)
    try:
        os.makedirs(os.path.dirname(dst_abs), exist_ok=True)
        shutil.copyfile(src_json, dst_abs)
    except OSError as exc:
        logger.warning("Gagal menyalin transkrip cache: %s", exc)
        return False
    db.add(Transcript(
        id=uuid.uuid4().hex,
        video_id=video.id,
        full_text=donor_t.full_text,
        transcript_json_path=dst_rel
    ))
    video.language = donor.language
    video.status = "UPLOADED"
    db.add(AppJob(
        id=uuid.uuid4().hex,
        job_type="LLM_ANALYZE",
        ref_id=video.id,
        status="QUEUED"
    ))
    await db.commit()
    logger.info("Transkrip %s dipakai ulang dari %s (hash sama).", video.id, donor.id)
    return True


def default_render_settings() -> dict:
    """
    Setelan render untuk jalur otomatis (auto-generate shorts).

    Field gaya (font, warna, outline, shadow, uppercase, margin) sengaja TIDAK dikirim:
    handle_render hanya memakai preset bila field terkait tidak dikirim, sehingga preset
    tetap berlaku utuh dan tidak tertimpa nilai default eksplisit.
    """
    return {
        "crop_mode": "smart" if settings.SMART_CROP_DEFAULT else "center",
        "crop_offset_x": 0,
        "smart_deadzone": DEFAULT_DEADZONE,
        "preset_id": None,
        "audio_mode": "mix",
        "bgm_volume": 0.2,
        "audio_track_id": None,
        "use_voiceover": False,
        "narration_text": None,
        "narration_voice": None
    }


async def handle_youtube_download(job: AppJob, db: AsyncSession):
    """
    Download video from YouTube/URL in the background worker queue.
    """
    video_id = job.ref_id
    video = await db.get(SourceVideo, video_id)
    if not video:
        raise ValueError(f"Source video {video_id} not found")

    video.status = "DOWNLOADING"
    await db.commit()

    payload = job.payload or {}
    url = payload.get("url")
    quality = payload.get("quality", "1080p")
    if not url:
        raise ValueError("Missing URL in download job payload")

    raw_video_path = resolve_path(video.local_file_path)

    # 1. Download via yt-dlp
    await download_youtube_video(url, raw_video_path, quality_pref=quality)

    if not os.path.exists(raw_video_path):
        raise ValueError("Downloaded video file not found on disk")

    total_bytes = os.path.getsize(raw_video_path)
    video.file_size_bytes = total_bytes

    # 2. Probe metadata & duration
    try:
        probe_info = await probe_video(raw_video_path)
        if probe_info.get("duration"):
            video.duration_seconds = probe_info["duration"]
    except Exception as e:
        logger.warning(f"Probe failed for {video_id}: {e}")

    # 3. Generate thumbnail
    thumb_rel = f"thumbnails/{video_id}.jpg"
    thumb_path = resolve_path(thumb_rel)
    try:
        seek_sec = min(2.0, video.duration_seconds / 2.0) if video.duration_seconds > 0 else 1.0
        await generate_thumbnail(raw_video_path, thumb_path, seek_seconds=seek_sec)
    except Exception as e:
        logger.warning(f"Thumbnail generation failed for {video_id}: {e}")

    video.status = "UPLOADED"
    video.file_hash = hash_file_head(raw_video_path)
    await db.commit()

    # 4. Reuse transkrip bila unduhan sama pernah diproses, else enqueue AUDIO_EXTRACT.
    if await try_reuse_transcript(db, video):
        return
    next_job = AppJob(
        id=uuid.uuid4().hex,
        job_type="AUDIO_EXTRACT",
        ref_id=video_id,
        status="QUEUED"
    )
    db.add(next_job)
    await db.commit()

async def handle_audio_extract(job: AppJob, db: AsyncSession):
    video_id = job.ref_id
    video = await db.get(SourceVideo, video_id)
    if not video:
        raise ValueError(f"Source video {video_id} not found")

    video.status = "EXTRACTING_AUDIO"
    await db.commit()

    raw_video_path = resolve_path(video.local_file_path)
    audio_rel = f"audio/{video_id}.wav"
    audio_path = resolve_path(audio_rel)
    thumb_rel = f"thumbnails/{video_id}.jpg"
    thumb_path = resolve_path(thumb_rel)

    # 1. Probe video
    probe_info = await probe_video(raw_video_path)
    if not probe_info["has_audio"]:
        raise ValueError("No audio track present in uploaded file")

    video.duration_seconds = probe_info["duration"]

    # 2. Extract thumbnail
    if not os.path.exists(thumb_path):
        await generate_thumbnail(raw_video_path, thumb_path, seek_seconds=1.0)

    # 3. Extract audio
    await extract_audio(raw_video_path, audio_path)

    # 4. Enqueue next job: TRANSCRIBE
    next_job = AppJob(
        id=uuid.uuid4().hex,
        job_type="TRANSCRIBE",
        ref_id=video_id,
        status="QUEUED"
    )
    db.add(next_job)
    await db.commit()

async def handle_transcribe(job: AppJob, db: AsyncSession):
    video_id = job.ref_id
    video = await db.get(SourceVideo, video_id)
    if not video:
        raise ValueError(f"Source video {video_id} not found")

    video.status = "TRANSCRIBING"
    await db.commit()

    audio_path = resolve_path(f"audio/{video_id}.wav")
    transcript_rel = f"transcripts/{video_id}.json"
    transcript_path = resolve_path(transcript_rel)

    result = await transcribe_audio(audio_path, transcript_path)

    video.language = result.get("language")
    full_text = result.get("full_text", "")

    # Save or update transcript in DB
    existing_t = await db.scalar(select(Transcript).where(Transcript.video_id == video_id))
    if existing_t:
        existing_t.full_text = full_text
        existing_t.transcript_json_path = transcript_rel
    else:
        new_t = Transcript(
            id=uuid.uuid4().hex,
            video_id=video_id,
            full_text=full_text,
            transcript_json_path=transcript_rel
        )
        db.add(new_t)

    # Backfill hash dedup untuk video lama yang belum punya
    if not getattr(video, "file_hash", None):
        try:
            video.file_hash = hash_file_head(resolve_path(video.local_file_path))
        except Exception:
            pass

    # Enqueue next job: LLM_ANALYZE
    next_job = AppJob(
        id=uuid.uuid4().hex,
        job_type="LLM_ANALYZE",
        ref_id=video_id,
        status="QUEUED"
    )
    db.add(next_job)
    await db.commit()

async def handle_llm_analyze(job: AppJob, db: AsyncSession):
    video_id = job.ref_id
    video = await db.get(SourceVideo, video_id)
    if not video:
        raise ValueError(f"Source video {video_id} not found")

    video.status = "ANALYZING"
    await db.commit()

    transcript_path = resolve_path(f"transcripts/{video_id}.json")
    if not os.path.exists(transcript_path):
        raise ValueError("Transcript JSON file does not exist")

    with open(transcript_path, "r", encoding="utf-8") as f:
        t_data = json.load(f)

    segments = t_data.get("segments", [])

    # Fetch LLM settings
    base_url_s = await db.get(AppSetting, "llm_base_url")
    api_key_s = await db.get(AppSetting, "llm_api_key")
    model_s = await db.get(AppSetting, "llm_model")
    prompt_s = await db.get(AppSetting, "llm_prompt")
    connected_s = await db.get(AppSetting, "llm_connected")

    is_connected = bool(connected_s and connected_s.setting_value.lower() == "true")
    llm_base_url = (base_url_s.setting_value if base_url_s else None) if is_connected else None
    llm_api_key = None
    if is_connected and api_key_s:
        try:
            llm_api_key = decrypt_setting(api_key_s.setting_value) if api_key_s.is_encrypted else api_key_s.setting_value
        except Exception:
            llm_api_key = None
    llm_model = model_s.setting_value if model_s else "gpt-4o-mini"

    # Fetch clipping limits (payload override menang bila not None — jangan pakai rantai `or`)
    min_dur_s = await db.get(AppSetting, "min_clip_seconds")
    max_dur_s = await db.get(AppSetting, "max_clip_seconds")
    min_dur = float(min_dur_s.setting_value) if min_dur_s else float(settings.MIN_CLIP_SECONDS)
    max_dur = float(max_dur_s.setting_value) if max_dur_s else float(settings.MAX_CLIP_SECONDS)
    custom_prompt = prompt_s.setting_value if prompt_s else None

    try:
        job_payload = job.payload if isinstance(job.payload, dict) else {}
    except Exception:
        job_payload = {}
    payload_min = job_payload.get("min_dur", None)
    payload_max = job_payload.get("max_dur", None)
    payload_prompt = job_payload.get("custom_prompt_override", None)
    if payload_min is not None:
        try:
            v = float(payload_min)
            if v > 0:
                min_dur = v
        except (TypeError, ValueError):
            pass
    if payload_max is not None:
        try:
            v = float(payload_max)
            if v > 0:
                max_dur = v
        except (TypeError, ValueError):
            pass
    if max_dur < min_dur:
        max_dur = min_dur
    if isinstance(payload_prompt, str) and payload_prompt.strip():
        custom_prompt = payload_prompt.strip()[:4000]

    video_desc = getattr(video, "description", None)
    full_text = t_data.get("full_text") or t_data.get("text")

    two_pass_s = await db.get(AppSetting, "llm_two_pass_enabled")
    two_pass = bool(two_pass_s and str(two_pass_s.setting_value).lower() == "true")
    chunk_s = await db.get(AppSetting, "llm_chunk_strategy")
    chunk_strategy = str(chunk_s.setting_value).lower() if chunk_s and chunk_s.setting_value else "auto"
    if chunk_strategy not in ("auto", "single_pass", "chunked"):
        chunk_strategy = "auto"
    use_chunked = chunk_strategy == "chunked" or (
        chunk_strategy == "auto" and (video.duration_seconds or 0) >= 1800
    )
    llm_kwargs = dict(
        segments=segments,
        video_duration=video.duration_seconds,
        video_title=video.original_name,
        video_description=video_desc,
        full_text=full_text,
        llm_base_url=llm_base_url,
        llm_api_key=llm_api_key,
        llm_model=llm_model,
        custom_prompt=custom_prompt,
        min_dur=min_dur,
        max_dur=max_dur
    )

    # Vision pass opsional (Phase 4 — 2.1): boost momen visual. Gagal → None (text only).
    vision_boost = None
    vision_weight = 0.3
    try:
        vision_on_s = await db.get(AppSetting, "llm_vision_enabled")
        vision_on = bool(vision_on_s and str(vision_on_s.setting_value).lower() == "true")
    except Exception:
        vision_on = False
    if vision_on and llm_base_url:
        try:
            from app.services.vision_service import extract_visual_highlights, build_vision_boost
            vision_model_s = await db.get(AppSetting, "llm_vision_model")
            vision_weight_s = await db.get(AppSetting, "llm_vision_weight")
            vision_model = vision_model_s.setting_value.strip() if vision_model_s and vision_model_s.setting_value else llm_model
            try:
                vision_weight = max(0.0, min(1.0, float(vision_weight_s.setting_value))) if vision_weight_s else 0.3
            except (TypeError, ValueError):
                vision_weight = 0.3
            raw_video_path = resolve_path(video.local_file_path)
            vision_highlights = await extract_visual_highlights(
                raw_video_path, video.duration_seconds or 0.0,
                llm_base_url, llm_api_key, vision_model,
            )
            vision_boost = build_vision_boost(vision_highlights) or None
        except Exception as exc:
            logger.warning("Vision pass dilewati: %s", exc)
            vision_boost = None
    llm_kwargs["vision_boost"] = vision_boost
    llm_kwargs["vision_weight"] = vision_weight

    if use_chunked:
        highlights = await extract_highlights_chunked(**llm_kwargs, two_pass=two_pass)
    elif two_pass:
        highlights = await extract_highlights_two_pass(**llm_kwargs)
    else:
        highlights = await extract_highlights_with_llm(**llm_kwargs)

    created_clips = []
    for h in highlights:
        clip = ClipCandidate(
            id=uuid.uuid4().hex,
            video_id=video_id,
            title=h["title"],
            start_time_seconds=h["start_time_seconds"],
            end_time_seconds=h["end_time_seconds"],
            duration_seconds=h["duration_seconds"],
            hook_score=h["hook_score"],
            composite_score=int(h.get("composite_score", h["hook_score"])),
            speech_rate=float(h.get("speech_rate", 0.0)),
            keyword_density=float(h.get("keyword_density", 0.0)),
            virality_reason=h["virality_reason"],
            is_selected=False
        )
        db.add(clip)
        created_clips.append(clip)

    rec_preset_id = getattr(highlights, "recommended_preset_id", None)
    detected_type = getattr(highlights, "video_type", "umum")
    video.video_type = detected_type
    video.status = "READY"
    await db.commit()

    # If auto_generate_shorts is enabled on this video, automatically queue 9:16 vertical renders!
    if getattr(video, "auto_generate_shorts", False) and created_clips:
        for clip in created_clips:
            short_id = uuid.uuid4().hex
            out_filename = f"{short_id}_9x16.mp4"
            rel_path = f"exports/{out_filename}"
            settings_dict = default_render_settings()
            if rec_preset_id:
                settings_dict["preset_id"] = rec_preset_id

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
            render_job = AppJob(
                id=uuid.uuid4().hex,
                job_type="RENDER",
                ref_id=short_id,
                status="QUEUED",
                payload=settings_dict
            )
            db.add(render_job)
        await db.commit()

async def handle_render(job: AppJob, db: AsyncSession):
    short_id = job.ref_id
    short = await db.get(RenderedShort, short_id)
    if not short:
        raise ValueError(f"Rendered short {short_id} not found")

    clip = await db.get(ClipCandidate, short.clip_id)
    if not clip:
        raise ValueError(f"Clip candidate {short.clip_id} not found")

    video = await db.get(SourceVideo, clip.video_id)
    if not video:
        raise ValueError(f"Source video {clip.video_id} not found")

    short.render_status = "RENDERING"
    short.render_progress = 0
    await db.commit()

    settings_dict = short.render_settings or {}
    preset_id = settings_dict.get("preset_id")
    preset = None
    if preset_id:
        preset = await db.get(TextPreset, preset_id)

    def pick(key: str, preset_value, default):
        """
        Nilai eksplisit dari permintaan render selalu menang; 0 dan False dihormati.
        Preset hanya mengisi field yang tidak dikirim. Rantai `or` sebelumnya menelan
        nilai 0 sehingga mis. outline_width=0 tidak pernah bisa diterapkan.
        """
        if key in settings_dict and settings_dict[key] is not None:
            return settings_dict[key]
        return preset_value if preset_value is not None else default

    crop_mode = pick("crop_mode", preset.crop_mode if preset else None, "center")
    crop_offset_x = int(pick("crop_offset_x", preset.crop_offset_x if preset else None, 0))
    smart_deadzone = float(pick("smart_deadzone", preset.smart_deadzone if preset else None, DEFAULT_DEADZONE))
    smart_pan_seconds = float(pick("smart_pan_seconds", preset.smart_pan_seconds if preset else None, DEFAULT_PAN_SECONDS))
    framing_layout = str(pick("framing_layout", preset.framing_layout if preset else None, "single"))
    screen_mode = str(pick("screen_mode", preset.screen_mode if preset else None, "full"))
    person_shape = str(pick("person_shape", preset.person_shape if preset else None, "circle"))
    person_scale = float(pick("person_scale", preset.person_scale if preset else None, 0.45))
    person_offset_x = int(pick("person_offset_x", preset.person_offset_x if preset else None, 0))
    person_offset_y = int(pick("person_offset_y", preset.person_offset_y if preset else None, 0))
    screen_offset_x = int(pick("screen_offset_x", preset.screen_offset_x if preset else None, 0))
    screen_offset_y = int(pick("screen_offset_y", preset.screen_offset_y if preset else None, 0))
    screen_scale = float(pick("screen_scale", preset.screen_scale if preset else None, 1.0))
    screen_aspect = str(pick("screen_aspect", preset.screen_aspect if preset else None, "16:9"))
    video_filter = str(pick("video_filter", getattr(preset, "video_filter", None) if preset else None, "none") or "none")

    # Motion graphics overlay (Phase 3 — 3.1). Judul intro diambil dari judul klip.
    enable_intro_title = bool(pick("enable_intro_title", getattr(preset, "enable_intro_title", None) if preset else None, False))
    intro_title_duration = float(pick("intro_title_duration", getattr(preset, "intro_title_duration", None) if preset else None, 1.5))
    intro_title_style = str(pick("intro_title_style", getattr(preset, "intro_title_style", None) if preset else None, "fade_slide") or "fade_slide")
    enable_outro_cta = bool(pick("enable_outro_cta", getattr(preset, "enable_outro_cta", None) if preset else None, False))
    outro_cta_text = str(pick("outro_cta_text", getattr(preset, "outro_cta_text", None) if preset else None, "Follow untuk lebih banyak!") or "Follow untuk lebih banyak!")
    outro_cta_duration = float(pick("outro_cta_duration", getattr(preset, "outro_cta_duration", None) if preset else None, 2.0))
    enable_lower_third = bool(pick("enable_lower_third", getattr(preset, "enable_lower_third", None) if preset else None, False))
    lower_third_text = pick("lower_third_text", getattr(preset, "lower_third_text", None) if preset else None, None)
    sticker_rel = pick("sticker_path", getattr(preset, "sticker_path", None) if preset else None, None)
    sticker_position = str(pick("sticker_position", getattr(preset, "sticker_position", None) if preset else None, "top_right") or "top_right")
    sticker_scale = float(pick("sticker_scale", getattr(preset, "sticker_scale", None) if preset else None, 0.15))
    sticker_abs = None
    if isinstance(sticker_rel, str) and sticker_rel.strip():
        candidate = resolve_path(sticker_rel.strip())
        if os.path.exists(candidate):
            sticker_abs = candidate
        else:
            logger.warning("Stiker overlay tak ditemukan, dilewati: %s", sticker_rel)
    overlay_config = {
        "enable_intro_title": enable_intro_title,
        "intro_title": clip.title,
        "intro_title_duration": intro_title_duration,
        "intro_title_style": intro_title_style,
        "enable_outro_cta": enable_outro_cta,
        "outro_cta_text": outro_cta_text,
        "outro_cta_duration": outro_cta_duration,
        "enable_lower_third": enable_lower_third,
        "lower_third_text": lower_third_text,
        "sticker_abs": sticker_abs,
        "sticker_position": sticker_position,
        "sticker_scale": sticker_scale,
    }

    # Sound effects (Phase 3 — 3.2): trigger manual + aturan hook otomatis.
    from app.services.sfx_service import resolve_sfx_triggers
    sfx_on_hook = bool(pick("sfx_on_hook", getattr(preset, "sfx_on_hook", None) if preset else None, False))
    sfx_hook_sfx_id = pick("sfx_hook_sfx_id", getattr(preset, "sfx_hook_sfx_id", None) if preset else None, None)
    sfx_hook_threshold = int(pick("sfx_hook_threshold", getattr(preset, "sfx_hook_threshold", None) if preset else None, 90))
    manual_sfx = settings_dict.get("sfx_triggers") or []
    clip_score = clip.composite_score or clip.hook_score or 0
    try:
        sfx_triggers = await resolve_sfx_triggers(
            db, manual_sfx if isinstance(manual_sfx, list) else [],
            auto_sfx_id=sfx_hook_sfx_id if isinstance(sfx_hook_sfx_id, str) else None,
            auto_enabled=sfx_on_hook,
            auto_score=float(clip_score),
            auto_threshold=float(sfx_hook_threshold),
        )
    except Exception as exc:
        logger.warning("Resolve SFX gagal, lanjut tanpa SFX: %s", exc)
        sfx_triggers = []

    font = pick("font", preset.font if preset else None, "Poppins")
    font_size = int(pick("font_size", preset.font_size if preset else None, 44))
    active_color = pick("active_color", preset.active_color if preset else None, "#FFCC00")
    primary_color = pick("primary_color", preset.primary_color if preset else None, "#FFFFFF")
    subtitle_position = pick("subtitle_position", preset.subtitle_position if preset else None, "bottom")
    margin_v = pick("margin_v", preset.margin_v if preset else None, None)
    outline_width = int(pick("outline_width", preset.outline_width if preset else None, 2))
    shadow_depth = int(pick("shadow_depth", preset.shadow_depth if preset else None, 1))
    is_uppercase = bool(pick("is_uppercase", preset.is_uppercase if preset else None, False))
    motion_type = str(pick("motion_type", preset.motion_type if preset else None, "karaoke"))
    highlight_bg_color = str(pick("highlight_bg_color", preset.highlight_bg_color if preset else None, "#FFCC00"))
    enable_keyword_color = bool(pick("enable_keyword_color", preset.enable_keyword_color if preset else None, True))
    keyword_color = str(pick("keyword_color", preset.keyword_color if preset else None, "#10B981"))
    enable_dynamic_scaling = bool(pick("enable_dynamic_scaling", preset.enable_dynamic_scaling if preset else None, False))
    enable_emoji_injection = bool(pick("enable_emoji_injection", preset.enable_emoji_injection if preset else None, False))
    glow_effect = bool(pick("glow_effect", preset.glow_effect if preset else None, False))
    enable_vocal_dynamics = bool(pick("enable_vocal_dynamics", preset.enable_vocal_dynamics if preset else None, False))

    # Voiceover AI synthesis or resolution
    use_voiceover = bool(pick("use_voiceover", preset.use_voiceover if preset else None, False))
    narration_text = settings_dict.get("narration_text") or clip.narration_text
    narration_voice = pick("narration_voice", preset.narration_voice if preset else None, clip.narration_voice or "id-ID-ArdiNeural")
    voiceover_audio_path = None

    if use_voiceover and narration_text:
        if clip.narration_audio_path and os.path.exists(resolve_path(clip.narration_audio_path)):
            voiceover_audio_path = resolve_path(clip.narration_audio_path)
        else:
            try:
                voice_rel = f"tts/{clip.id}_{uuid.uuid4().hex[:6]}.mp3"
                voice_abs = resolve_path(voice_rel)
                await generate_speech(narration_text, voice_abs, voice=narration_voice)
                clip.narration_text = narration_text
                clip.narration_voice = narration_voice
                clip.narration_audio_path = voice_rel
                await db.commit()
                voiceover_audio_path = voice_abs
            except Exception as e:
                logger.error("Gagal mensintesis voiceover untuk render: %s", e)
                voiceover_audio_path = None

    # Background Music (BGM) track resolution
    audio_track_id = pick("audio_track_id", preset.audio_track_id if preset else None, None)
    bgm_volume = float(pick("bgm_volume", preset.bgm_volume if preset else None, 0.2))
    audio_mode = str(pick("audio_mode", preset.audio_mode if preset else None, "mix"))
    bgm_audio_path = None

    if audio_track_id:
        track = await db.get(AudioTrack, audio_track_id)
        if track and track.local_path:
            resolved_bgm = resolve_path(track.local_path)
            if os.path.exists(resolved_bgm):
                bgm_audio_path = resolved_bgm

    # 1. Read word timestamps from transcript JSON (with fallback synthesis)
    transcript_path = resolve_path(f"transcripts/{video.id}.json")
    all_words = []
    if os.path.exists(transcript_path):
        with open(transcript_path, "r", encoding="utf-8") as f:
            t_data = json.load(f)
            for seg in t_data.get("segments", []):
                words = seg.get("words", [])
                if words:
                    for w in words:
                        all_words.append(w)
                else:
                    text_words = seg.get("text", "").strip().split()
                    if text_words:
                        seg_s = float(seg.get("start", 0.0))
                        seg_e = float(seg.get("end", seg_s + 1.0))
                        seg_d = max(0.1, seg_e - seg_s)
                        w_dur = seg_d / len(text_words)
                        for i, tw in enumerate(text_words):
                            all_words.append({
                                "word": tw,
                                "start": round(seg_s + i * w_dur, 2),
                                "end": round(seg_s + (i + 1) * w_dur, 2),
                                "probability": 1.0
                            })

    # 1.5. If vocal dynamics is enabled, analyze audio loudness & energy profile per word
    if enable_vocal_dynamics and all_words:
        vocal_source_audio = voiceover_audio_path if voiceover_audio_path else resolve_path(f"audio/{video.id}.wav")
        all_words = analyze_vocal_dynamics(
            audio_path=vocal_source_audio,
            words=all_words,
            clip_start=clip.start_time_seconds,
            clip_end=clip.end_time_seconds
        )

    # 2. Generate ASS file
    ass_rel = f"subtitles/{clip.id}.ass"
    ass_path = resolve_path(ass_rel)
    generate_karaoke_ass(
        words=all_words,
        clip_start=clip.start_time_seconds,
        clip_end=clip.end_time_seconds,
        output_path=ass_path,
        font=font,
        font_size=font_size,
        active_color=active_color,
        primary_color=primary_color,
        position=subtitle_position,
        margin_v=margin_v,
        outline_width=outline_width,
        shadow_depth=shadow_depth,
        is_uppercase=is_uppercase,
        motion_type=motion_type,
        highlight_bg_color=highlight_bg_color,
        enable_keyword_color=enable_keyword_color,
        keyword_color=keyword_color,
        enable_dynamic_scaling=enable_dynamic_scaling,
        enable_emoji_injection=enable_emoji_injection,
        glow_effect=glow_effect,
        enable_vocal_dynamics=enable_vocal_dynamics,
        fallback_title=clip.title
    )

    # 3. Render 9:16 short with progress callback
    raw_video_path = resolve_path(video.local_file_path)
    output_path = resolve_path(short.local_path)

    # Smart reframe: resolve the head-tracking timeline into a crop expression.
    # Any failure degrades to a static crop instead of failing the job.
    crop_x_expr = None
    if crop_mode == "smart":
        try:
            probe_info = await probe_video(raw_video_path)
            crop_x_expr = await build_smart_crop_expression(
                video_path=raw_video_path,
                clip_start=clip.start_time_seconds,
                clip_end=clip.end_time_seconds,
                src_w=int(probe_info["width"]),
                src_h=int(probe_info["height"]),
                deadzone=float(settings_dict.get("smart_deadzone", DEFAULT_DEADZONE)),
                pan_seconds=float(settings_dict.get("smart_pan_seconds", DEFAULT_PAN_SECONDS)),
                fallback_offset=crop_offset_x,
                video_id=video.id,
                clip_id=clip.id,
                snap=bool(settings_dict.get("smart_snap", False))
            )
        except Exception as exc:
            logger.warning("Smart crop gagal disiapkan, memakai crop statis: %s", exc)
            crop_x_expr = None

    # Streamer face layout (Phase 3 — 5.2): pre-analysis posisi wajah untuk crop Y-aware.
    # Gagal → fallback ke split setara, JANGAN gagalkan job.
    face_cy_ratio = None
    if framing_layout in ("streamer_face_top", "streamer_face_bottom"):
        try:
            from app.services.reframe_service import analyze_face_anchor
            anchor = await analyze_face_anchor(
                raw_video_path, clip.start_time_seconds, clip.end_time_seconds
            )
            face_cy_ratio = float(anchor.get("avg_cy") or (0.25 if framing_layout == "streamer_face_top" else 0.75))
        except Exception as exc:
            logger.warning("Face anchor gagal, fallback ke split: %s", exc)
            framing_layout = "split_top_bottom" if framing_layout == "streamer_face_top" else "split_bottom_top"
            face_cy_ratio = None

    async def update_progress(pct: int):
        try:
            job.progress = pct
            short.render_progress = pct
            await db.commit()
        except Exception:
            pass

    await render_vertical_clip(
        video_path=raw_video_path,
        ass_path=ass_path,
        output_path=output_path,
        start_time=clip.start_time_seconds,
        end_time=clip.end_time_seconds,
        crop_mode=crop_mode,
        crop_offset_x=crop_offset_x,
        progress_callback=update_progress,
        crop_x_expr=crop_x_expr,
        voiceover_audio_path=voiceover_audio_path,
        bgm_audio_path=bgm_audio_path,
        bgm_volume=bgm_volume,
        audio_mode=audio_mode,
        framing_layout=framing_layout,
        person_offset_x=person_offset_x,
        person_offset_y=person_offset_y,
        screen_offset_x=screen_offset_x,
        screen_offset_y=screen_offset_y,
        screen_scale=screen_scale,
        screen_aspect=screen_aspect,
        screen_mode=screen_mode,
        person_shape=person_shape,
        person_scale=person_scale,
        video_filter=video_filter,
        overlay_config=overlay_config,
        sfx_triggers=sfx_triggers,
        face_cy_ratio=face_cy_ratio,
    )

    short.render_status = "COMPLETED"
    short.render_progress = 100
    if os.path.exists(output_path):
        short.file_size_bytes = os.path.getsize(output_path)
    await db.commit()

async def handle_gdrive_upload(job: AppJob, db: AsyncSession):
    export_id = job.ref_id
    export_rec = await db.get(GoogleDriveExport, export_id)
    if not export_rec:
        raise ValueError(f"Google Drive export record {export_id} not found")

    short = await db.get(RenderedShort, export_rec.short_id)
    if not short:
        raise ValueError(f"Rendered short {export_rec.short_id} not found")

    # Anti-double uploading check:
    if short.is_drive_uploaded and export_rec.gdrive_file_id:
        export_rec.upload_status = "SUCCESS"
        export_rec.upload_progress = 100
        await db.commit()
        return

    export_rec.upload_status = "UPLOADING"
    export_rec.upload_progress = 0
    await db.commit()

    # Read credentials from app_settings
    auth_type_s = await db.get(AppSetting, "gdrive_auth_type")
    auth_type = auth_type_s.setting_value if auth_type_s else "SERVICE_ACCOUNT"
    folder_s = await db.get(AppSetting, "gdrive_folder_id")
    folder_id = folder_s.setting_value if folder_s else ""

    creds_data = {}
    if auth_type == "SERVICE_ACCOUNT":
        sa_s = await db.get(AppSetting, "gdrive_sa_json")
        if not sa_s:
            raise ValueError("Google Drive Service Account belum dikonfigurasi")
        creds_data["service_account_json"] = decrypt_setting(sa_s.setting_value) if sa_s.is_encrypted else sa_s.setting_value
    else:
        cid = await db.get(AppSetting, "gdrive_client_id")
        csec = await db.get(AppSetting, "gdrive_client_secret")
        rt = await db.get(AppSetting, "gdrive_refresh_token")
        if not cid or not csec or not rt:
            raise ValueError("Kredensial OAuth2 Google Drive belum lengkap")
        creds_data["client_id"] = cid.setting_value
        creds_data["client_secret"] = decrypt_setting(csec.setting_value) if csec.is_encrypted else csec.setting_value
        creds_data["refresh_token"] = decrypt_setting(rt.setting_value) if rt.is_encrypted else rt.setting_value

    file_path = resolve_path(short.local_path)
    if not os.path.exists(file_path):
        raise ValueError(f"Berkas video {short.local_path} tidak ditemukan di storage")

    def sync_progress(pct: int):
        export_rec.upload_progress = pct

    res = await upload_file_to_drive(
        file_path=file_path,
        filename=short.output_filename,
        folder_id=folder_id,
        auth_type=auth_type,
        credentials_data=creds_data,
        progress_callback=sync_progress
    )

    export_rec.upload_status = "SUCCESS"
    export_rec.upload_progress = 100
    export_rec.gdrive_file_id = res["file_id"]
    export_rec.gdrive_web_view_link = res["web_view_link"]
    export_rec.uploaded_at = datetime.now(timezone.utc)
    
    # Mark short as uploaded to guard against double uploading!
    short.is_drive_uploaded = True
    await db.commit()
