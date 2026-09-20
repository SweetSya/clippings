from datetime import datetime
from typing import Generic, TypeVar, Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator
import re

T = TypeVar("T")

# ----------------- Error & Pagination -----------------
class ErrorDetail(BaseModel):
    code: str
    message: str
    detail: Optional[Any] = None

class ErrorEnvelope(BaseModel):
    error: ErrorDetail

class PaginatedResponse(BaseModel, Generic[T]):
    items: List[T]
    page: int
    limit: int
    total: int

# ----------------- Auth Schemas -----------------
class PinSetupRequest(BaseModel):
    pin: str = Field(..., description="4-8 digit numeric PIN")

    @field_validator("pin")
    @classmethod
    def validate_pin(cls, v: str) -> str:
        if not re.match(r"^\d{4,8}$", v):
            raise ValueError("PIN must be 4 to 8 digits numeric only")
        return v

class PinLoginRequest(BaseModel):
    pin: str

class AuthStatusResponse(BaseModel):
    is_configured: bool
    has_session: bool

class TokenResponse(BaseModel):
    token: str
    token_type: str = "Bearer"

# ----------------- Settings Schemas -----------------
class AISettingsRequest(BaseModel):
    base_url: str = Field(..., description="OpenAI-compatible base URL")
    api_key: Optional[str] = None
    model_name: str = Field("gpt-4o-mini", description="Model name")
    temperature: float = 0.4
    prompt: Optional[str] = None
    two_pass_enabled: Optional[bool] = Field(None, description="Sequential two-pass LLM strategy")
    chunk_strategy: Optional[str] = Field(None, description="'auto', 'single_pass', or 'chunked'")
    vision_enabled: Optional[bool] = Field(None, description="Vision-aware clipping pass")
    vision_model: Optional[str] = Field(None, description="Vision-capable model (default: text model)")
    vision_weight: Optional[float] = Field(None, ge=0.0, le=1.0, description="Bobot boost visual")

    @field_validator("chunk_strategy")
    @classmethod
    def validate_chunk_strategy(cls, v):
        if v is None:
            return v
        norm = str(v).strip().lower()
        if norm not in ("auto", "single_pass", "chunked"):
            raise ValueError("chunk_strategy harus salah satu: auto, single_pass, chunked")
        return norm

class GDriveSettingsRequest(BaseModel):
    auth_type: str = Field("OAUTH2", description="OAUTH2 or SERVICE_ACCOUNT")
    credentials_json: Optional[str] = Field(None, description="Raw JSON: OAuth2 client_secret or Service Account")
    service_account_json: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    refresh_token: Optional[str] = None
    target_folder_id: str = Field(..., description="Google Drive Folder ID")

class GDriveOAuthUrlResponse(BaseModel):
    auth_url: str
    redirect_uri: str

class GDriveOAuthExchangeRequest(BaseModel):
    code: str
    redirect_uri: Optional[str] = None

class GeneralSettingsRequest(BaseModel):
    min_clip_seconds: int = Field(10, ge=5, le=180, description="Minimum clip duration in seconds")
    max_clip_seconds: int = Field(60, ge=10, le=300, description="Maximum clip duration in seconds")
    yt_quality: str = Field("1080p", description="Default YouTube quality: '1080p', '720p', or 'best'")
    whisper_language: str = Field("auto", description="Whisper language: 'auto' or ISO code (id, en, ms, ...)")

class YouTubeCookiesStatusResponse(BaseModel):
    has_cookies: bool
    file_path: Optional[str] = None
    file_size_bytes: int = 0
    line_count: int = 0

class YouTubeCookiesSaveRequest(BaseModel):
    cookies_content: str = Field(..., description="Raw Netscape cookies.txt content")

class AITestRequest(BaseModel):
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    model_name: Optional[str] = None

class AITestResponse(BaseModel):
    ok: bool
    message: Optional[str] = None
    error: Optional[str] = None
    model: Optional[str] = None

class UIPreferencesRequest(BaseModel):
    clip_view_mode: Optional[str] = Field(None, description="'grid' or 'list'")
    shorts_view_mode: Optional[str] = Field(None, description="'grid' or 'list'")

