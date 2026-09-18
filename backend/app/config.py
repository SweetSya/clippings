import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./storage/autoshorts.db"
    MYSQL_ROOT_PASSWORD: str = "change_me_root"
    MYSQL_DATABASE: str = "autoshorts"
    MYSQL_USER: str = "autoshorts"
    MYSQL_PASSWORD: str = "change_me"

    # Security
    JWT_SECRET: str = "default_jwt_secret_min_32_characters_long_12345"
    SETTINGS_ENCRYPTION_KEY: str = "Q4+sfyd7lz6B5Nb0RVbaVT+s7lIgZ7kz/3oH17mv9AM="

    # Storage & Limits
    STORAGE_ROOT: str = "./storage"
    MAX_UPLOAD_SIZE_MB: int = 2048
    MIN_CLIP_SECONDS: float = 10.0
    MAX_CLIP_SECONDS: float = 90.0
    AUTO_CLEANUP_DAYS: int = 0

    # Concurrency
    TRANSCRIBE_CONCURRENCY: int = 1
    RENDER_CONCURRENCY: int = 2

    # Smart Reframe (head-tracking crop)
    SMART_CROP_DEFAULT: bool = True
    REFRAME_SAMPLE_FPS: float = 2.0
    REFRAME_MAX_KEYFRAMES: int = 150
    REFRAME_MODEL_FILENAME: str = "face_detection_yunet_2023mar.onnx"

    # Faster-Whisper
    WHISPER_MODEL: str = "base"
    WHISPER_DEVICE: str = "cpu"
    WHISPER_COMPUTE_TYPE: str = "int8"

    # API
    VITE_API_BASE_URL: str = "/api"

    # WhatsApp Bot (WAHA)
    WAHA_BASE_URL: str = "http://localhost:3008"
    WAHA_API_KEY: str = "embershorts_waha_secret_key"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()

# Ensure storage directories exist at import time
def ensure_storage_dirs():
    root = os.path.abspath(settings.STORAGE_ROOT)
    for sub in ["uploads", "audio", "transcripts", "subtitles", "thumbnails", "exports", "tts", "credentials", "reframe"]:
        os.makedirs(os.path.join(root, sub), exist_ok=True)

ensure_storage_dirs()
