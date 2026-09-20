from datetime import datetime
from sqlalchemy import Column, String, Text, Boolean, Integer, Float, BigInteger, DateTime, ForeignKey, JSON, Index, func
from sqlalchemy.orm import relationship
from app.database import Base

class AppSetting(Base):
    __tablename__ = "app_settings"

    setting_key = Column(String(50), primary_key=True)
    setting_value = Column(Text, nullable=False)
    is_encrypted = Column(Boolean, default=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class AuthPin(Base):
    __tablename__ = "auth_pin"

    id = Column(Integer, primary_key=True, autoincrement=True)
    pin_hash = Column(String(255), nullable=False)
    salt = Column(String(64), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class SourceVideo(Base):
    __tablename__ = "source_videos"

    id = Column(String(36), primary_key=True)  # UUID v4
    filename = Column(String(255), nullable=False)  # {id}.mp4
    original_name = Column(String(255), nullable=False)
    local_file_path = Column(String(500), nullable=False)  # uploads/{id}.mp4
    file_size_bytes = Column(BigInteger, nullable=False)
    duration_seconds = Column(Float, nullable=False, default=0.0)
    language = Column(String(10), nullable=True)
    video_type = Column(String(50), nullable=True)
    status = Column(String(30), nullable=False, default="UPLOADED")  # UPLOADED, EXTRACTING_AUDIO, TRANSCRIBING, ANALYZING, READY, FAILED
    error_message = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    auto_generate_shorts = Column(Boolean, default=False)
    file_hash = Column(String(64), nullable=True)  # SHA256 1MB pertama (dedup transkrip)
    source_url = Column(String(500), nullable=True)  # URL asal (YouTube) bila diunduh dari URL
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    transcript = relationship("Transcript", back_populates="video", uselist=False, cascade="all, delete-orphan")
    clips = relationship("ClipCandidate", back_populates="video", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_video_status", "status", "created_at"),
    )


class Transcript(Base):
    __tablename__ = "transcripts"

    id = Column(String(36), primary_key=True)  # UUID v4
    video_id = Column(String(36), ForeignKey("source_videos.id", ondelete="CASCADE"), unique=True, nullable=False)
    full_text = Column(Text, nullable=False)
    transcript_json_path = Column(String(500), nullable=False)  # transcripts/{video_id}.json
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    video = relationship("SourceVideo", back_populates="transcript")


class ClipCandidate(Base):
    __tablename__ = "clip_candidates"

    id = Column(String(36), primary_key=True)  # UUID v4
    video_id = Column(String(36), ForeignKey("source_videos.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(255), nullable=False)
    start_time_seconds = Column(Float, nullable=False)
    end_time_seconds = Column(Float, nullable=False)
    duration_seconds = Column(Float, nullable=False)
    hook_score = Column(Integer, default=0)
    composite_score = Column(Integer, default=0)
    speech_rate = Column(Float, default=0.0)
    keyword_density = Column(Float, default=0.0)
    face_coverage = Column(Float, default=0.0)
    virality_reason = Column(Text, nullable=True)
    is_selected = Column(Boolean, default=False)
    narration_text = Column(Text, nullable=True)
    narration_voice = Column(String(50), nullable=True)
    narration_audio_path = Column(String(500), nullable=True)
    seo_titles = Column(JSON, nullable=True)
    seo_description = Column(Text, nullable=True)
    seo_tags = Column(JSON, nullable=True)
    seo_hashtags = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    video = relationship("SourceVideo", back_populates="clips")
    rendered_shorts = relationship("RenderedShort", back_populates="clip", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_clip_video", "video_id", "hook_score"),
    )


class RenderedShort(Base):
    __tablename__ = "rendered_shorts"

    id = Column(String(36), primary_key=True)  # UUID v4
    clip_id = Column(String(36), ForeignKey("clip_candidates.id", ondelete="CASCADE"), nullable=False)
    output_filename = Column(String(255), nullable=False)  # {short_id}_9x16.mp4
    local_path = Column(String(500), nullable=False)  # exports/{short_id}_9x16.mp4
    file_size_bytes = Column(BigInteger, default=0)
    render_settings = Column(JSON, nullable=True)
    render_status = Column(String(30), default="PENDING")  # PENDING, RENDERING, COMPLETED, FAILED
    render_progress = Column(Integer, default=0)  # 0..100
    is_drive_uploaded = Column(Boolean, default=False)  # Guard against double uploading!
    is_youtube_uploaded = Column(Boolean, default=False)  # Guard against double uploading to YouTube!
    thumbnail_path = Column(String(500), nullable=True)  # thumbnails/{short_id}.jpg
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    clip = relationship("ClipCandidate", back_populates="rendered_shorts")
    exports = relationship("GoogleDriveExport", back_populates="short", cascade="all, delete-orphan")
    youtube_exports = relationship("YouTubeExport", back_populates="short", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_short_status", "render_status"),
    )


class GoogleDriveExport(Base):
    __tablename__ = "google_drive_exports"

    id = Column(String(36), primary_key=True)  # UUID v4
    short_id = Column(String(36), ForeignKey("rendered_shorts.id", ondelete="CASCADE"), nullable=False)
    gdrive_file_id = Column(String(150), nullable=True)
    gdrive_web_view_link = Column(Text, nullable=True)
    upload_status = Column(String(30), default="QUEUED")  # QUEUED, UPLOADING, SUCCESS, FAILED
    upload_progress = Column(Integer, default=0)  # 0..100
    error_message = Column(Text, nullable=True)
    uploaded_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    short = relationship("RenderedShort", back_populates="exports")


class YouTubeExport(Base):
    """Riwayat upload ke YouTube (Phase 5 — 8.1)."""
    __tablename__ = "youtube_exports"

    id = Column(String(36), primary_key=True)  # UUID v4
    short_id = Column(String(36), ForeignKey("rendered_shorts.id", ondelete="CASCADE"), nullable=False)
    youtube_video_id = Column(String(20), nullable=True)
    youtube_url = Column(String(200), nullable=True)
    title = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    tags = Column(JSON, nullable=True)
    hashtags = Column(JSON, nullable=True)
    privacy_status = Column(String(20), default="public")  # public, unlisted, private
    category_id = Column(String(5), default="22")
    made_for_kids = Column(Boolean, default=False)  # True jika khusus anak-anak, False untuk semua kalangan umur
    custom_thumbnail_path = Column(String(500), nullable=True)
    upload_status = Column(String(30), default="QUEUED")  # QUEUED, UPLOADING, SUCCESS, FAILED
    upload_progress = Column(Integer, default=0)  # 0..100
    error_message = Column(Text, nullable=True)
    uploaded_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    short = relationship("RenderedShort", back_populates="youtube_exports")

    __table_args__ = (
        Index("idx_export_status", "upload_status"),
    )


class AppJob(Base):
    __tablename__ = "app_jobs"

    id = Column(String(36), primary_key=True)  # UUID v4
    job_type = Column(String(30), nullable=False)  # AUDIO_EXTRACT, TRANSCRIBE, LLM_ANALYZE, RENDER, GDRIVE_UPLOAD
    ref_id = Column(String(36), nullable=False)  # video_id / clip_id / short_id
    status = Column(String(30), default="QUEUED")  # QUEUED, RUNNING, COMPLETED, FAILED, CANCELLED
    progress = Column(Integer, default=0)
    attempts = Column(Integer, default=0)
    max_attempts = Column(Integer, default=3)
    payload = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_job_status", "status", "created_at"),
        Index("idx_job_ref", "ref_id"),
    )


class TTSGeneration(Base):
    __tablename__ = "tts_generations"

    id = Column(String(36), primary_key=True)  # UUID v4
    text = Column(Text, nullable=False)
    voice = Column(String(100), default="id-ID-ArdiNeural")
    local_path = Column(String(500), nullable=False)  # tts/{id}.mp3
    file_size_bytes = Column(BigInteger, default=0)
    duration_seconds = Column(Float, default=0.0)
    status = Column(String(30), default="COMPLETED")
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class TextPreset(Base):
    __tablename__ = "text_presets"

    id = Column(String(36), primary_key=True)  # UUID v4
    name = Column(String(100), nullable=False)
    description = Column(String(255), nullable=True)

    # 1. Visual Framing
    crop_mode = Column(String(20), default="center")  # smart, center, manual
    crop_offset_x = Column(Integer, default=0)
    smart_deadzone = Column(Float, default=0.5)
    smart_pan_seconds = Column(Float, default=0.5)
    framing_layout = Column(String(30), default="single")  # single, pip_full, pip_center, split_top_bottom, split_bottom_top, fit_16_9_center
    screen_mode = Column(String(20), default="full")  # full, center
    person_shape = Column(String(20), default="circle")  # circle, rounded, rectangle
    person_scale = Column(Float, default=0.35)  # Scale for PIP overlay (0.15 - 1.0)
    person_offset_x = Column(Integer, default=0)
    person_offset_y = Column(Integer, default=0)
    screen_offset_x = Column(Integer, default=0)
    screen_offset_y = Column(Integer, default=0)
    screen_scale = Column(Float, default=1.0)
    screen_aspect = Column(String(10), default="16:9")
    video_filter = Column(String(20), default="none")  # none, cinematic, vivid, warm, cool, drama, vintage

    # 2. Text & Subtitles Styling
    font = Column(String(100), default="Poppins")
    font_size = Column(Integer, default=44)
    primary_color = Column(String(20), default="#FFFFFF")
    active_color = Column(String(20), default="#FFCC00")
    subtitle_position = Column(String(20), default="bottom")  # bottom, middle, top, custom
    margin_v = Column(Integer, default=340)  # Vertical Y offset in pixels
    outline_width = Column(Integer, default=3)
    shadow_depth = Column(Integer, default=1)
    is_uppercase = Column(Boolean, default=False)

    # Subtitle Motion & Visual Emphasis
    motion_type = Column(String(30), default="karaoke")  # single_word_pop, karaoke, background_box, typewriter, slide_up, bounce_in, zoom_flash, glitch_reveal
    highlight_bg_color = Column(String(20), default="#FFCC00")
    enable_keyword_color = Column(Boolean, default=True)
    keyword_color = Column(String(20), default="#10B981")
    enable_dynamic_scaling = Column(Boolean, default=False)
    enable_emoji_injection = Column(Boolean, default=False)
    glow_effect = Column(Boolean, default=False)
    enable_vocal_dynamics = Column(Boolean, default=False)

    # 2b. Motion Graphics Overlay (Phase 3 — 3.1), semua default OFF
    enable_intro_title = Column(Boolean, default=False)
    intro_title_duration = Column(Float, default=2.0)
    intro_title_style = Column(String(20), default="fade_slide")
    intro_title_tts = Column(Boolean, default=True)
    intro_title_voice = Column(String(50), default="id-ID-ArdiNeural")
    intro_title_pause = Column(Boolean, default=False)
    enable_outro_cta = Column(Boolean, default=False)
    outro_cta_text = Column(String(255), default="Follow untuk lebih banyak!")
    outro_cta_duration = Column(Float, default=2.0)
    enable_lower_third = Column(Boolean, default=False)
    lower_third_text = Column(String(255), nullable=True)
    sticker_path = Column(String(500), nullable=True)
    sticker_position = Column(String(20), default="top_right")
    sticker_scale = Column(Float, default=0.15)

    # 2c. Sound Effect auto-trigger (Phase 3 — 3.2)
    sfx_on_hook = Column(Boolean, default=False)
    sfx_hook_sfx_id = Column(String(36), nullable=True)
    sfx_hook_threshold = Column(Integer, default=90)

    # 3. Audio & Voiceover
    audio_track_id = Column(String(36), nullable=True)
    bgm_volume = Column(Float, default=0.2)
    audio_mode = Column(String(20), default="mix")  # mix, replace, original
    use_voiceover = Column(Boolean, default=False)
    narration_voice = Column(String(100), default="id-ID-ArdiNeural")
    narration_style = Column(String(50), default="hook_story")

    # Meta
    is_builtin = Column(Boolean, default=False)
    category = Column(String(20), default="text")  # text, full, streamer, podcast, educational, motivational, gaming
    thumbnail_preview = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AudioTrack(Base):
    __tablename__ = "audio_tracks"

    id = Column(String(36), primary_key=True)  # UUID v4
    title = Column(String(255), nullable=False)
    source_type = Column(String(20), default="UPLOAD")  # UPLOAD, YOUTUBE, BUILTIN
    source_url = Column(String(500), nullable=True)
    local_path = Column(String(500), nullable=False)  # audio/{id}.mp3
    duration_seconds = Column(Float, default=0.0)
    file_size_bytes = Column(BigInteger, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class SFXTrack(Base):
    """Sound effect pendek untuk trigger momen (Phase 3 — 3.2)."""
    __tablename__ = "sfx_tracks"

    id = Column(String(36), primary_key=True)  # UUID v4
    title = Column(String(255), nullable=False)
    local_path = Column(String(500), nullable=False)  # sfx/{id}.mp3
    duration_seconds = Column(Float, default=0.0)
    file_size_bytes = Column(BigInteger, default=0)
    is_builtin = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