class BatchDeleteRequest(BaseModel):
    ids: List[str] = Field(..., min_length=1, description="List of IDs")

class BatchClipRenderRequest(BaseModel):
    clip_ids: List[str] = Field(..., min_length=1, description="List of clip candidate IDs to render in background queue")
    render_settings: Optional['ClipRenderRequest'] = Field(None, description="Optional common render settings to apply to all clips")

class BatchActionResponse(BaseModel):
    success_count: int
    failed_count: int = 0
    message: str

class JobItem(BaseModel):
    id: str
    job_type: str
    ref_id: str
    ref_kind: str = "unknown"
    ref_label: str = ""
    status: str
    progress: int = 0
    attempts: int = 0
    max_attempts: int = 3
    error_message: Optional[str] = None
    created_at: str = ""
    started_at: Optional[str] = None
    finished_at: Optional[str] = None

class SettingsResponse(BaseModel):
    llm_base_url: Optional[str] = None
    llm_model: Optional[str] = None
    llm_configured: bool = False
    llm_connected: bool = False
    llm_prompt: Optional[str] = None
    llm_two_pass_enabled: bool = False
    llm_chunk_strategy: str = "auto"
    llm_vision_enabled: bool = False
    llm_vision_model: Optional[str] = None
    llm_vision_weight: float = 0.3
    gdrive_auth_type: Optional[str] = "OAUTH2"
    gdrive_folder_id: Optional[str] = None
    gdrive_configured: bool = False
    gdrive_client_id: Optional[str] = None
    gdrive_oauth_connected: bool = False
    gdrive_redirect_uri: Optional[str] = None
    min_clip_seconds: int = 10
    max_clip_seconds: int = 60
    yt_quality: str = "1080p"
    whisper_language: str = "auto"
    clip_view_mode: str = "grid"
    shorts_view_mode: str = "grid"
    youtube_auto_upload: bool = False
    youtube_default_privacy: str = "public"
    youtube_default_category: str = "22"
    youtube_default_made_for_kids: bool = False
    youtube_connected: bool = False
    youtube_client_id: Optional[str] = None

class GDriveTestResponse(BaseModel):
    ok: bool
    folder_name: Optional[str] = None
    error: Optional[str] = None

# ----------------- Video Schemas -----------------
class VideoUploadResponse(BaseModel):
    video_id: str
    filename: str
    original_name: str
    duration_seconds: float
    file_size_bytes: int
    auto_generate_shorts: bool = False

class VideoListItem(BaseModel):
    id: str
    original_name: str
    status: str
    duration_seconds: float
    file_size_bytes: int
    language: Optional[str] = None
    thumbnail_url: str
    created_at: str
    description: Optional[str] = None
    video_type: Optional[str] = None
    clips_count: int = 0
    rendered_count: int = 0
    auto_generate_shorts: bool = False

class VideoStatusResponse(BaseModel):
    video_id: str
    status: str
    error_message: Optional[str] = None
    job_progress: Dict[str, int] = Field(default_factory=dict)

class TranscriptResponse(BaseModel):
    video_id: str
    full_text: str
    language: Optional[str] = None
    json_url: str

class TranscriptSegmentItem(BaseModel):
    start: float = Field(..., ge=0)
    end: float = Field(..., ge=0)
    text: str = Field(..., max_length=2000)

    @field_validator("end")
    @classmethod
    def validate_end(cls, v, info):
        start = info.data.get("start") if hasattr(info, "data") else None
        if start is not None and v <= start:
            raise ValueError("end harus > start")
        return v

class TranscriptSegmentsResponse(BaseModel):
    video_id: str
    language: Optional[str] = None
    count: int = 0
    segments: List[TranscriptSegmentItem] = Field(default_factory=list)

class TranscriptSegmentsUpdate(BaseModel):
    segments: List[TranscriptSegmentItem] = Field(..., min_length=1, max_length=5000)

class RetranscribeRequest(BaseModel):
    language: Optional[str] = Field(None, max_length=10, description="'auto' atau kode bahasa; kosong = pakai setting global")

class YouTubeInfoRequest(BaseModel):
    url: str

class YouTubeInfoResponse(BaseModel):
    id: Optional[str] = None
    title: str
    duration_seconds: float
    thumbnail_url: Optional[str] = None
    channel: Optional[str] = None
    webpage_url: str
    description: Optional[str] = None

