import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
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
        audio_track_id=p.audio_track_id,
        bgm_volume=p.bgm_volume if p.bgm_volume is not None else 0.2,
        audio_mode=p.audio_mode or "mix",
        use_voiceover=bool(p.use_voiceover),
        narration_voice=p.narration_voice or "id-ID-ArdiNeural",
        narration_style=p.narration_style or "hook_story",
        is_builtin=bool(p.is_builtin),
        created_at=p.created_at.isoformat() if p.created_at else ""
    )


@router.get("", response_model=List[TextPresetResponse])
async def list_presets(db: AsyncSession = Depends(get_db)):
    """
    List all unified presets (combining visual, text, audio, and voiceover settings).
    Built-in presets are listed first, followed by custom presets sorted by newest.
    """
    stmt = select(TextPreset).order_by(desc(TextPreset.is_builtin), desc(TextPreset.created_at))
    rows = (await db.execute(stmt)).scalars().all()
    return [_to_response(r) for r in rows]


@router.get("/{preset_id}", response_model=TextPresetResponse)
async def get_preset(preset_id: str, db: AsyncSession = Depends(get_db)):
    preset = await db.get(TextPreset, preset_id)
    if not preset:
        raise HTTPException(status_code=404, detail="Preset tidak ditemukan.")
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
        audio_track_id=payload.audio_track_id,
        bgm_volume=payload.bgm_volume if payload.bgm_volume is not None else 0.2,
        audio_mode=payload.audio_mode or "mix",
        use_voiceover=payload.use_voiceover,
        narration_voice=payload.narration_voice,
        narration_style=payload.narration_style,
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
