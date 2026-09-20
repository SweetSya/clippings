import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import ValidationError
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import TextPreset
from app.schemas import TextPresetResponse, TextPresetCreate, TextPresetUpdate
from app.core.security import get_current_session

router = APIRouter(prefix="/presets", tags=["Unified Presets"], dependencies=[Depends(get_current_session)])


def _to_response(p: TextPreset) -> TextPresetResponse:
    return TextPresetResponse(
        id=p.id,
        name=p.name,
        description=p.description,
        crop_mode=p.crop_mode or "center",
        crop_offset_x=p.crop_offset_x or 0,
        smart_deadzone=p.smart_deadzone if p.smart_deadzone is not None else 0.5,
        smart_pan_seconds=p.smart_pan_seconds if p.smart_pan_seconds is not None else 0.5,
        framing_layout=p.framing_layout or "single",
        screen_mode=p.screen_mode or "full",
        person_shape=p.person_shape or "circle",
        person_scale=p.person_scale if p.person_scale is not None else 0.45,
        person_offset_x=p.person_offset_x if p.person_offset_x is not None else 0,
        person_offset_y=p.person_offset_y if p.person_offset_y is not None else 0,
        screen_offset_x=p.screen_offset_x if p.screen_offset_x is not None else 0,
        screen_offset_y=p.screen_offset_y if p.screen_offset_y is not None else 0,
        screen_scale=p.screen_scale if p.screen_scale is not None else 1.0,
        screen_aspect=p.screen_aspect or "16:9",
        video_filter=p.video_filter or "none",
        font=p.font or "Poppins",
        font_size=p.font_size or 44,
        primary_color=p.primary_color or "#FFFFFF",
        active_color=p.active_color or "#FFCC00",
        subtitle_position=p.subtitle_position or "bottom",
        margin_v=p.margin_v if p.margin_v is not None else 340,
        outline_width=p.outline_width if p.outline_width is not None else 3,
        shadow_depth=p.shadow_depth if p.shadow_depth is not None else 1,
        is_uppercase=bool(p.is_uppercase),
        motion_type=p.motion_type or "karaoke",
        highlight_bg_color=p.highlight_bg_color or "#FFCC00",
        enable_keyword_color=bool(p.enable_keyword_color) if p.enable_keyword_color is not None else True,
        keyword_color=p.keyword_color or "#10B981",
        enable_dynamic_scaling=bool(p.enable_dynamic_scaling),
        enable_emoji_injection=bool(p.enable_emoji_injection),
        glow_effect=bool(p.glow_effect),
        enable_vocal_dynamics=bool(p.enable_vocal_dynamics),
        audio_track_id=p.audio_track_id,
        bgm_volume=p.bgm_volume if p.bgm_volume is not None else 0.2,
        audio_mode=p.audio_mode or "mix",
        use_voiceover=bool(p.use_voiceover),
        narration_voice=p.narration_voice or "id-ID-ArdiNeural",
        narration_style=p.narration_style or "hook_story",
        enable_intro_title=bool(p.enable_intro_title),
        intro_title_duration=p.intro_title_duration if p.intro_title_duration is not None else 2.0,
        intro_title_style=p.intro_title_style or "fade_slide",
        intro_title_tts=bool(p.intro_title_tts) if getattr(p, "intro_title_tts", None) is not None else True,
        intro_title_voice=getattr(p, "intro_title_voice", None) or "id-ID-ArdiNeural",
        intro_title_pause=bool(getattr(p, "intro_title_pause", False)),
        enable_outro_cta=bool(p.enable_outro_cta),
        outro_cta_text=p.outro_cta_text or "Follow untuk lebih banyak!",
        outro_cta_duration=p.outro_cta_duration if p.outro_cta_duration is not None else 2.0,
        enable_lower_third=bool(p.enable_lower_third),
        lower_third_text=p.lower_third_text,
        sticker_path=p.sticker_path,
        sticker_position=p.sticker_position or "top_right",
        sticker_scale=p.sticker_scale if p.sticker_scale is not None else 0.15,
        sfx_on_hook=bool(p.sfx_on_hook),
        sfx_hook_sfx_id=p.sfx_hook_sfx_id,
        sfx_hook_threshold=p.sfx_hook_threshold if p.sfx_hook_threshold is not None else 90,
        category=p.category or "text",
        thumbnail_preview=p.thumbnail_preview,
        is_builtin=bool(p.is_builtin),
        created_at=p.created_at.isoformat() if p.created_at else ""
    )