class YouTubeDownloadRequest(BaseModel):
    url: str
    quality: Optional[str] = Field("1080p", description="'1080p', '720p', or 'best'")
    auto_generate: bool = False

class ReanalyzeRequest(BaseModel):
    min_dur: Optional[float] = Field(None, gt=0, le=600, description="Durasi minimum klip (detik)")
    max_dur: Optional[float] = Field(None, gt=0, le=600, description="Durasi maksimum klip (detik)")
    custom_prompt_override: Optional[str] = Field(None, max_length=4000, description="Prompt kustom sekali pakai")

    @field_validator("max_dur")
    @classmethod
    def validate_range(cls, v, info):
        min_v = info.data.get("min_dur") if hasattr(info, "data") else None
        if v is not None and min_v is not None and v < min_v:
            raise ValueError("max_dur harus >= min_dur")
        return v

# ----------------- Clip Schemas -----------------
class ClipCandidateResponse(BaseModel):
    id: str
    video_id: str
    title: str
    start_time_seconds: float
    end_time_seconds: float
    duration_seconds: float
    hook_score: int
    composite_score: int = 0
    speech_rate: float = 0.0
    keyword_density: float = 0.0
    face_coverage: float = 0.0
    virality_reason: Optional[str] = None
    is_selected: bool
    narration_text: Optional[str] = None
    narration_voice: Optional[str] = None
    narration_audio_path: Optional[str] = None
    seo_titles: Optional[List[str]] = None
    seo_description: Optional[str] = None
    seo_tags: Optional[List[str]] = None
    seo_hashtags: Optional[List[str]] = None
    created_at: str

class ClipUpdateRequest(BaseModel):
    is_selected: Optional[bool] = None
    title: Optional[str] = None
    start_time_seconds: Optional[float] = None
    end_time_seconds: Optional[float] = None
    narration_text: Optional[str] = None
    narration_voice: Optional[str] = None

class SFXTriggerRequest(BaseModel):
    sfx_id: str = Field(..., description="ID SFX di library")
    start_t: float = Field(0.0, ge=0.0, le=3600.0, description="Offset detik dalam klip")
    volume: float = Field(0.8, ge=0.0, le=2.0, description="Volume 0.0-2.0")

