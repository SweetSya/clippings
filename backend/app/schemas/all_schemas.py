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

class BatchActionResponse(BaseModel):
    success_count: int
    failed_count: int = 0
    message: str

class SettingsResponse(BaseModel):
    llm_base_url: Optional[str] = None
    llm_model: Optional[str] = None
    llm_configured: bool = False
    llm_connected: bool = False
    llm_prompt: Optional[str] = None
    gdrive_auth_type: Optional[str] = "OAUTH2"
    gdrive_folder_id: Optional[str] = None
    gdrive_configured: bool = False
    gdrive_client_id: Optional[str] = None
    gdrive_oauth_connected: bool = False
    gdrive_redirect_uri: Optional[str] = None
    min_clip_seconds: int = 10
    max_clip_seconds: int = 60
    yt_quality: str = "1080p"
    clip_view_mode: str = "grid"
    shorts_view_mode: str = "grid"

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

# ----------------- Clip Schemas -----------------
class ClipCandidateResponse(BaseModel):
    id: str
    video_id: str
    title: str
    start_time_seconds: float
    end_time_seconds: float
    duration_seconds: float
    hook_score: int
    virality_reason: Optional[str] = None
    is_selected: bool
    narration_text: Optional[str] = None
    narration_voice: Optional[str] = None
    narration_audio_path: Optional[str] = None
    created_at: str

class ClipUpdateRequest(BaseModel):
    is_selected: Optional[bool] = None
    title: Optional[str] = None
    start_time_seconds: Optional[float] = None
    end_time_seconds: Optional[float] = None
    narration_text: Optional[str] = None
    narration_voice: Optional[str] = None

class ClipRenderRequest(BaseModel):
    crop_mode: str = Field("center", description="'center', 'manual', or 'smart'")
    crop_offset_x: int = Field(0, description="Horizontal crop offset X in px")
    smart_deadzone: float = Field(0.5, ge=0.1, le=0.9, description="Fraction of crop width the head may move freely")
    smart_pan_seconds: float = Field(0.5, ge=0.0, le=2.0, description="Seconds the crop takes to pan; also the minimum gap between snaps")
    smart_snap: bool = Field(False, description="True cuts instantly to the subject instead of panning smoothly")
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
    motion_type: Optional[str] = Field("karaoke", description="'single_word_pop', 'karaoke', 'background_box', 'typewriter', or 'slide_up'")
    highlight_bg_color: Optional[str] = Field("#FFCC00", description="Background color for background_box sticker")
    enable_keyword_color: Optional[bool] = Field(True, description="Enable auto-color shift on key words")
    keyword_color: Optional[str] = Field("#10B981", description="Contrasting color for key words")
    enable_dynamic_scaling: Optional[bool] = Field(False, description="Scale key words slightly larger (125%)")
    enable_emoji_injection: Optional[bool] = Field(False, description="Automatically prepend smart emojis to key phrases")
    glow_effect: Optional[bool] = Field(False, description="Glow / neon effect outline")

    # Audio & Voiceover fields
    use_voiceover: bool = Field(False, description="Whether to use AI voiceover narration")
    narration_text: Optional[str] = Field(None, description="Narration text to speak")
    narration_voice: Optional[str] = Field("id-ID-ArdiNeural", description="Voice ID for narration")
    audio_track_id: Optional[str] = Field(None, description="Selected BGM audio track ID")
    bgm_volume: float = Field(0.2, ge=0.0, le=1.0, description="Background music volume (0.0 - 1.0)")
    audio_mode: str = Field("mix", description="'mix' (duck original for voiceover/bgm), 'replace' (replace original audio), 'original'")

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
    download_url: str
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
    audio_track_id: Optional[str] = None
    bgm_volume: float = 0.2
    audio_mode: str = "mix"
    use_voiceover: bool = False
    narration_voice: str = "id-ID-ArdiNeural"
    narration_style: str = "hook_story"
    is_builtin: bool = False
    created_at: str

class TextPresetCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=255)
    crop_mode: str = Field("center", description="'smart', 'center', or 'manual'")
    crop_offset_x: int = 0
    smart_deadzone: float = Field(0.5, ge=0.1, le=0.9)
    smart_pan_seconds: float = Field(0.5, ge=0.2, le=2.0)
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
    audio_track_id: Optional[str] = None
    bgm_volume: float = Field(0.2, ge=0.0, le=1.0)
    audio_mode: str = Field("mix", description="'mix', 'replace', or 'original'")
    use_voiceover: bool = False
    narration_voice: str = Field("id-ID-ArdiNeural", max_length=100)
    narration_style: str = Field("hook_story", max_length=50)

class TextPresetUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = Field(None, max_length=255)
    crop_mode: Optional[str] = None
    crop_offset_x: Optional[int] = None
    smart_deadzone: Optional[float] = Field(None, ge=0.1, le=0.9)
    smart_pan_seconds: Optional[float] = Field(None, ge=0.2, le=2.0)
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
    audio_track_id: Optional[str] = None
    bgm_volume: Optional[float] = Field(None, ge=0.0, le=1.0)
    audio_mode: Optional[str] = None
    use_voiceover: Optional[bool] = None
    narration_voice: Optional[str] = None
    narration_style: Optional[str] = None

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

class YouTubeAudioDownloadRequest(BaseModel):
    url: str = Field(..., min_length=1, description="YouTube URL to convert to audio")

# ----------------- Narration Schemas -----------------
class GenerateNarrationRequest(BaseModel):
    target_duration_seconds: Optional[float] = None
    style: Optional[str] = Field("hook_story", description="'hook_story', 'summary', or 'educational'")

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