@router.get("", response_model=List[TextPresetResponse])
async def list_presets(
    category: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    List all unified presets (combining visual, text, audio, and voiceover settings).
    Built-in presets are listed first, followed by custom presets sorted by newest.
    Filter by category with ?category=streamer (text, full, streamer, podcast, educational, motivational, gaming).
    """
    stmt = select(TextPreset)
    if category:
        stmt = stmt.where(TextPreset.category == category.strip().lower())
    stmt = stmt.order_by(desc(TextPreset.is_builtin), desc(TextPreset.created_at))
    rows = (await db.execute(stmt)).scalars().all()
    return [_to_response(r) for r in rows]


@router.post("/reset-builtins", response_model=List[TextPresetResponse])
async def reset_builtin_presets(db: AsyncSession = Depends(get_db)):
    """
    Refresh and restore all official built-in presets to their canonical defaults.
    Custom presets are preserved.
    """
    from app.database import init_db
    await init_db()
    stmt = select(TextPreset).order_by(desc(TextPreset.is_builtin), desc(TextPreset.created_at))
    rows = (await db.execute(stmt)).scalars().all()
    return [_to_response(r) for r in rows]


@router.get("/{preset_id}", response_model=TextPresetResponse)
async def get_preset(preset_id: str, db: AsyncSession = Depends(get_db)):
    preset = await db.get(TextPreset, preset_id)
    if not preset:
        raise HTTPException(status_code=404, detail="Preset tidak ditemukan.")
    return _to_response(preset)


def _build_preset_from_validated(validated: TextPresetCreate, name_override: str = None) -> TextPreset:
    """Bangun row TextPreset custom dari payload tervalidasi (selalu is_builtin=False)."""
    return TextPreset(
        id=uuid.uuid4().hex,
        name=(name_override or validated.name).strip(),
        description=(validated.description or "").strip() or None,
        crop_mode=validated.crop_mode or "center",
        crop_offset_x=validated.crop_offset_x or 0,
        smart_deadzone=validated.smart_deadzone if validated.smart_deadzone is not None else 0.5,
        smart_pan_seconds=validated.smart_pan_seconds if validated.smart_pan_seconds is not None else 0.5,
        framing_layout=validated.framing_layout or "single",
        screen_mode=validated.screen_mode or "full",
        person_shape=validated.person_shape or "circle",
        person_scale=validated.person_scale if validated.person_scale is not None else 0.45,
        person_offset_x=validated.person_offset_x if validated.person_offset_x is not None else 0,
        person_offset_y=validated.person_offset_y if validated.person_offset_y is not None else 0,
        screen_offset_x=validated.screen_offset_x if validated.screen_offset_x is not None else 0,
        screen_offset_y=validated.screen_offset_y if validated.screen_offset_y is not None else 0,
        screen_scale=validated.screen_scale if validated.screen_scale is not None else 1.0,
        screen_aspect=validated.screen_aspect or "16:9",
        video_filter=(validated.video_filter or "none"),
        font=validated.font.strip(),
        font_size=validated.font_size,
        primary_color=validated.primary_color.strip(),
        active_color=validated.active_color.strip(),
        subtitle_position=validated.subtitle_position.strip(),
        margin_v=validated.margin_v if validated.margin_v is not None else 340,
        outline_width=validated.outline_width,
        shadow_depth=validated.shadow_depth,
        is_uppercase=validated.is_uppercase,
        motion_type=validated.motion_type or "karaoke",
        highlight_bg_color=validated.highlight_bg_color or "#FFCC00",
        enable_keyword_color=validated.enable_keyword_color,
        keyword_color=validated.keyword_color or "#10B981",
        enable_dynamic_scaling=validated.enable_dynamic_scaling,
        enable_emoji_injection=validated.enable_emoji_injection,
        glow_effect=validated.glow_effect,
        enable_vocal_dynamics=validated.enable_vocal_dynamics,
        audio_track_id=validated.audio_track_id,
        bgm_volume=validated.bgm_volume if validated.bgm_volume is not None else 0.2,
        audio_mode=validated.audio_mode or "mix",
        use_voiceover=validated.use_voiceover,
        narration_voice=validated.narration_voice,
        narration_style=validated.narration_style,
        enable_intro_title=validated.enable_intro_title,
        intro_title_duration=validated.intro_title_duration if validated.intro_title_duration is not None else 2.0,
        intro_title_style=validated.intro_title_style or "fade_slide",
        intro_title_tts=validated.intro_title_tts if validated.intro_title_tts is not None else True,
        intro_title_voice=validated.intro_title_voice or "id-ID-ArdiNeural",
        intro_title_pause=bool(validated.intro_title_pause),
        enable_outro_cta=validated.enable_outro_cta,
        outro_cta_text=validated.outro_cta_text or "Follow untuk lebih banyak!",
        outro_cta_duration=validated.outro_cta_duration if validated.outro_cta_duration is not None else 2.0,
        enable_lower_third=validated.enable_lower_third,
        lower_third_text=(validated.lower_third_text or "").strip() or None,
        sticker_path=(validated.sticker_path or "").strip() or None,
        sticker_position=validated.sticker_position or "top_right",
        sticker_scale=validated.sticker_scale if validated.sticker_scale is not None else 0.15,
        sfx_on_hook=validated.sfx_on_hook,
        sfx_hook_sfx_id=(validated.sfx_hook_sfx_id or "").strip() or None,
        sfx_hook_threshold=validated.sfx_hook_threshold if validated.sfx_hook_threshold is not None else 90,
        category=(validated.category or "text").strip() or "text",
        thumbnail_preview=(validated.thumbnail_preview or "").strip() or None,
        is_builtin=False
    )


@router.get("/{preset_id}/export")
async def export_preset(preset_id: str, db: AsyncSession = Depends(get_db)):
    """
    Export preset sebagai JSON untuk dibagikan/di-backup.
    Bisa export builtin maupun custom; metadata internal (is_builtin/created_at) dibuang.
    """
    preset = await db.get(TextPreset, preset_id)
    if not preset:
        raise HTTPException(status_code=404, detail="Preset tidak ditemukan.")
    data = _to_response(preset).model_dump()
    data.pop("is_builtin", None)
    data.pop("created_at", None)
    return {
        "preset": data,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "app_version": "2.2.0",
    }


@router.post("/import", response_model=TextPresetResponse, status_code=status.HTTP_201_CREATED)
async def import_preset(payload: Dict[str, Any], db: AsyncSession = Depends(get_db)):
    """
    Import preset dari JSON hasil export. Selalu jadi custom preset baru.
    Terima format terbungkus {"preset": {...}} maupun raw {...}.
    """
    if not isinstance(payload, dict):
        raise HTTPException(status_code=422, detail="Format JSON preset tidak valid.")
    raw = payload.get("preset", payload)
    if not isinstance(raw, dict):
        raise HTTPException(status_code=422, detail="Format JSON preset tidak valid.")
    allowed = set(TextPresetCreate.model_fields.keys())
    filtered = {k: v for k, v in raw.items() if k in allowed}
    try:
        validated = TextPresetCreate(**filtered)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=f"Validasi preset gagal: {e.errors()}")
    preset = _build_preset_from_validated(validated)
    db.add(preset)
    await db.commit()
    await db.refresh(preset)
    return _to_response(preset)


@router.post("/{preset_id}/duplicate", response_model=TextPresetResponse, status_code=status.HTTP_201_CREATED)
async def duplicate_preset(preset_id: str, db: AsyncSession = Depends(get_db)):
    """
    Duplikat preset (termasuk builtin) sebagai starting point custom baru.
    """
    src = await db.get(TextPreset, preset_id)
    if not src:
        raise HTTPException(status_code=404, detail="Preset tidak ditemukan.")
    current = _to_response(src).model_dump()
    allowed = set(TextPresetCreate.model_fields.keys())
    filtered = {k: v for k, v in current.items() if k in allowed}
    try:
        validated = TextPresetCreate(**filtered)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=f"Preset sumber tidak valid untuk diduplikat: {e.errors()}")
    preset = _build_preset_from_validated(validated, name_override=f"Salinan dari {src.name}"[:100])
    db.add(preset)
    await db.commit()
    await db.refresh(preset)
    return _to_response(preset)


@router.post("", response_model=TextPresetResponse, status_code=status.HTTP_201_CREATED)
async def create_preset(payload: TextPresetCreate, db: AsyncSession = Depends(get_db)):
    """
    Create a new custom unified preset (visual + text + audio + voiceover).
    """
    preset = TextPreset(
        id=uuid.uuid4().hex,
        name=payload.name.strip(),
        description=(payload.description or "").strip() or None,
        crop_mode=payload.crop_mode or "center",
        crop_offset_x=payload.crop_offset_x or 0,
        smart_deadzone=payload.smart_deadzone if payload.smart_deadzone is not None else 0.5,
        smart_pan_seconds=payload.smart_pan_seconds if payload.smart_pan_seconds is not None else 0.5,
        framing_layout=payload.framing_layout or "single",
        screen_mode=payload.screen_mode or "full",
        person_shape=payload.person_shape or "circle",
        person_scale=payload.person_scale if payload.person_scale is not None else 0.45,
        person_offset_x=payload.person_offset_x if payload.person_offset_x is not None else 0,
        person_offset_y=payload.person_offset_y if payload.person_offset_y is not None else 0,
        screen_offset_x=payload.screen_offset_x if payload.screen_offset_x is not None else 0,
        screen_offset_y=payload.screen_offset_y if payload.screen_offset_y is not None else 0,
        screen_scale=payload.screen_scale if payload.screen_scale is not None else 1.0,
        screen_aspect=payload.screen_aspect or "16:9",
        video_filter=(payload.video_filter or "none"),
        font=payload.font.strip(),
        font_size=payload.font_size,
        primary_color=payload.primary_color.strip(),
        active_color=payload.active_color.strip(),
        subtitle_position=payload.subtitle_position.strip(),
        margin_v=payload.margin_v if payload.margin_v is not None else 340,
        outline_width=payload.outline_width,
        shadow_depth=payload.shadow_depth,
        is_uppercase=payload.is_uppercase,
        motion_type=payload.motion_type or "karaoke",
        highlight_bg_color=payload.highlight_bg_color or "#FFCC00",
        enable_keyword_color=payload.enable_keyword_color,
        keyword_color=payload.keyword_color or "#10B981",
        enable_dynamic_scaling=payload.enable_dynamic_scaling,
        enable_emoji_injection=payload.enable_emoji_injection,
        glow_effect=payload.glow_effect,
        enable_vocal_dynamics=payload.enable_vocal_dynamics,
        audio_track_id=payload.audio_track_id,
        bgm_volume=payload.bgm_volume if payload.bgm_volume is not None else 0.2,
        audio_mode=payload.audio_mode or "mix",
        use_voiceover=payload.use_voiceover,
        narration_voice=payload.narration_voice,
        narration_style=payload.narration_style,
        enable_intro_title=payload.enable_intro_title,
        intro_title_duration=payload.intro_title_duration if payload.intro_title_duration is not None else 2.0,
        intro_title_style=payload.intro_title_style or "fade_slide",
        intro_title_tts=payload.intro_title_tts if payload.intro_title_tts is not None else True,
        intro_title_voice=payload.intro_title_voice or "id-ID-ArdiNeural",
        intro_title_pause=bool(payload.intro_title_pause),
        enable_outro_cta=payload.enable_outro_cta,
        outro_cta_text=payload.outro_cta_text or "Follow untuk lebih banyak!",
        outro_cta_duration=payload.outro_cta_duration if payload.outro_cta_duration is not None else 2.0,
        enable_lower_third=payload.enable_lower_third,
        lower_third_text=(payload.lower_third_text or "").strip() or None,
        sticker_path=(payload.sticker_path or "").strip() or None,
        sticker_position=payload.sticker_position or "top_right",
        sticker_scale=payload.sticker_scale if payload.sticker_scale is not None else 0.15,
        sfx_on_hook=payload.sfx_on_hook,
        sfx_hook_sfx_id=(payload.sfx_hook_sfx_id or "").strip() or None,
        sfx_hook_threshold=payload.sfx_hook_threshold if payload.sfx_hook_threshold is not None else 90,
        category=(payload.category or "text").strip() or "text",
        thumbnail_preview=(payload.thumbnail_preview or "").strip() or None,
        is_builtin=False
    )
    db.add(preset)
    await db.commit()
    await db.refresh(preset)
    return _to_response(preset)


@router.put("/{preset_id}", response_model=TextPresetResponse)
async def update_preset(preset_id: str, payload: TextPresetUpdate, db: AsyncSession = Depends(get_db)):
    """
    Update a custom unified preset. Built-in presets cannot be updated.
    """
    preset = await db.get(TextPreset, preset_id)
    if not preset:
        raise HTTPException(status_code=404, detail="Preset tidak ditemukan.")
    if preset.is_builtin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Preset bawaan sistem tidak dapat diubah."
        )

    if payload.name is not None:
        preset.name = payload.name.strip()
    if payload.description is not None:
        preset.description = payload.description.strip()
    if payload.crop_mode is not None:
        preset.crop_mode = payload.crop_mode
    if payload.crop_offset_x is not None:
        preset.crop_offset_x = payload.crop_offset_x
    if payload.smart_deadzone is not None:
        preset.smart_deadzone = payload.smart_deadzone
    if payload.smart_pan_seconds is not None:
        preset.smart_pan_seconds = payload.smart_pan_seconds
    if payload.framing_layout is not None:
        preset.framing_layout = payload.framing_layout
    if payload.screen_mode is not None:
        preset.screen_mode = payload.screen_mode
    if payload.person_shape is not None:
        preset.person_shape = payload.person_shape
    if payload.person_scale is not None:
        preset.person_scale = payload.person_scale
    if payload.person_offset_x is not None:
        preset.person_offset_x = payload.person_offset_x
    if payload.person_offset_y is not None:
        preset.person_offset_y = payload.person_offset_y
    if payload.screen_offset_x is not None:
        preset.screen_offset_x = payload.screen_offset_x
    if payload.screen_offset_y is not None:
        preset.screen_offset_y = payload.screen_offset_y
    if payload.screen_scale is not None:
        preset.screen_scale = payload.screen_scale
    if payload.screen_aspect is not None:
        preset.screen_aspect = payload.screen_aspect
    if payload.video_filter is not None:
        preset.video_filter = payload.video_filter or "none"
    if payload.font is not None:
        preset.font = payload.font.strip()
    if payload.font_size is not None:
        preset.font_size = payload.font_size
    if payload.primary_color is not None:
        preset.primary_color = payload.primary_color.strip()
    if payload.active_color is not None:
        preset.active_color = payload.active_color.strip()
    if payload.subtitle_position is not None:
        preset.subtitle_position = payload.subtitle_position.strip()
    if payload.margin_v is not None:
        preset.margin_v = payload.margin_v
    if payload.outline_width is not None:
        preset.outline_width = payload.outline_width
    if payload.shadow_depth is not None:
        preset.shadow_depth = payload.shadow_depth
    if payload.is_uppercase is not None:
        preset.is_uppercase = payload.is_uppercase
    if payload.motion_type is not None:
        preset.motion_type = payload.motion_type
    if payload.highlight_bg_color is not None:
        preset.highlight_bg_color = payload.highlight_bg_color
    if payload.enable_keyword_color is not None:
        preset.enable_keyword_color = payload.enable_keyword_color
    if payload.keyword_color is not None:
        preset.keyword_color = payload.keyword_color
    if payload.enable_dynamic_scaling is not None:
        preset.enable_dynamic_scaling = payload.enable_dynamic_scaling
    if payload.enable_emoji_injection is not None:
        preset.enable_emoji_injection = payload.enable_emoji_injection
    if payload.glow_effect is not None:
        preset.glow_effect = payload.glow_effect
    if payload.enable_vocal_dynamics is not None:
        preset.enable_vocal_dynamics = payload.enable_vocal_dynamics
    if payload.audio_track_id is not None:
        preset.audio_track_id = payload.audio_track_id
    if payload.bgm_volume is not None:
        preset.bgm_volume = payload.bgm_volume
    if payload.audio_mode is not None:
        preset.audio_mode = payload.audio_mode
    if payload.use_voiceover is not None:
        preset.use_voiceover = payload.use_voiceover
    if payload.narration_voice is not None:
        preset.narration_voice = payload.narration_voice
    if payload.narration_style is not None:
        preset.narration_style = payload.narration_style
    if payload.enable_intro_title is not None:
        preset.enable_intro_title = payload.enable_intro_title
    if payload.intro_title_duration is not None:
        preset.intro_title_duration = payload.intro_title_duration
    if payload.intro_title_style is not None:
        preset.intro_title_style = payload.intro_title_style
    if payload.intro_title_tts is not None:
        preset.intro_title_tts = payload.intro_title_tts
    if payload.intro_title_voice is not None:
        preset.intro_title_voice = payload.intro_title_voice
    if payload.intro_title_pause is not None:
        preset.intro_title_pause = payload.intro_title_pause
    if payload.enable_outro_cta is not None:
        preset.enable_outro_cta = payload.enable_outro_cta
    if payload.outro_cta_text is not None:
        preset.outro_cta_text = payload.outro_cta_text
    if payload.outro_cta_duration is not None:
        preset.outro_cta_duration = payload.outro_cta_duration
    if payload.enable_lower_third is not None:
        preset.enable_lower_third = payload.enable_lower_third
    if payload.lower_third_text is not None:
        preset.lower_third_text = payload.lower_third_text
    if payload.sticker_path is not None:
        preset.sticker_path = (payload.sticker_path or "").strip() or None
    if payload.sticker_position is not None:
        preset.sticker_position = payload.sticker_position
    if payload.sticker_scale is not None:
        preset.sticker_scale = payload.sticker_scale
    if payload.sfx_on_hook is not None:
        preset.sfx_on_hook = payload.sfx_on_hook
    if payload.sfx_hook_sfx_id is not None:
        preset.sfx_hook_sfx_id = (payload.sfx_hook_sfx_id or "").strip() or None
    if payload.sfx_hook_threshold is not None:
        preset.sfx_hook_threshold = payload.sfx_hook_threshold
    if payload.category is not None:
        preset.category = (payload.category or "text").strip() or "text"
    if payload.thumbnail_preview is not None:
        preset.thumbnail_preview = (payload.thumbnail_preview or "").strip() or None

    await db.commit()
    await db.refresh(preset)
    return _to_response(preset)


@router.delete("/{preset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_preset(preset_id: str, db: AsyncSession = Depends(get_db)):
    """
    Delete a custom preset. Built-in presets cannot be deleted.
    """
    preset = await db.get(TextPreset, preset_id)
    if not preset:
        raise HTTPException(status_code=404, detail="Preset tidak ditemukan.")
    if preset.is_builtin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Preset bawaan sistem tidak dapat dihapus."
        )

    await db.delete(preset)
    await db.commit()
    return None