class ClipRenderRequest(BaseModel):
    crop_mode: str = Field("center", description="'center', 'manual', or 'smart'")
    crop_offset_x: int = Field(0, description="Horizontal crop offset X in px")
    smart_deadzone: float = Field(0.5, ge=0.1, le=0.9, description="Fraction of crop width the head may move freely")
    smart_pan_seconds: float = Field(0.5, ge=0.0, le=2.0, description="Seconds the crop takes to pan; also the minimum gap between snaps")
    smart_snap: bool = Field(False, description="True cuts instantly to the subject instead of panning smoothly")
    framing_layout: Optional[str] = Field("single", description="'single', 'pip_full', 'pip_center', 'split_top_bottom', 'split_bottom_top', or 'fit_16_9_center'")
    screen_mode: Optional[str] = Field("full", description="'full' (fill 9:16) or 'center' (fit 16:9 ambient blur)")
    person_shape: Optional[str] = Field("circle", description="'circle', 'rounded', or 'rectangle'")
    person_scale: Optional[float] = Field(0.35, ge=0.15, le=1.5, description="Person facecam crop scale relative to frame")
    person_offset_x: Optional[int] = Field(0, description="Person crop horizontal offset in px (-500..500)")
    person_offset_y: Optional[int] = Field(0, description="Person crop vertical offset in px (-800..800)")
    screen_offset_x: Optional[int] = Field(0, description="Screen content horizontal offset in px (-500..500)")
    screen_offset_y: Optional[int] = Field(0, description="Screen content vertical offset in px (-500..500)")
    screen_scale: Optional[float] = Field(1.0, ge=0.5, le=1.5, description="Screen content zoom scale (0.5..1.5)")
    screen_aspect: Optional[str] = Field("16:9", description="'16:9' or '9:16'")
    video_filter: Optional[str] = Field("none", description="'none', 'cinematic', 'vivid', 'warm', 'cool', 'drama', or 'vintage'")
    preset_id: Optional[str] = Field(None, description="Preset ID if using a saved preset")
    font: str = Field("Poppins", description="Font name")
    font_size: int = Field(44, description="Font size")
    active_color: str = Field("#FFCC00", description="Active word karaoke color hex")
    primary_color: str = Field("#FFFFFF", description="Base caption color hex")
    subtitle_position: str = Field("bottom", description="'bottom', 'middle', or 'top'")
    margin_v: Optional[int] = Field(None, description="Custom vertical margin in px")
    outline_width: int = Field(3, description="Outline width in px")
    shadow_depth: int = Field(1, description="Shadow depth in px")
    is_uppercase: bool = Field(False, description="Uppercase subtitle text")
    
    # Subtitle Motion & Visual Emphasis
    motion_type: Optional[str] = Field("karaoke", description="'single_word_pop', 'karaoke', 'background_box', 'typewriter', 'slide_up', 'bounce_in', 'zoom_flash', or 'glitch_reveal'")
    highlight_bg_color: Optional[str] = Field("#FFCC00", description="Background color for background_box sticker")
    enable_keyword_color: Optional[bool] = Field(True, description="Enable auto-color shift on key words")
    keyword_color: Optional[str] = Field("#10B981", description="Contrasting color for key words")
    enable_dynamic_scaling: Optional[bool] = Field(False, description="Scale key words slightly larger (125%)")
    enable_emoji_injection: Optional[bool] = Field(False, description="Automatically prepend smart emojis to key phrases")
    glow_effect: Optional[bool] = Field(False, description="Glow / neon effect outline")
    enable_vocal_dynamics: Optional[bool] = Field(False, description="Auto-detect voice loudness/energy emphasis and dynamically resize text")

    # Audio & Voiceover fields
    use_voiceover: bool = Field(False, description="Whether to use AI voiceover narration")
    narration_text: Optional[str] = Field(None, description="Narration text to speak")
    narration_voice: Optional[str] = Field("id-ID-ArdiNeural", description="Voice ID for narration")
    audio_track_id: Optional[str] = Field(None, description="Selected BGM audio track ID")
    bgm_volume: float = Field(0.2, ge=0.0, le=1.0, description="Background music volume (0.0 - 1.0)")
    audio_mode: str = Field("mix", description="'mix' (duck original for voiceover/bgm), 'replace' (replace original audio), 'original'")
    video_filter: Optional[str] = Field("none", description="'none', 'cinematic', 'vivid', 'warm', 'cool', 'drama', or 'vintage'")
    enable_intro_title: Optional[bool] = Field(False, description="Tampilkan judul klip di awal")
    intro_title_duration: Optional[float] = Field(2.0, ge=0.5, le=5.0)
    intro_title_style: Optional[str] = Field("fade_slide", description="'fade_slide', 'pop', or 'typewriter'")
    intro_title_tts: Optional[bool] = Field(True, description="Bacakan judul singkat dengan audio AI")
    intro_title_voice: Optional[str] = Field("id-ID-ArdiNeural", description="Voice ID untuk audio AI intro")
    intro_title_pause: Optional[bool] = Field(False, description="Freeze frame jeda sejenak saat opening intro")
    enable_outro_cta: Optional[bool] = Field(False, description="Tampilkan CTA di akhir")
    outro_cta_text: Optional[str] = Field("Follow untuk lebih banyak!", max_length=255)
    outro_cta_duration: Optional[float] = Field(2.0, ge=0.5, le=10.0)
    enable_lower_third: Optional[bool] = Field(False, description="Strip nama pembicara")
    lower_third_text: Optional[str] = Field(None, max_length=255)
    sticker_path: Optional[str] = Field(None, description="Path stiker di storage/stickers/")
    sticker_position: Optional[str] = Field("top_right")
    sticker_scale: Optional[float] = Field(0.15, ge=0.05, le=0.5)
    sfx_triggers: Optional[List[SFXTriggerRequest]] = Field(None, description="Trigger SFX manual")

# ----------------- Smart Reframe Schemas -----------------
class HeadSampleItem(BaseModel):
    t: float
    cx: float

class CropKeyframeItem(BaseModel):
    t: float
    x: int
    head_cx: Optional[float] = None

