import os
import json
import logging
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
from app.services.storage_service import resolve_path
from app.services.ffmpeg_service import probe_video, extract_audio, generate_thumbnail, render_vertical_clip
from app.services.ass_service import generate_karaoke_ass
from app.services.whisper_service import transcribe_audio
from app.services.llm_service import extract_highlights_with_llm
from app.services.tts_service import generate_speech
from app.services.gdrive_service import upload_file_to_drive
from app.services.reframe_service import (
    build_smart_crop_expression,
    DEFAULT_DEADZONE,
    DEFAULT_PAN_SECONDS,
)
from app.core.crypto import decrypt_setting
from app.config import settings

logger = logging.getLogger(__name__)


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
    custom_prompt = prompt_s.setting_value if prompt_s else None

    # Fetch clipping limits
    min_dur_s = await db.get(AppSetting, "min_clip_seconds")
    max_dur_s = await db.get(AppSetting, "max_clip_seconds")
    min_dur = float(min_dur_s.setting_value) if min_dur_s else float(settings.MIN_CLIP_SECONDS)
    max_dur = float(max_dur_s.setting_value) if max_dur_s else float(settings.MAX_CLIP_SECONDS)

    video_desc = getattr(video, "description", None)
    full_text = t_data.get("full_text") or t_data.get("text")

    highlights = await extract_highlights_with_llm(
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
            virality_reason=h["virality_reason"],
            is_selected=False
        )
        db.add(clip)
        created_clips.append(clip)

    video.status = "READY"
    await db.commit()

    # If auto_generate_shorts is enabled on this video, automatically queue 9:16 vertical renders!
    if getattr(video, "auto_generate_shorts", False) and created_clips:
        for clip in created_clips:
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

    async def update_progress(pct: int):
        job.progress = pct
        short.render_progress = pct
        await db.commit()

    def sync_progress_callback(pct: int):
        # We can update the job in background or let worker update
        short.render_progress = pct

    await render_vertical_clip(
        video_path=raw_video_path,
        ass_path=ass_path,
        output_path=output_path,
        start_time=clip.start_time_seconds,
        end_time=clip.end_time_seconds,
        crop_mode=crop_mode,
        crop_offset_x=crop_offset_x,
        progress_callback=sync_progress_callback,
        crop_x_expr=crop_x_expr,
        voiceover_audio_path=voiceover_audio_path,
        bgm_audio_path=bgm_audio_path,
        bgm_volume=bgm_volume,
        audio_mode=audio_mode
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
