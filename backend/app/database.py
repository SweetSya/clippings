from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from app.config import settings

# Configure engine arguments based on driver
engine_kwargs = {"echo": False}
if settings.DATABASE_URL.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    engine_kwargs["pool_pre_ping"] = True
    engine_kwargs["pool_recycle"] = 3600

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

            # Migrate clip_candidates columns
            res_clips = await conn.execute(text("PRAGMA table_info(clip_candidates)"))
            clip_cols = [row[1] for row in res_clips.fetchall()]
            if clip_cols and "narration_text" not in clip_cols:
                await conn.execute(text("ALTER TABLE clip_candidates ADD COLUMN narration_text TEXT"))
            if clip_cols and "narration_voice" not in clip_cols:
                await conn.execute(text("ALTER TABLE clip_candidates ADD COLUMN narration_voice VARCHAR(50)"))
            if clip_cols and "narration_audio_path" not in clip_cols:
                await conn.execute(text("ALTER TABLE clip_candidates ADD COLUMN narration_audio_path VARCHAR(500)"))

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
                    "font": "Poppins",
                    "font_size": 48,
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
                    "name": "Cyberpunk Neon",
                    "description": "Gaya futuristik neon cyan-kuning dengan efek glow neon dan karaoke highlight",
                    "crop_mode": "smart",
                    "crop_offset_x": 0,
                    "smart_deadzone": 0.3,
                    "smart_pan_seconds": 0.3,
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
                    "audio_track_id": None,
                    "bgm_volume": 0.25,
                    "audio_mode": "mix",
                    "use_voiceover": 0,
                    "narration_voice": "id-ID-ArdiNeural",
                    "narration_style": "hook_story",
                    "is_builtin": 1
                },
                {
                    "id": "preset_minimalist",
                    "name": "Minimalist Clean",
                    "description": "Tampilan bersih minimalis slide-up elegan di bawah layar untuk dialog santai dan podcast",
                    "crop_mode": "center",
                    "crop_offset_x": 0,
                    "smart_deadzone": 0.5,
                    "smart_pan_seconds": 0.5,
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
                    "audio_track_id": None,
                    "bgm_volume": 0.15,
                    "audio_mode": "mix",
                    "use_voiceover": 0,
                    "narration_voice": "id-ID-GadisNeural",
                    "narration_style": "summary",
                    "is_builtin": 1
                },
                {
                    "id": "preset_documentary",
                    "name": "Classic Documentary",
                    "description": "Serif sinematik dengan animasi kata typewriter untuk narasi mendalam",
                    "crop_mode": "smart",
                    "crop_offset_x": 0,
                    "smart_deadzone": 0.5,
                    "smart_pan_seconds": 0.8,
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
                    "audio_track_id": None,
                    "bgm_volume": 0.2,
                    "audio_mode": "mix",
                    "use_voiceover": 0,
                    "narration_voice": "id-ID-ArdiNeural",
                    "narration_style": "hook_story",
                    "is_builtin": 1
                },
                {
                    "id": "preset_golden_lux",
                    "name": "Golden Luxury",
                    "description": "Gaya premium highlighter sticker box emas di tengah layar untuk quotes & motivasi",
                    "crop_mode": "center",
                    "crop_offset_x": 0,
                    "smart_deadzone": 0.5,
                    "smart_pan_seconds": 0.5,
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
                    "audio_track_id": None,
                    "bgm_volume": 0.2,
                    "audio_mode": "mix",
                    "use_voiceover": 0,
                    "narration_voice": "id-ID-GadisNeural",
                    "narration_style": "hook_story",
                    "is_builtin": 1
                },
            ]

            for p in default_presets:
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
                            bgm_volume = :bgm_volume,
                            audio_mode = :audio_mode,
                            use_voiceover = :use_voiceover,
                            narration_voice = :narration_voice,
                            narration_style = :narration_style
                        WHERE id = :id AND is_builtin = 1
                    """), p)
                else:
                    await conn.execute(text("""
                        INSERT INTO text_presets (
                            id, name, description, crop_mode, crop_offset_x, smart_deadzone, smart_pan_seconds,
                            font, font_size, primary_color, active_color, subtitle_position, margin_v,
                            outline_width, shadow_depth, is_uppercase, motion_type, highlight_bg_color,
                            enable_keyword_color, keyword_color, enable_dynamic_scaling, enable_emoji_injection, glow_effect,
                            audio_track_id, bgm_volume, audio_mode,
                            use_voiceover, narration_voice, narration_style, is_builtin, created_at
                        )
                        VALUES (
                            :id, :name, :description, :crop_mode, :crop_offset_x, :smart_deadzone, :smart_pan_seconds,
                            :font, :font_size, :primary_color, :active_color, :subtitle_position, :margin_v,
                            :outline_width, :shadow_depth, :is_uppercase, :motion_type, :highlight_bg_color,
                            :enable_keyword_color, :keyword_color, :enable_dynamic_scaling, :enable_emoji_injection, :glow_effect,
                            :audio_track_id, :bgm_volume, :audio_mode,
                            :use_voiceover, :narration_voice, :narration_style, :is_builtin, CURRENT_TIMESTAMP
                        )
                    """), p)