class ReframePreviewResponse(BaseModel):
    clip_start: float
    clip_end: float
    duration: float
    src_width: int
    src_height: int
    crop_width: int
    max_offset_x: int
    deadzone: float
    snap: bool = False
    detected: bool
    coverage: float
    head_samples: List[HeadSampleItem]
    keyframes: List[CropKeyframeItem]

class FaceAnchorResponse(BaseModel):
    clip_id: str
    dominant_zone: str = "center"
    avg_cx: float = 0.5
    avg_cy: float = 0.5
    face_coverage: float = 0.0
    recommended_layout: str = "single"
    recommended_preset_id: Optional[str] = None
    warning: Optional[str] = None

# ----------------- Short & Export Schemas -----------------
class RenderedShortItem(BaseModel):
    id: str
    clip_id: str
    video_id: Optional[str] = None
    title: Optional[str] = None
    output_filename: str
    file_size_bytes: int
    render_status: str
    render_progress: int
    is_drive_uploaded: bool
    is_youtube_uploaded: bool = False
    source_url: Optional[str] = None
    source_title: Optional[str] = None
    download_url: str
    thumbnail_url: Optional[str] = None
    created_at: str
    gdrive: Optional[Dict[str, Any]] = None

class GDriveUploadResponse(BaseModel):
    export_id: str
    status: str

class GDriveUploadStatusResponse(BaseModel):
    export_id: str
    upload_status: str
    upload_progress: int
    gdrive_file_id: Optional[str] = None
    gdrive_web_view_link: Optional[str] = None
    error_message: Optional[str] = None

# ----------------- YouTube Upload Schemas (Phase 5 — 8.1) -----------------
class YouTubeSettingsRequest(BaseModel):
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    auto_upload: Optional[bool] = None
    default_privacy: Optional[str] = "public"
    default_category: Optional[str] = "22"
    made_for_kids: Optional[bool] = False

class YouTubeConfigResponse(BaseModel):
    client_id: Optional[str] = None
    auto_upload: bool = False
    default_privacy: str = "public"
    default_category: str = "22"
    made_for_kids: bool = False
    connected: bool = False
    channel_name: Optional[str] = None
    channel_id: Optional[str] = None

class YouTubeOAuthUrlResponse(BaseModel):
    auth_url: str
    redirect_uri: str

class YouTubeOAuthExchangeRequest(BaseModel):
    code: str
    redirect_uri: Optional[str] = None

class YouTubeChannelInfo(BaseModel):
    ok: bool
    channel_name: Optional[str] = None
    channel_id: Optional[str] = None
    subscriber_count: Optional[str] = None
    error: Optional[str] = None

class YouTubeUploadRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field("", max_length=5000)
    tags: Optional[List[str]] = Field(default_factory=list, max_length=15)
    hashtags: Optional[List[str]] = Field(default_factory=list, max_length=10)
    privacy_status: str = Field("public", description="'public', 'unlisted', or 'private'")
    category_id: str = Field("22", max_length=5)
    custom_thumbnail_path: Optional[str] = None
    made_for_kids: Optional[bool] = Field(False, description="Apakah konten khusus anak-anak? False = untuk semua kalangan umur")

    @field_validator("privacy_status")
    @classmethod
    def validate_privacy(cls, v: str) -> str:
        norm = str(v or "public").strip().lower()
        if norm not in ("public", "unlisted", "private"):
            raise ValueError("privacy_status harus public, unlisted, atau private")
        return norm

class YouTubeExportResponse(BaseModel):
    export_id: str
    status: str

class YouTubeUploadStatusResponse(BaseModel):
    export_id: str
    upload_status: str
    upload_progress: int
    youtube_video_id: Optional[str] = None
    youtube_url: Optional[str] = None
    error_message: Optional[str] = None

# ----------------- TTS Schemas -----------------
class TTSGenerateRequest(BaseModel):
    text: str = Field(..., min_length=1, description="Text to convert to speech")
    voice: str = Field("id-ID-ArdiNeural", description="Voice name (e.g. id-ID-ArdiNeural, id-ID-GadisNeural, en-US-ChristopherNeural)")
    rate: str = Field("+0%", description="Rate adjustment e.g. +10% or -10%")
    pitch: str = Field("+0Hz", description="Pitch adjustment e.g. +5Hz")

