from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool
from app.config import settings

def build_engine_kwargs(database_url: str) -> dict:
    """
    Argumen engine per driver.
    SQLite: NullPool — tiap sesi buka/tutup koneksi sendiri. Worker menahan sesi
    selama job panjang (render/vision bermenit-menit); QueuePool default (5+10)
    habis dan poll loop timeout 30s. NullPool menghilangkan batas checkout;
    kontensi tulis SQLite ditahan busy timeout 30s.
    """
    kwargs: dict = {"echo": False}
    if database_url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False, "timeout": 30}
        kwargs["poolclass"] = NullPool
    else:
        kwargs["pool_pre_ping"] = True
        kwargs["pool_recycle"] = 3600
    return kwargs

# Configure engine arguments based on driver
engine_kwargs = build_engine_kwargs(settings.DATABASE_URL)

engine = create_async_engine(settings.DATABASE_URL, **engine_kwargs)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False
)

class Base(DeclarativeBase):
    pass

async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

async def init_db():
    import app.models  # Ensure all models are registered on Base.metadata
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        if settings.DATABASE_URL.startswith("sqlite"):
            from sqlalchemy import text
            res = await conn.execute(text("PRAGMA table_info(source_videos)"))
            cols = [row[1] for row in res.fetchall()]
            if cols and "description" not in cols:
                await conn.execute(text("ALTER TABLE source_videos ADD COLUMN description TEXT"))
            if cols and "auto_generate_shorts" not in cols:
                await conn.execute(text("ALTER TABLE source_videos ADD COLUMN auto_generate_shorts BOOLEAN DEFAULT 0"))
            if cols and "video_type" not in cols:
                await conn.execute(text("ALTER TABLE source_videos ADD COLUMN video_type VARCHAR(50)"))
            if cols and "file_hash" not in cols:
                await conn.execute(text("ALTER TABLE source_videos ADD COLUMN file_hash VARCHAR(64)"))
            if cols and "source_url" not in cols:
                await conn.execute(text("ALTER TABLE source_videos ADD COLUMN source_url VARCHAR(500)"))

            # Migrate rendered_shorts columns
            res_shorts = await conn.execute(text("PRAGMA table_info(rendered_shorts)"))
            short_cols = [row[1] for row in res_shorts.fetchall()]
            if short_cols and "is_youtube_uploaded" not in short_cols:
                await conn.execute(text("ALTER TABLE rendered_shorts ADD COLUMN is_youtube_uploaded BOOLEAN DEFAULT 0"))
            if short_cols and "thumbnail_path" not in short_cols:
                await conn.execute(text("ALTER TABLE rendered_shorts ADD COLUMN thumbnail_path VARCHAR(500)"))

            # Migrate youtube_exports columns
            res_yt = await conn.execute(text("PRAGMA table_info(youtube_exports)"))
            yt_cols = [row[1] for row in res_yt.fetchall()]
            if yt_cols and "made_for_kids" not in yt_cols:
                await conn.execute(text("ALTER TABLE youtube_exports ADD COLUMN made_for_kids BOOLEAN DEFAULT 0"))

            # Migrate clip_candidates columns
            res_clips = await conn.execute(text("PRAGMA table_info(clip_candidates)"))
            clip_cols = [row[1] for row in res_clips.fetchall()]
            if clip_cols and "narration_text" not in clip_cols:
                await conn.execute(text("ALTER TABLE clip_candidates ADD COLUMN narration_text TEXT"))
            if clip_cols and "narration_voice" not in clip_cols:
                await conn.execute(text("ALTER TABLE clip_candidates ADD COLUMN narration_voice VARCHAR(50)"))
            if clip_cols and "narration_audio_path" not in clip_cols:
                await conn.execute(text("ALTER TABLE clip_candidates ADD COLUMN narration_audio_path VARCHAR(500)"))
            if clip_cols and "seo_titles" not in clip_cols:
                await conn.execute(text("ALTER TABLE clip_candidates ADD COLUMN seo_titles JSON"))
            if clip_cols and "seo_description" not in clip_cols:
                await conn.execute(text("ALTER TABLE clip_candidates ADD COLUMN seo_description TEXT"))
            if clip_cols and "seo_tags" not in clip_cols:
                await conn.execute(text("ALTER TABLE clip_candidates ADD COLUMN seo_tags JSON"))
            if clip_cols and "seo_hashtags" not in clip_cols:
                await conn.execute(text("ALTER TABLE clip_candidates ADD COLUMN seo_hashtags JSON"))
            if clip_cols and "composite_score" not in clip_cols:
                await conn.execute(text("ALTER TABLE clip_candidates ADD COLUMN composite_score INTEGER DEFAULT 0"))
            if clip_cols and "speech_rate" not in clip_cols:
                await conn.execute(text("ALTER TABLE clip_candidates ADD COLUMN speech_rate FLOAT DEFAULT 0"))
            if clip_cols and "keyword_density" not in clip_cols:
                await conn.execute(text("ALTER TABLE clip_candidates ADD COLUMN keyword_density FLOAT DEFAULT 0"))
            if clip_cols and "face_coverage" not in clip_cols:
                await conn.execute(text("ALTER TABLE clip_candidates ADD COLUMN face_coverage FLOAT DEFAULT 0"))

            # Migrate text_presets columns
            res_presets_info = await conn.execute(text("PRAGMA table_info(text_presets)"))
            preset_cols = [row[1] for row in res_presets_info.fetchall()]
            if preset_cols:
                if "description" not in preset_cols:
                    await conn.execute(text("ALTER TABLE text_presets ADD COLUMN description VARCHAR(255)"))
                if "crop_mode" not in preset_cols:
                    await conn.execute(text("ALTER TABLE text_presets ADD COLUMN crop_mode VARCHAR(20) DEFAULT 'center'"))
                if "crop_offset_x" not in preset_cols:
                    await conn.execute(text("ALTER TABLE text_presets ADD COLUMN crop_offset_x INTEGER DEFAULT 0"))
                if "smart_deadzone" not in preset_cols:
                    await conn.execute(text("ALTER TABLE text_presets ADD COLUMN smart_deadzone FLOAT DEFAULT 0.5"))
                if "smart_pan_seconds" not in preset_cols:
                    await conn.execute(text("ALTER TABLE text_presets ADD COLUMN smart_pan_seconds FLOAT DEFAULT 0.5"))
                if "audio_track_id" not in preset_cols:
                    await conn.execute(text("ALTER TABLE text_presets ADD COLUMN audio_track_id VARCHAR(36)"))
                if "bgm_volume" not in preset_cols:
                    await conn.execute(text("ALTER TABLE text_presets ADD COLUMN bgm_volume FLOAT DEFAULT 0.2"))
                if "audio_mode" not in preset_cols:
                    await conn.execute(text("ALTER TABLE text_presets ADD COLUMN audio_mode VARCHAR(20) DEFAULT 'mix'"))
                if "use_voiceover" not in preset_cols:
                    await conn.execute(text("ALTER TABLE text_presets ADD COLUMN use_voiceover BOOLEAN DEFAULT 0"))
                if "narration_voice" not in preset_cols:
                    await conn.execute(text("ALTER TABLE text_presets ADD COLUMN narration_voice VARCHAR(100) DEFAULT 'id-ID-ArdiNeural'"))
                if "narration_style" not in preset_cols:
                    await conn.execute(text("ALTER TABLE text_presets ADD COLUMN narration_style VARCHAR(50) DEFAULT 'hook_story'"))
                if "motion_type" not in preset_cols:
                    await conn.execute(text("ALTER TABLE text_presets ADD COLUMN motion_type VARCHAR(30) DEFAULT 'karaoke'"))
                if "highlight_bg_color" not in preset_cols:
                    await conn.execute(text("ALTER TABLE text_presets ADD COLUMN highlight_bg_color VARCHAR(20) DEFAULT '#FFCC00'"))
                if "enable_keyword_color" not in preset_cols:
                    await conn.execute(text("ALTER TABLE text_presets ADD COLUMN enable_keyword_color BOOLEAN DEFAULT 1"))
                if "keyword_color" not in preset_cols:
                    await conn.execute(text("ALTER TABLE text_presets ADD COLUMN keyword_color VARCHAR(20) DEFAULT '#10B981'"))
                if "enable_dynamic_scaling" not in preset_cols:
                    await conn.execute(text("ALTER TABLE text_presets ADD COLUMN enable_dynamic_scaling BOOLEAN DEFAULT 0"))
                if "enable_emoji_injection" not in preset_cols:
                    await conn.execute(text("ALTER TABLE text_presets ADD COLUMN enable_emoji_injection BOOLEAN DEFAULT 0"))
                if "glow_effect" not in preset_cols:
                    await conn.execute(text("ALTER TABLE text_presets ADD COLUMN glow_effect BOOLEAN DEFAULT 0"))
                if "framing_layout" not in preset_cols:
                    await conn.execute(text("ALTER TABLE text_presets ADD COLUMN framing_layout VARCHAR(30) DEFAULT 'single'"))
                if "person_offset_x" not in preset_cols:
                    await conn.execute(text("ALTER TABLE text_presets ADD COLUMN person_offset_x INTEGER DEFAULT 0"))
                if "person_offset_y" not in preset_cols:
                    await conn.execute(text("ALTER TABLE text_presets ADD COLUMN person_offset_y INTEGER DEFAULT 0"))
                if "screen_offset_x" not in preset_cols:
                    await conn.execute(text("ALTER TABLE text_presets ADD COLUMN screen_offset_x INTEGER DEFAULT 0"))
                if "screen_offset_y" not in preset_cols:
                    await conn.execute(text("ALTER TABLE text_presets ADD COLUMN screen_offset_y INTEGER DEFAULT 0"))
                if "screen_scale" not in preset_cols:
                    await conn.execute(text("ALTER TABLE text_presets ADD COLUMN screen_scale FLOAT DEFAULT 1.0"))
                if "screen_aspect" not in preset_cols:
                    await conn.execute(text("ALTER TABLE text_presets ADD COLUMN screen_aspect VARCHAR(10) DEFAULT '16:9'"))
                if "enable_vocal_dynamics" not in preset_cols:
                    await conn.execute(text("ALTER TABLE text_presets ADD COLUMN enable_vocal_dynamics BOOLEAN DEFAULT 0"))
                if "screen_mode" not in preset_cols:
                    await conn.execute(text("ALTER TABLE text_presets ADD COLUMN screen_mode VARCHAR(20) DEFAULT 'full'"))
                if "person_shape" not in preset_cols:
                    await conn.execute(text("ALTER TABLE text_presets ADD COLUMN person_shape VARCHAR(20) DEFAULT 'circle'"))
                if "person_scale" not in preset_cols:
                    await conn.execute(text("ALTER TABLE text_presets ADD COLUMN person_scale FLOAT DEFAULT 0.45"))
                if "video_filter" not in preset_cols:
                    await conn.execute(text("ALTER TABLE text_presets ADD COLUMN video_filter VARCHAR(20) DEFAULT 'none'"))
                if "enable_intro_title" not in preset_cols:
                    await conn.execute(text("ALTER TABLE text_presets ADD COLUMN enable_intro_title BOOLEAN DEFAULT 0"))
                if "intro_title_duration" not in preset_cols:
                    await conn.execute(text("ALTER TABLE text_presets ADD COLUMN intro_title_duration FLOAT DEFAULT 2.0"))
                if "intro_title_style" not in preset_cols:
                    await conn.execute(text("ALTER TABLE text_presets ADD COLUMN intro_title_style VARCHAR(20) DEFAULT 'fade_slide'"))
                if "intro_title_tts" not in preset_cols:
                    await conn.execute(text("ALTER TABLE text_presets ADD COLUMN intro_title_tts BOOLEAN DEFAULT 1"))
                if "intro_title_voice" not in preset_cols:
                    await conn.execute(text("ALTER TABLE text_presets ADD COLUMN intro_title_voice VARCHAR(50) DEFAULT 'id-ID-ArdiNeural'"))
                if "intro_title_pause" not in preset_cols:
                    await conn.execute(text("ALTER TABLE text_presets ADD COLUMN intro_title_pause BOOLEAN DEFAULT 0"))
                if "enable_outro_cta" not in preset_cols:
                    await conn.execute(text("ALTER TABLE text_presets ADD COLUMN enable_outro_cta BOOLEAN DEFAULT 0"))
                if "outro_cta_text" not in preset_cols:
                    await conn.execute(text("ALTER TABLE text_presets ADD COLUMN outro_cta_text VARCHAR(255) DEFAULT 'Follow untuk lebih banyak!'"))
                if "outro_cta_duration" not in preset_cols:
                    await conn.execute(text("ALTER TABLE text_presets ADD COLUMN outro_cta_duration FLOAT DEFAULT 2.0"))
                if "enable_lower_third" not in preset_cols:
                    await conn.execute(text("ALTER TABLE text_presets ADD COLUMN enable_lower_third BOOLEAN DEFAULT 0"))
                if "lower_third_text" not in preset_cols:
                    await conn.execute(text("ALTER TABLE text_presets ADD COLUMN lower_third_text VARCHAR(255)"))
                if "sticker_path" not in preset_cols:
                    await conn.execute(text("ALTER TABLE text_presets ADD COLUMN sticker_path VARCHAR(500)"))
                if "sticker_position" not in preset_cols:
                    await conn.execute(text("ALTER TABLE text_presets ADD COLUMN sticker_position VARCHAR(20) DEFAULT 'top_right'"))
                if "sticker_scale" not in preset_cols:
                    await conn.execute(text("ALTER TABLE text_presets ADD COLUMN sticker_scale FLOAT DEFAULT 0.15"))
                if "sfx_on_hook" not in preset_cols:
                    await conn.execute(text("ALTER TABLE text_presets ADD COLUMN sfx_on_hook BOOLEAN DEFAULT 0"))
                if "sfx_hook_sfx_id" not in preset_cols:
                    await conn.execute(text("ALTER TABLE text_presets ADD COLUMN sfx_hook_sfx_id VARCHAR(36)"))
                if "sfx_hook_threshold" not in preset_cols:
                    await conn.execute(text("ALTER TABLE text_presets ADD COLUMN sfx_hook_threshold INTEGER DEFAULT 90"))
                if "category" not in preset_cols:
                    await conn.execute(text("ALTER TABLE text_presets ADD COLUMN category VARCHAR(20) DEFAULT 'text'"))
                if "thumbnail_preview" not in preset_cols:
                    await conn.execute(text("ALTER TABLE text_presets ADD COLUMN thumbnail_preview VARCHAR(500)"))

            # Seed or update default unified presets
            default_presets = [
                {
                    "id": "preset_tiktok_bold",
                    "name": "TikTok Viral Bold",
                    "description": "Gaya dinamis Hormozi pop 1 kata di tengah layar dengan smart reframing dan emoji otomatis",
                    "crop_mode": "smart",
                    "crop_offset_x": 0,
                    "smart_deadzone": 0.4,
                    "smart_pan_seconds": 0.4,
                    "framing_layout": "single",
                    "screen_mode": "full",
                    "person_shape": "circle",
                    "person_scale": 0.35,
                    "person_offset_x": 0,
                    "person_offset_y": 0,
                    "screen_offset_x": 0,
                    "screen_offset_y": 0,
                    "screen_scale": 1.0,
                    "screen_aspect": "16:9",
                    "font": "Poppins",
                    "font_size": 50,
                    "primary_color": "#FFFFFF",
                    "active_color": "#FFCC00",
                    "subtitle_position": "middle",
                    "margin_v": 920,
                    "outline_width": 4,
                    "shadow_depth": 2,
                    "is_uppercase": 1,
                    "motion_type": "single_word_pop",
                    "highlight_bg_color": "#FFCC00",
                    "enable_keyword_color": 1,
                    "keyword_color": "#10B981",
                    "enable_dynamic_scaling": 1,
                    "enable_emoji_injection": 1,
                    "glow_effect": 0,
                    "enable_vocal_dynamics": 0,
                    "audio_track_id": None,
                    "bgm_volume": 0.2,
                    "audio_mode": "mix",
                    "use_voiceover": 0,
                    "narration_voice": "id-ID-ArdiNeural",
                    "narration_style": "hook_story",
                    "is_builtin": 1
                },
                {
                    "id": "preset_streamer_pip_circle",
                    "category": "streamer",
                    "name": "Gaming Streamer (With Overlay)",
                    "description": "With Overlay: Layar 9:16 vertikal penuh + facecam lingkaran di kanan bawah dengan efek neon glow",
                    "crop_mode": "manual",
                    "crop_offset_x": 1380,
                    "smart_deadzone": 0.5,
                    "smart_pan_seconds": 0.5,
                    "framing_layout": "pip_full",
                    "screen_mode": "full",
                    "person_shape": "circle",
                    "person_scale": 0.35,
                    "person_offset_x": 0,
                    "person_offset_y": 420,
                    "screen_offset_x": 0,
                    "screen_offset_y": 0,
                    "screen_scale": 1.0,
                    "screen_aspect": "16:9",
                    "font": "Anton",
                    "font_size": 46,
                    "primary_color": "#00F0FF",
                    "active_color": "#FFE600",
                    "subtitle_position": "bottom",
                    "margin_v": 320,
                    "outline_width": 3,
                    "shadow_depth": 2,
                    "is_uppercase": 1,
                    "motion_type": "karaoke",
                    "highlight_bg_color": "#FFE600",
                    "enable_keyword_color": 1,
                    "keyword_color": "#00F0FF",
                    "enable_dynamic_scaling": 1,
                    "enable_emoji_injection": 0,
                    "glow_effect": 1,
                    "enable_vocal_dynamics": 1,
                    "audio_track_id": None,
                    "bgm_volume": 0.25,
                    "audio_mode": "mix",
                    "use_voiceover": 0,
                    "narration_voice": "id-ID-ArdiNeural",
                    "narration_style": "hook_story",
                    "is_builtin": 1
                },
                {
                    "id": "preset_streamer_pip_center",
                    "category": "streamer",
                    "name": "Streamer 16:9 (With Overlay)",
                    "description": "With Overlay: Layar 16:9 di tengah dengan ambient blur dan facecam rounded di bawah",
                    "crop_mode": "manual",
                    "crop_offset_x": 1380,
                    "smart_deadzone": 0.5,
                    "smart_pan_seconds": 0.5,
                    "framing_layout": "pip_center",
                    "screen_mode": "center",
                    "person_shape": "rounded",
                    "person_scale": 0.36,
                    "person_offset_x": 0,
                    "person_offset_y": 460,
                    "screen_offset_x": 0,
                    "screen_offset_y": 0,
                    "screen_scale": 1.0,
                    "screen_aspect": "16:9",
                    "font": "Poppins",
                    "font_size": 42,
                    "primary_color": "#FFFFFF",
                    "active_color": "#F59E0B",
                    "subtitle_position": "bottom",
                    "margin_v": 280,
                    "outline_width": 2,
                    "shadow_depth": 1,
                    "is_uppercase": 1,
                    "motion_type": "background_box",
                    "highlight_bg_color": "#F59E0B",
                    "enable_keyword_color": 1,
                    "keyword_color": "#F59E0B",
                    "enable_dynamic_scaling": 1,
                    "enable_emoji_injection": 0,
                    "glow_effect": 0,
                    "enable_vocal_dynamics": 0,
                    "audio_track_id": None,
                    "bgm_volume": 0.2,
                    "audio_mode": "mix",
                    "use_voiceover": 0,
                    "narration_voice": "id-ID-GadisNeural",
                    "narration_style": "hook_story",
                    "is_builtin": 1
                },
                {
                    "id": "preset_tech_tutorial_center",
                    "category": "educational",
                    "name": "Tech Tutorial (Without Overlay)",
                    "description": "Without Overlay: Layar 16:9 di tengah dengan ambient blur lembut dan teks slide-up untuk tutorial & screencast",
                    "crop_mode": "center",
                    "crop_offset_x": 0,
                    "smart_deadzone": 0.5,
                    "smart_pan_seconds": 0.5,
                    "framing_layout": "fit_16_9_center",
                    "screen_mode": "center",
                    "person_shape": "circle",
                    "person_scale": 0.35,
                    "person_offset_x": 0,
                    "person_offset_y": 0,
                    "screen_offset_x": 0,
                    "screen_offset_y": 0,
                    "screen_scale": 1.0,
                    "screen_aspect": "16:9",
                    "font": "Inter",
                    "font_size": 38,
                    "primary_color": "#F8FAFC",
                    "active_color": "#38BDF8",
                    "subtitle_position": "bottom",
                    "margin_v": 280,
                    "outline_width": 2,
                    "shadow_depth": 1,
                    "is_uppercase": 0,
                    "motion_type": "slide_up",
                    "highlight_bg_color": "#38BDF8",
                    "enable_keyword_color": 1,
                    "keyword_color": "#38BDF8",
                    "enable_dynamic_scaling": 0,
                    "enable_emoji_injection": 0,
                    "glow_effect": 0,
                    "enable_vocal_dynamics": 0,
                    "audio_track_id": None,
                    "bgm_volume": 0.15,
                    "audio_mode": "mix",
                    "use_voiceover": 0,
                    "narration_voice": "id-ID-GadisNeural",
                    "narration_style": "summary",
                    "is_builtin": 1
                },
                {
                    "id": "preset_streamer_16_9_blur",
                    "category": "streamer",
                    "name": "Streamer 16:9 Blur (Without Overlay)",
                    "description": "Without Overlay: Layar gameplay 16:9 di tengah dengan background ambient blur dan subtitle neon dinamis untuk gaming streamer",
                    "crop_mode": "center",
                    "crop_offset_x": 0,
                    "smart_deadzone": 0.5,
                    "smart_pan_seconds": 0.5,
                    "framing_layout": "fit_16_9_center",
                    "screen_mode": "center",
                    "person_shape": "circle",
                    "person_scale": 0.35,
                    "person_offset_x": 0,
                    "person_offset_y": 0,
                    "screen_offset_x": 0,
                    "screen_offset_y": 0,
                    "screen_scale": 1.0,
                    "screen_aspect": "16:9",
                    "font": "Anton",
                    "font_size": 46,
                    "primary_color": "#FFFFFF",
                    "active_color": "#00F0FF",
                    "subtitle_position": "bottom",
                    "margin_v": 280,
                    "outline_width": 3,
                    "shadow_depth": 2,
                    "is_uppercase": 1,
                    "motion_type": "karaoke",
                    "highlight_bg_color": "#00F0FF",
                    "enable_keyword_color": 1,
                    "keyword_color": "#FFE600",
                    "enable_dynamic_scaling": 1,
                    "enable_emoji_injection": 0,
                    "glow_effect": 1,
                    "enable_vocal_dynamics": 1,
                    "audio_track_id": None,
                    "bgm_volume": 0.2,
                    "audio_mode": "mix",
                    "use_voiceover": 0,
                    "narration_voice": "id-ID-ArdiNeural",
                    "narration_style": "hook_story",
                    "is_builtin": 1
                },
                {
                    "id": "preset_cyberpunk",
                    "category": "gaming",
                    "name": "Cyberpunk Neon Karaoke",
                    "description": "Gaya futuristik neon cyan-kuning dengan efek glow neon dan karaoke highlight perkata",
                    "crop_mode": "smart",
                    "crop_offset_x": 0,
                    "smart_deadzone": 0.3,
                    "smart_pan_seconds": 0.3,
                    "framing_layout": "single",
                    "screen_mode": "full",
                    "person_shape": "circle",
                    "person_scale": 0.35,
                    "person_offset_x": 0,
                    "person_offset_y": 0,
                    "screen_offset_x": 0,
                    "screen_offset_y": 0,
                    "screen_scale": 1.0,
                    "screen_aspect": "16:9",
                    "font": "Anton",
                    "font_size": 48,
                    "primary_color": "#00F0FF",
                    "active_color": "#FFE600",
                    "subtitle_position": "middle",
                    "margin_v": 920,
                    "outline_width": 3,
                    "shadow_depth": 3,
                    "is_uppercase": 1,
                    "motion_type": "karaoke",
                    "highlight_bg_color": "#FFE600",
                    "enable_keyword_color": 1,
                    "keyword_color": "#00F0FF",
                    "enable_dynamic_scaling": 1,
                    "enable_emoji_injection": 0,
                    "glow_effect": 1,
                    "enable_vocal_dynamics": 0,
                    "audio_track_id": None,
                    "bgm_volume": 0.25,
                    "audio_mode": "mix",
                    "use_voiceover": 0,
                    "narration_voice": "id-ID-ArdiNeural",
                    "narration_style": "hook_story",
                    "is_builtin": 1
                },
                {
                    "id": "preset_golden_lux",
                    "category": "motivational",
                    "name": "Golden Luxury Sticker",
                    "description": "Gaya premium highlighter sticker box emas di tengah layar untuk quotes & motivasi",
                    "crop_mode": "center",
                    "crop_offset_x": 0,
                    "smart_deadzone": 0.5,
                    "smart_pan_seconds": 0.5,
                    "framing_layout": "single",
                    "screen_mode": "full",
                    "person_shape": "circle",
                    "person_scale": 0.35,
                    "person_offset_x": 0,
                    "person_offset_y": 0,
                    "screen_offset_x": 0,
                    "screen_offset_y": 0,
                    "screen_scale": 1.0,
                    "screen_aspect": "16:9",
                    "font": "Poppins",
                    "font_size": 44,
                    "primary_color": "#1C1917",
                    "active_color": "#F59E0B",
                    "subtitle_position": "middle",
                    "margin_v": 920,
                    "outline_width": 2,
                    "shadow_depth": 1,
                    "is_uppercase": 1,
                    "motion_type": "background_box",
                    "highlight_bg_color": "#F59E0B",
                    "enable_keyword_color": 1,
                    "keyword_color": "#F59E0B",
                    "enable_dynamic_scaling": 1,
                    "enable_emoji_injection": 0,
                    "glow_effect": 1,
                    "enable_vocal_dynamics": 0,
                    "audio_track_id": None,
                    "bgm_volume": 0.2,
                    "audio_mode": "mix",
                    "use_voiceover": 0,
                    "narration_voice": "id-ID-GadisNeural",
                    "narration_style": "hook_story",
                    "is_builtin": 1
                },
                {
                    "id": "preset_documentary",
                    "category": "podcast",
                    "name": "Classic Documentary Typewriter",
                    "description": "Serif sinematik klasik dengan animasi kata typewriter untuk narasi sejarah & kisah mendalam",
                    "crop_mode": "smart",
                    "crop_offset_x": 0,
                    "smart_deadzone": 0.5,
                    "smart_pan_seconds": 0.8,
                    "framing_layout": "single",
                    "screen_mode": "full",
                    "person_shape": "circle",
                    "person_scale": 0.35,
                    "person_offset_x": 0,
                    "person_offset_y": 0,
                    "screen_offset_x": 0,
                    "screen_offset_y": 0,
                    "screen_scale": 1.0,
                    "screen_aspect": "16:9",
                    "font": "Playfair Display",
                    "font_size": 42,
                    "primary_color": "#FFFFFF",
                    "active_color": "#E2E8F0",
                    "subtitle_position": "bottom",
                    "margin_v": 340,
                    "outline_width": 2,
                    "shadow_depth": 1,
                    "is_uppercase": 0,
                    "motion_type": "typewriter",
                    "highlight_bg_color": "#E2E8F0",
                    "enable_keyword_color": 0,
                    "keyword_color": "#E2E8F0",
                    "enable_dynamic_scaling": 0,
                    "enable_emoji_injection": 0,
                    "glow_effect": 0,
                    "enable_vocal_dynamics": 0,
                    "audio_track_id": None,
                    "bgm_volume": 0.2,
                    "audio_mode": "mix",
                    "use_voiceover": 0,
                    "narration_voice": "id-ID-ArdiNeural",
                    "narration_style": "hook_story",
                    "is_builtin": 1
                },
                {
                    "id": "preset_minimalist",
                    "name": "Minimalist Clean Podcast",
                    "description": "Tampilan bersih minimalis slide-up elegan di bawah layar untuk dialog santai dan podcast",
                    "crop_mode": "center",
                    "crop_offset_x": 0,
                    "smart_deadzone": 0.5,
                    "smart_pan_seconds": 0.5,
                    "framing_layout": "single",
                    "screen_mode": "full",
                    "person_shape": "circle",
                    "person_scale": 0.35,
                    "person_offset_x": 0,
                    "person_offset_y": 0,
                    "screen_offset_x": 0,
                    "screen_offset_y": 0,
                    "screen_scale": 1.0,
                    "screen_aspect": "16:9",
                    "font": "Inter",
                    "font_size": 40,
                    "primary_color": "#F5F5F4",
                    "active_color": "#38BDF8",
                    "subtitle_position": "bottom",
                    "margin_v": 300,
                    "outline_width": 2,
                    "shadow_depth": 1,
                    "is_uppercase": 0,
                    "motion_type": "slide_up",
                    "highlight_bg_color": "#38BDF8",
                    "enable_keyword_color": 0,
                    "keyword_color": "#38BDF8",
                    "enable_dynamic_scaling": 0,
                    "enable_emoji_injection": 0,
                    "glow_effect": 0,
                    "enable_vocal_dynamics": 0,
                    "audio_track_id": None,
                    "bgm_volume": 0.15,
                    "audio_mode": "mix",
                    "use_voiceover": 0,
                    "narration_voice": "id-ID-GadisNeural",
                    "narration_style": "summary",
                    "is_builtin": 1
                },
                {
                    "id": "preset_impact_meme",
                    "category": "gaming",
                    "name": "Meme Flash Punchy",
                    "description": "Huruf ultra tebal dengan outline kontras tinggi dan warna merah pop untuk klip meme & reaksi lucu",
                    "crop_mode": "smart",
                    "crop_offset_x": 0,
                    "smart_deadzone": 0.3,
                    "smart_pan_seconds": 0.3,
                    "framing_layout": "single",
                    "screen_mode": "full",
                    "person_shape": "circle",
                    "person_scale": 0.35,
                    "person_offset_x": 0,
                    "person_offset_y": 0,
                    "screen_offset_x": 0,
                    "screen_offset_y": 0,
                    "screen_scale": 1.0,
                    "screen_aspect": "16:9",
                    "font": "Archivo Black",
                    "font_size": 52,
                    "primary_color": "#FFFFFF",
                    "active_color": "#EF4444",
                    "subtitle_position": "middle",
                    "margin_v": 920,
                    "outline_width": 5,
                    "shadow_depth": 3,
                    "is_uppercase": 1,
                    "motion_type": "single_word_pop",
                    "highlight_bg_color": "#EF4444",
                    "enable_keyword_color": 1,
                    "keyword_color": "#F59E0B",
                    "enable_dynamic_scaling": 1,
                    "enable_emoji_injection": 1,
                    "glow_effect": 0,
                    "enable_vocal_dynamics": 1,
                    "audio_track_id": None,
                    "bgm_volume": 0.25,
                    "audio_mode": "mix",
                    "use_voiceover": 0,
                    "narration_voice": "id-ID-ArdiNeural",
                    "narration_style": "hook_story",
                    "is_builtin": 1
                },
                {
                    "id": "preset_vocal_bebas",
                    "category": "podcast",
                    "name": "Vocal Punch Dynamic",
                    "description": "Tipografi tegas all-caps dengan pembesaran kata dinamis berdasarkan dinamika vokal pembicara",
                    "crop_mode": "smart",
                    "crop_offset_x": 0,
                    "smart_deadzone": 0.4,
                    "smart_pan_seconds": 0.4,
                    "framing_layout": "single",
                    "screen_mode": "full",
                    "person_shape": "circle",
                    "person_scale": 0.35,
                    "person_offset_x": 0,
                    "person_offset_y": 0,
                    "screen_offset_x": 0,
                    "screen_offset_y": 0,
                    "screen_scale": 1.0,
                    "screen_aspect": "16:9",
                    "font": "Bebas Neue",
                    "font_size": 54,
                    "primary_color": "#FFFFFF",
                    "active_color": "#10B981",
                    "subtitle_position": "middle",
                    "margin_v": 880,
                    "outline_width": 3,
                    "shadow_depth": 2,
                    "is_uppercase": 1,
                    "motion_type": "karaoke",
                    "highlight_bg_color": "#10B981",
                    "enable_keyword_color": 1,
                    "keyword_color": "#FACC15",
                    "enable_dynamic_scaling": 1,
                    "enable_emoji_injection": 1,
                    "glow_effect": 0,
                    "enable_vocal_dynamics": 1,
                    "audio_track_id": None,
                    "bgm_volume": 0.2,
                    "audio_mode": "mix",
                    "use_voiceover": 0,
                    "narration_voice": "id-ID-ArdiNeural",
                    "narration_style": "hook_story",
                    "is_builtin": 1
                },
                {
                    "id": "preset_streamer_face_top",
                    "category": "streamer",
                    "name": "Streamer: Wajah Atas",
                    "description": "Wajah di sepertiga atas, konten/game di bawah",
                    "crop_mode": "smart",
                    "crop_offset_x": 0,
                    "smart_deadzone": 0.4,
                    "smart_pan_seconds": 0.4,
                    "framing_layout": "streamer_face_top",
                    "screen_mode": "full",
                    "person_shape": "rounded",
                    "person_scale": 0.4,
                    "person_offset_x": 0,
                    "person_offset_y": 0,
                    "screen_offset_x": 0,
                    "screen_offset_y": 0,
                    "screen_scale": 1.0,
                    "screen_aspect": "16:9",
                    "font": "Poppins",
                    "font_size": 46,
                    "primary_color": "#FFFFFF",
                    "active_color": "#00F0FF",
                    "subtitle_position": "bottom",
                    "margin_v": 340,
                    "outline_width": 3,
                    "shadow_depth": 2,
                    "is_uppercase": 0,
                    "motion_type": "karaoke",
                    "highlight_bg_color": "#00F0FF",
                    "enable_keyword_color": 1,
                    "keyword_color": "#10B981",
                    "enable_dynamic_scaling": 0,
                    "enable_emoji_injection": 0,
                    "glow_effect": 1,
                    "enable_vocal_dynamics": 0,
                    "audio_track_id": None,
                    "bgm_volume": 0.2,
                    "audio_mode": "mix",
                    "use_voiceover": 0,
                    "narration_voice": "id-ID-ArdiNeural",
                    "narration_style": "hook_story",
                    "is_builtin": 1
                },
                {
                    "id": "preset_streamer_face_bottom",
                    "category": "streamer",
                    "name": "Streamer: Wajah Bawah",
                    "description": "Konten/game di atas, wajah di sepertiga bawah",
                    "crop_mode": "smart",
                    "crop_offset_x": 0,
                    "smart_deadzone": 0.4,
                    "smart_pan_seconds": 0.4,
                    "framing_layout": "streamer_face_bottom",
                    "screen_mode": "full",
                    "person_shape": "rounded",
                    "person_scale": 0.4,
                    "person_offset_x": 0,
                    "person_offset_y": 0,
                    "screen_offset_x": 0,
                    "screen_offset_y": 0,
                    "screen_scale": 1.0,
                    "screen_aspect": "16:9",
                    "font": "Poppins",
                    "font_size": 46,
                    "primary_color": "#FFFFFF",
                    "active_color": "#00F0FF",
                    "subtitle_position": "middle",
                    "margin_v": 920,
                    "outline_width": 3,
                    "shadow_depth": 2,
                    "is_uppercase": 0,
                    "motion_type": "karaoke",
                    "highlight_bg_color": "#00F0FF",
                    "enable_keyword_color": 1,
                    "keyword_color": "#10B981",
                    "enable_dynamic_scaling": 0,
                    "enable_emoji_injection": 0,
                    "glow_effect": 1,
                    "enable_vocal_dynamics": 0,
                    "audio_track_id": None,
                    "bgm_volume": 0.2,
                    "audio_mode": "mix",
                    "use_voiceover": 0,
                    "narration_voice": "id-ID-ArdiNeural",
                    "narration_style": "hook_story",
                    "is_builtin": 1
                },
                {
                    "id": "preset_streamer_pip_right",
                    "category": "streamer",
                    "name": "Streamer: PIP Kanan",
                    "description": "Wajah bulat kecil di sudut kanan atas di atas konten penuh",
                    "crop_mode": "smart",
                    "crop_offset_x": 0,
                    "smart_deadzone": 0.4,
                    "smart_pan_seconds": 0.4,
                    "framing_layout": "pip_full",
                    "screen_mode": "full",
                    "person_shape": "circle",
                    "person_scale": 0.3,
                    "person_offset_x": 320,
                    "person_offset_y": -600,
                    "screen_offset_x": 0,
                    "screen_offset_y": 0,
                    "screen_scale": 1.0,
                    "screen_aspect": "16:9",
                    "font": "Poppins",
                    "font_size": 44,
                    "primary_color": "#FFFFFF",
                    "active_color": "#FFCC00",
                    "subtitle_position": "bottom",
                    "margin_v": 340,
                    "outline_width": 3,
                    "shadow_depth": 2,
                    "is_uppercase": 0,
                    "motion_type": "single_word_pop",
                    "highlight_bg_color": "#FFCC00",
                    "enable_keyword_color": 1,
                    "keyword_color": "#10B981",
                    "enable_dynamic_scaling": 1,
                    "enable_emoji_injection": 1,
                    "glow_effect": 0,
                    "enable_vocal_dynamics": 0,
                    "audio_track_id": None,
                    "bgm_volume": 0.2,
                    "audio_mode": "mix",
                    "use_voiceover": 0,
                    "narration_voice": "id-ID-ArdiNeural",
                    "narration_style": "hook_story",
                    "is_builtin": 1
                },
                {
                    "id": "preset_podcast_clean",
                    "category": "podcast",
                    "name": "Podcast: Clean White",
                    "description": "Subtitle putih bersih font besar tanpa efek untuk wawancara/diskusi",
                    "crop_mode": "smart",
                    "crop_offset_x": 0,
                    "smart_deadzone": 0.5,
                    "smart_pan_seconds": 0.5,
                    "framing_layout": "single",
                    "screen_mode": "full",
                    "person_shape": "circle",
                    "person_scale": 0.35,
                    "person_offset_x": 0,
                    "person_offset_y": 0,
                    "screen_offset_x": 0,
                    "screen_offset_y": 0,
                    "screen_scale": 1.0,
                    "screen_aspect": "16:9",
                    "font": "Inter",
                    "font_size": 52,
                    "primary_color": "#FFFFFF",
                    "active_color": "#FFFFFF",
                    "subtitle_position": "bottom",
                    "margin_v": 340,
                    "outline_width": 3,
                    "shadow_depth": 1,
                    "is_uppercase": 0,
                    "motion_type": "karaoke",
                    "highlight_bg_color": "#FFFFFF",
                    "enable_keyword_color": 0,
                    "keyword_color": "#10B981",
                    "enable_dynamic_scaling": 0,
                    "enable_emoji_injection": 0,
                    "glow_effect": 0,
                    "enable_vocal_dynamics": 0,
                    "audio_track_id": None,
                    "bgm_volume": 0.15,
                    "audio_mode": "mix",
                    "use_voiceover": 0,
                    "narration_voice": "id-ID-ArdiNeural",
                    "narration_style": "summary",
                    "is_builtin": 1
                },
                {
                    "id": "preset_podcast_cinematic",
                    "category": "podcast",
                    "name": "Podcast: Sinematik",
                    "description": "Filter cinematic + slide_up elegan untuk podcast premium",
                    "crop_mode": "smart",
                    "crop_offset_x": 0,
                    "smart_deadzone": 0.5,
                    "smart_pan_seconds": 0.5,
                    "framing_layout": "single",
                    "screen_mode": "full",
                    "person_shape": "circle",
                    "person_scale": 0.35,
                    "person_offset_x": 0,
                    "person_offset_y": 0,
                    "screen_offset_x": 0,
                    "screen_offset_y": 0,
                    "screen_scale": 1.0,
                    "screen_aspect": "16:9",
                    "video_filter": "cinematic",
                    "font": "Playfair Display",
                    "font_size": 48,
                    "primary_color": "#FFFFFF",
                    "active_color": "#FFCC00",
                    "subtitle_position": "bottom",
                    "margin_v": 340,
                    "outline_width": 3,
                    "shadow_depth": 2,
                    "is_uppercase": 0,
                    "motion_type": "slide_up",
                    "highlight_bg_color": "#FFCC00",
                    "enable_keyword_color": 1,
                    "keyword_color": "#10B981",
                    "enable_dynamic_scaling": 0,
                    "enable_emoji_injection": 0,
                    "glow_effect": 0,
                    "enable_vocal_dynamics": 0,
                    "audio_track_id": None,
                    "bgm_volume": 0.15,
                    "audio_mode": "mix",
                    "use_voiceover": 0,
                    "narration_voice": "id-ID-ArdiNeural",
                    "narration_style": "summary",
                    "is_builtin": 1
                },
                {
                    "id": "preset_edu_minimal",
                    "category": "educational",
                    "name": "Edukasi: Minimal",
                    "description": "Typewriter biru minimalis untuk materi edukasi",
                    "crop_mode": "center",
                    "crop_offset_x": 0,
                    "smart_deadzone": 0.5,
                    "smart_pan_seconds": 0.5,
                    "framing_layout": "fit_16_9_center",
                    "screen_mode": "center",
                    "person_shape": "circle",
                    "person_scale": 0.35,
                    "person_offset_x": 0,
                    "person_offset_y": 0,
                    "screen_offset_x": 0,
                    "screen_offset_y": 0,
                    "screen_scale": 1.0,
                    "screen_aspect": "16:9",
                    "font": "Inter",
                    "font_size": 46,
                    "primary_color": "#FFFFFF",
                    "active_color": "#38BDF8",
                    "subtitle_position": "bottom",
                    "margin_v": 340,
                    "outline_width": 3,
                    "shadow_depth": 1,
                    "is_uppercase": 0,
                    "motion_type": "typewriter",
                    "highlight_bg_color": "#38BDF8",
                    "enable_keyword_color": 1,
                    "keyword_color": "#38BDF8",
                    "enable_dynamic_scaling": 0,
                    "enable_emoji_injection": 0,
                    "glow_effect": 0,
                    "enable_vocal_dynamics": 0,
                    "audio_track_id": None,
                    "bgm_volume": 0.1,
                    "audio_mode": "mix",
                    "use_voiceover": 0,
                    "narration_voice": "id-ID-ArdiNeural",
                    "narration_style": "educational",
                    "is_builtin": 1
                },
                {
                    "id": "preset_motivasi_fire",
                    "category": "motivational",
                    "name": "Motivasi: Fire",
                    "description": "Hormozi pop + glow + emoji untuk kutipan motivasi membara",
                    "crop_mode": "smart",
                    "crop_offset_x": 0,
                    "smart_deadzone": 0.4,
                    "smart_pan_seconds": 0.4,
                    "framing_layout": "single",
                    "screen_mode": "full",
                    "person_shape": "circle",
                    "person_scale": 0.35,
                    "person_offset_x": 0,
                    "person_offset_y": 0,
                    "screen_offset_x": 0,
                    "screen_offset_y": 0,
                    "screen_scale": 1.0,
                    "screen_aspect": "16:9",
                    "video_filter": "warm",
                    "font": "Archivo Black",
                    "font_size": 52,
                    "primary_color": "#FFFFFF",
                    "active_color": "#F97316",
                    "subtitle_position": "middle",
                    "margin_v": 920,
                    "outline_width": 4,
                    "shadow_depth": 2,
                    "is_uppercase": 1,
                    "motion_type": "single_word_pop",
                    "highlight_bg_color": "#F97316",
                    "enable_keyword_color": 1,
                    "keyword_color": "#FACC15",
                    "enable_dynamic_scaling": 1,
                    "enable_emoji_injection": 1,
                    "glow_effect": 1,
                    "enable_vocal_dynamics": 0,
                    "audio_track_id": None,
                    "bgm_volume": 0.25,
                    "audio_mode": "mix",
                    "use_voiceover": 0,
                    "narration_voice": "id-ID-ArdiNeural",
                    "narration_style": "hook_story",
                    "is_builtin": 1
                },
                {
                    "id": "preset_gaming_impact",
                    "category": "gaming",
                    "name": "Gaming: IMPACT",
                    "description": "Background box + zoom flash uppercase untuk konten gaming",
                    "crop_mode": "smart",
                    "crop_offset_x": 0,
                    "smart_deadzone": 0.4,
                    "smart_pan_seconds": 0.4,
                    "framing_layout": "single",
                    "screen_mode": "full",
                    "person_shape": "circle",
                    "person_scale": 0.35,
                    "person_offset_x": 0,
                    "person_offset_y": 0,
                    "screen_offset_x": 0,
                    "screen_offset_y": 0,
                    "screen_scale": 1.0,
                    "screen_aspect": "16:9",
                    "video_filter": "vivid",
                    "font": "Anton",
                    "font_size": 54,
                    "primary_color": "#FFFFFF",
                    "active_color": "#00F0FF",
                    "subtitle_position": "middle",
                    "margin_v": 920,
                    "outline_width": 4,
                    "shadow_depth": 2,
                    "is_uppercase": 1,
                    "motion_type": "zoom_flash",
                    "highlight_bg_color": "#00F0FF",
                    "enable_keyword_color": 1,
                    "keyword_color": "#F43F5E",
                    "enable_dynamic_scaling": 1,
                    "enable_emoji_injection": 0,
                    "glow_effect": 1,
                    "enable_vocal_dynamics": 0,
                    "audio_track_id": None,
                    "bgm_volume": 0.25,
                    "audio_mode": "mix",
                    "use_voiceover": 0,
                    "narration_voice": "id-ID-ArdiNeural",
                    "narration_style": "hook_story",
                    "is_builtin": 1
                },
            ]

            # Remove old legacy builtins if any (e.g., split presets that are no longer valid)
            valid_builtin_ids = [p["id"] for p in default_presets]
            from sqlalchemy import bindparam
            await conn.execute(
                text("DELETE FROM text_presets WHERE is_builtin = 1 AND id NOT IN (" + ",".join(f"'{i}'" for i in valid_builtin_ids) + ")")
            )

            for p in default_presets:
                # Ensure all required keys exist
                p.setdefault("framing_layout", "single")
                p.setdefault("screen_mode", "full")
                p.setdefault("person_shape", "circle")
                p.setdefault("person_scale", 0.35)
                p.setdefault("person_offset_x", 0)
                p.setdefault("person_offset_y", 0)
                p.setdefault("screen_offset_x", 0)
                p.setdefault("screen_offset_y", 0)
                p.setdefault("screen_scale", 1.0)
                p.setdefault("screen_aspect", "16:9")
                p.setdefault("video_filter", "none")
                p.setdefault("category", "text")
                p.setdefault("thumbnail_preview", None)
                p.setdefault("enable_vocal_dynamics", 0)

                # Check if preset exists
                res_check = await conn.execute(text("SELECT COUNT(*) FROM text_presets WHERE id = :id"), {"id": p["id"]})
                exists = (res_check.scalar() or 0) > 0
                if exists:
                    await conn.execute(text("""
                        UPDATE text_presets SET
                            name = :name,
                            description = :description,
                            crop_mode = :crop_mode,
                            crop_offset_x = :crop_offset_x,
                            smart_deadzone = :smart_deadzone,
                            smart_pan_seconds = :smart_pan_seconds,
                            framing_layout = :framing_layout,
                            screen_mode = :screen_mode,
                            person_shape = :person_shape,
                            person_scale = :person_scale,
                            person_offset_x = :person_offset_x,
                            person_offset_y = :person_offset_y,
                            screen_offset_x = :screen_offset_x,
                            screen_offset_y = :screen_offset_y,
                            screen_scale = :screen_scale,
                            screen_aspect = :screen_aspect,
                            video_filter = :video_filter,
                            font = :font,
                            font_size = :font_size,
                            primary_color = :primary_color,
                            active_color = :active_color,
                            subtitle_position = :subtitle_position,
                            margin_v = :margin_v,
                            outline_width = :outline_width,
                            shadow_depth = :shadow_depth,
                            is_uppercase = :is_uppercase,
                            motion_type = :motion_type,
                            highlight_bg_color = :highlight_bg_color,
                            enable_keyword_color = :enable_keyword_color,
                            keyword_color = :keyword_color,
                            enable_dynamic_scaling = :enable_dynamic_scaling,
                            enable_emoji_injection = :enable_emoji_injection,
                            glow_effect = :glow_effect,
                            enable_vocal_dynamics = :enable_vocal_dynamics,
                            bgm_volume = :bgm_volume,
                            audio_mode = :audio_mode,
                            use_voiceover = :use_voiceover,
                            narration_voice = :narration_voice,
                            narration_style = :narration_style,
                            category = :category,
                            thumbnail_preview = :thumbnail_preview
                        WHERE id = :id AND is_builtin = 1
                    """), p)
                else:
                    await conn.execute(text("""
                        INSERT INTO text_presets (
                            id, name, description, crop_mode, crop_offset_x, smart_deadzone, smart_pan_seconds,
                            framing_layout, screen_mode, person_shape, person_scale,
                            person_offset_x, person_offset_y, screen_offset_x, screen_offset_y, screen_scale, screen_aspect, video_filter,
                            font, font_size, primary_color, active_color, subtitle_position, margin_v,
                            outline_width, shadow_depth, is_uppercase, motion_type, highlight_bg_color,
                            enable_keyword_color, keyword_color, enable_dynamic_scaling, enable_emoji_injection, glow_effect, enable_vocal_dynamics,
                            audio_track_id, bgm_volume, audio_mode,
                            use_voiceover, narration_voice, narration_style, category, thumbnail_preview, is_builtin, created_at
                        )
                        VALUES (
                            :id, :name, :description, :crop_mode, :crop_offset_x, :smart_deadzone, :smart_pan_seconds,
                            :framing_layout, :screen_mode, :person_shape, :person_scale,
                            :person_offset_x, :person_offset_y, :screen_offset_x, :screen_offset_y, :screen_scale, :screen_aspect, :video_filter,
                            :font, :font_size, :primary_color, :active_color, :subtitle_position, :margin_v,
                            :outline_width, :shadow_depth, :is_uppercase, :motion_type, :highlight_bg_color,
                            :enable_keyword_color, :keyword_color, :enable_dynamic_scaling, :enable_emoji_injection, :glow_effect, :enable_vocal_dynamics,
                            :audio_track_id, :bgm_volume, :audio_mode,
                            :use_voiceover, :narration_voice, :narration_style, :category, :thumbnail_preview, :is_builtin, CURRENT_TIMESTAMP
                        )
                    """), p)