class TTSResponse(BaseModel):
    id: str
    text: str
    voice: str
    audio_url: str
    file_size_bytes: int
    duration_seconds: float
    created_at: str

# ----------------- Text / Unified Preset Schemas -----------------
class TextPresetResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    crop_mode: str = "center"
    crop_offset_x: int = 0
    smart_deadzone: float = 0.5
    smart_pan_seconds: float = 0.5
    framing_layout: str = "single"
    screen_mode: str = "full"
    person_shape: str = "circle"
    person_scale: float = 0.45
    person_offset_x: int = 0
    person_offset_y: int = 0
    screen_offset_x: int = 0
    screen_offset_y: int = 0
    screen_scale: float = 1.0
    screen_aspect: str = "16:9"
    video_filter: str = "none"
    font: str = "Poppins"
    font_size: int = 44
    primary_color: str = "#FFFFFF"
    active_color: str = "#FFCC00"
    subtitle_position: str = "bottom"
    margin_v: Optional[int] = 340
    outline_width: int = 3
    shadow_depth: int = 1
    is_uppercase: bool = False
    motion_type: str = "karaoke"
    highlight_bg_color: str = "#FFCC00"
    enable_keyword_color: bool = True
    keyword_color: str = "#10B981"
    enable_dynamic_scaling: bool = False
    enable_emoji_injection: bool = False
    glow_effect: bool = False
    enable_vocal_dynamics: bool = False
    audio_track_id: Optional[str] = None
    bgm_volume: float = 0.2
    audio_mode: str = "mix"
    use_voiceover: bool = False
    narration_voice: str = "id-ID-ArdiNeural"
    narration_style: str = "hook_story"
    enable_intro_title: bool = False
    intro_title_duration: float = 2.0
    intro_title_style: str = "fade_slide"
    intro_title_tts: bool = True
    intro_title_voice: str = "id-ID-ArdiNeural"
    intro_title_pause: bool = False
    enable_outro_cta: bool = False
    outro_cta_text: str = "Follow untuk lebih banyak!"
    outro_cta_duration: float = 2.0
    enable_lower_third: bool = False
    lower_third_text: Optional[str] = None
    sticker_path: Optional[str] = None
    sticker_position: str = "top_right"
    sticker_scale: float = 0.15
    sfx_on_hook: bool = False
    sfx_hook_sfx_id: Optional[str] = None
    sfx_hook_threshold: int = 90
    category: str = "text"
    thumbnail_preview: Optional[str] = None
    is_builtin: bool = False
    created_at: str

class TextPresetCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=255)
    crop_mode: str = Field("center", description="'smart', 'center', or 'manual'")
    crop_offset_x: int = 0
    smart_deadzone: float = Field(0.5, ge=0.1, le=0.9)
    smart_pan_seconds: float = Field(0.5, ge=0.2, le=2.0)
    framing_layout: str = Field("single", description="'single', 'pip_full', 'pip_center', 'split_top_bottom', 'split_bottom_top', or 'fit_16_9_center'")
    screen_mode: str = Field("full", max_length=20)
    person_shape: str = Field("circle", max_length=20)
    person_scale: float = Field(0.35, ge=0.15, le=1.5)
    person_offset_x: int = Field(0, ge=-500, le=500)
    person_offset_y: int = Field(0, ge=-800, le=800)
    screen_offset_x: int = Field(0, ge=-500, le=500)
    screen_offset_y: int = Field(0, ge=-500, le=500)
    screen_scale: float = Field(1.0, ge=0.5, le=1.5)
    screen_aspect: str = Field("16:9", max_length=10)
    video_filter: str = Field("none", max_length=20, description="'none', 'cinematic', 'vivid', 'warm', 'cool', 'drama', or 'vintage'")
    font: str = Field("Poppins", max_length=100)
    font_size: int = Field(44, ge=18, le=90)
    primary_color: str = Field("#FFFFFF", max_length=20)
    active_color: str = Field("#FFCC00", max_length=20)
    subtitle_position: str = Field("bottom", max_length=20)
    margin_v: Optional[int] = Field(340, ge=0, le=1920)
    outline_width: int = Field(3, ge=0, le=10)
    shadow_depth: int = Field(1, ge=0, le=10)
    is_uppercase: bool = False
    motion_type: str = Field("karaoke", max_length=30)
    highlight_bg_color: str = Field("#FFCC00", max_length=20)
    enable_keyword_color: bool = True
    keyword_color: str = Field("#10B981", max_length=20)
    enable_dynamic_scaling: bool = False
    enable_emoji_injection: bool = False
    glow_effect: bool = False
    enable_vocal_dynamics: bool = False
    audio_track_id: Optional[str] = None
    bgm_volume: float = Field(0.2, ge=0.0, le=1.0)
    audio_mode: str = Field("mix", description="'mix', 'replace', or 'original'")
    use_voiceover: bool = False
    narration_voice: str = Field("id-ID-ArdiNeural", max_length=100)
    narration_style: str = Field("hook_story", max_length=50)
    enable_intro_title: bool = False
    intro_title_duration: float = Field(2.0, ge=0.5, le=5.0)
    intro_title_style: str = Field("fade_slide", max_length=20)
    intro_title_tts: bool = True
    intro_title_voice: str = Field("id-ID-ArdiNeural", max_length=50)
    intro_title_pause: bool = False
    enable_outro_cta: bool = False
    outro_cta_text: str = Field("Follow untuk lebih banyak!", max_length=255)
    outro_cta_duration: float = Field(2.0, ge=0.5, le=10.0)
    enable_lower_third: bool = False
    lower_third_text: Optional[str] = Field(None, max_length=255)
    sticker_path: Optional[str] = None
    sticker_position: str = Field("top_right", max_length=20)
    sticker_scale: float = Field(0.15, ge=0.05, le=0.5)
    sfx_on_hook: bool = False
    sfx_hook_sfx_id: Optional[str] = None
    sfx_hook_threshold: int = Field(90, ge=0, le=100)
    category: str = Field("text", max_length=20)
    thumbnail_preview: Optional[str] = Field(None, max_length=500)

class TextPresetUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = Field(None, max_length=255)
    crop_mode: Optional[str] = None
    crop_offset_x: Optional[int] = None
    smart_deadzone: Optional[float] = Field(None, ge=0.1, le=0.9)
    smart_pan_seconds: Optional[float] = Field(None, ge=0.2, le=2.0)
    framing_layout: Optional[str] = None
    screen_mode: Optional[str] = None
    person_shape: Optional[str] = None
    person_scale: Optional[float] = Field(None, ge=0.15, le=1.5)
    person_offset_x: Optional[int] = Field(None, ge=-500, le=500)
    person_offset_y: Optional[int] = Field(None, ge=-800, le=800)
    screen_offset_x: Optional[int] = Field(None, ge=-500, le=500)
    screen_offset_y: Optional[int] = Field(None, ge=-500, le=500)
    screen_scale: Optional[float] = Field(None, ge=0.5, le=1.5)
    screen_aspect: Optional[str] = None
    video_filter: Optional[str] = Field(None, max_length=20)
    font: Optional[str] = None
    font_size: Optional[int] = Field(None, ge=18, le=90)
    primary_color: Optional[str] = None
    active_color: Optional[str] = None
    subtitle_position: Optional[str] = None
    margin_v: Optional[int] = Field(None, ge=0, le=1920)
    outline_width: Optional[int] = None
    shadow_depth: Optional[int] = None
    is_uppercase: Optional[bool] = None
    motion_type: Optional[str] = None
    highlight_bg_color: Optional[str] = None
    enable_keyword_color: Optional[bool] = None
    keyword_color: Optional[str] = None
    enable_dynamic_scaling: Optional[bool] = None
    enable_emoji_injection: Optional[bool] = None
    glow_effect: Optional[bool] = None
    enable_vocal_dynamics: Optional[bool] = None
    audio_track_id: Optional[str] = None
    bgm_volume: Optional[float] = Field(None, ge=0.0, le=1.0)
    audio_mode: Optional[str] = None
    use_voiceover: Optional[bool] = None
    narration_voice: Optional[str] = None
    narration_style: Optional[str] = None
    enable_intro_title: Optional[bool] = None
    intro_title_duration: Optional[float] = Field(None, ge=0.5, le=5.0)
    intro_title_style: Optional[str] = None
    intro_title_tts: Optional[bool] = None
    intro_title_voice: Optional[str] = Field(None, max_length=50)
    intro_title_pause: Optional[bool] = None
    enable_outro_cta: Optional[bool] = None
    outro_cta_text: Optional[str] = None
    outro_cta_duration: Optional[float] = Field(None, ge=0.5, le=10.0)
    enable_lower_third: Optional[bool] = None
    lower_third_text: Optional[str] = None
    sticker_path: Optional[str] = None
    sticker_position: Optional[str] = None
    sticker_scale: Optional[float] = Field(None, ge=0.05, le=0.5)
    sfx_on_hook: Optional[bool] = None
    sfx_hook_sfx_id: Optional[str] = None
    sfx_hook_threshold: Optional[int] = Field(None, ge=0, le=100)
    category: Optional[str] = Field(None, max_length=20)
    thumbnail_preview: Optional[str] = Field(None, max_length=500)

# ----------------- Audio Track Schemas -----------------
class AudioTrackResponse(BaseModel):
    id: str
    title: str
    source_type: str
    source_url: Optional[str] = None
    duration_seconds: float
    file_size_bytes: int
    stream_url: str
    created_at: str


class SFXTrackResponse(BaseModel):
    id: str
    title: str
    duration_seconds: float
    file_size_bytes: int
    is_builtin: bool = False
    stream_url: str
    created_at: str

class YouTubeAudioDownloadRequest(BaseModel):
    url: str = Field(..., min_length=1, description="YouTube URL to convert to audio")

# ----------------- Narration Schemas -----------------
class GenerateNarrationRequest(BaseModel):
    target_duration_seconds: Optional[float] = None
    style: Optional[str] = Field("hook_story", description="'hook_story', 'summary', or 'educational'")

class SEOGenerateRequest(BaseModel):
    platform: str = Field("youtube_shorts", description="'youtube_shorts', 'tiktok', or 'instagram_reels'")
    language: str = Field("id", max_length=10)

class SEOGenerateResponse(BaseModel):
    clip_id: str
    titles: List[str]
    description: str = ""
    tags: List[str] = Field(default_factory=list)
    hashtags: List[str] = Field(default_factory=list)
    category_suggestion: str = "22"
    best_upload_time: Optional[str] = None
    estimated_reach: Optional[str] = None
    caption: Optional[str] = None

class GenerateNarrationResponse(BaseModel):
    clip_id: str
    narration_text: str
    estimated_duration_seconds: float

class SynthesizeVoiceRequest(BaseModel):
    text: str = Field(..., min_length=1)
    voice: str = Field("id-ID-ArdiNeural")
    rate: str = Field("+0%")
    pitch: str = Field("+0Hz")

class SynthesizeVoiceResponse(BaseModel):
    clip_id: str
    audio_url: str
    duration_seconds: float


# ----------------- WAHA (WhatsApp HTTP API) Schemas -----------------
class WahaConfigRequest(BaseModel):
    api_url: Optional[str] = Field(None, description="WAHA API URL e.g. http://localhost:3008 or http://waha:3000")
    api_key: Optional[str] = Field(None, description="Optional WAHA API Key")
    session_name: Optional[str] = Field(None, description="WAHA Session Name (default 'default')")
    enabled: Optional[bool] = Field(None, description="Enable or disable WAHA integration")

class WahaStatusResponse(BaseModel):
    enabled: bool = False
    api_url: str = "http://localhost:3008"
    session_name: str = "default"
    session_status: str = "STOPPED"  # STOPPED, STARTING, SCAN_QR_CODE, WORKING, FAILED
    qr_code: Optional[str] = None  # Base64 data URI or QR raw string
    sync_token: str
    paired_chat_id: Optional[str] = None
    paired_chat_name: Optional[str] = None
    paired_chat_type: Optional[str] = None  # "direct" or "group"
    paired_at: Optional[str] = None

class WahaTestMessageRequest(BaseModel):
    message: Optional[str] = Field("🤖 Pesan uji coba dari EmberShorts via WAHA berhasil diterima!", description="Message content")

