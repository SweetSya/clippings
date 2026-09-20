import uuid
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.core.security import get_current_session
from app.models import TextPreset
from app.services.pipeline_rules import (
    get_pipeline_config,
    save_pipeline_config,
    match_pipeline_preset,
    DEFAULT_PIPELINE_RULES
)
from app.services.waha_service import send_waha_message, get_waha_settings

router = APIRouter(prefix="/pipeline", tags=["Automated Pipeline"], dependencies=[Depends(get_current_session)])


class PipelineRuleItem(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    name: Optional[str] = None
    context: str
    preset_id: str


class PipelineConfigUpdate(BaseModel):
    auto_clip_enabled: Optional[bool] = None
    min_score: Optional[int] = Field(default=None, ge=0, le=100)
    context_rules: Optional[List[PipelineRuleItem]] = None
    default_preset_id: Optional[str] = None
    auto_upload_youtube: Optional[bool] = None
    auto_upload_gdrive: Optional[bool] = None
    auto_notify_whatsapp: Optional[bool] = None
    whatsapp_target_chat: Optional[str] = None


class MatchTestRequest(BaseModel):
    title: Optional[str] = None
    video_type: Optional[str] = None
    description: Optional[str] = None
    clip_title: Optional[str] = None


class TestWhatsAppRequest(BaseModel):
    target_chat: Optional[str] = None


@router.get("/config")
async def get_config(db: AsyncSession = Depends(get_db)):
    """
    Mengambil setelan pipeline otomasi saat ini (skor minimum, context rules, post-render actions).
    """
    config = await get_pipeline_config(db)
    return config


@router.post("/config")
async def update_config(payload: PipelineConfigUpdate, db: AsyncSession = Depends(get_db)):
    """
    Memperbarui konfigurasi pipeline otomasi.
    """
    data = payload.model_dump(exclude_unset=True)
    if "context_rules" in data and data["context_rules"] is not None:
        data["context_rules"] = [
            r if isinstance(r, dict) else r.model_dump()
            for r in data["context_rules"]
        ]
    updated = await save_pipeline_config(db, data)
    return {"ok": True, "config": updated}


@router.post("/test-match")
async def test_match(payload: MatchTestRequest, db: AsyncSession = Depends(get_db)):
    """
    Menguji kecocokan judul video / tipe video terhadap rules context-to-preset yang aktif.
    """
    config = await get_pipeline_config(db)
    rules = config.get("context_rules", DEFAULT_PIPELINE_RULES)
    default_preset_id = config.get("default_preset_id")

    selected_id, matched_rule, reason = match_pipeline_preset(
        video_type=payload.video_type,
        video_title=payload.title,
        video_desc=payload.description,
        clip_title=payload.clip_title,
        rules=rules,
        default_preset_id=default_preset_id,
        rec_preset_id=None
    )

    preset_name = None
    if selected_id:
        p = await db.get(TextPreset, selected_id)
        if p:
            preset_name = p.name

    return {
        "matched": matched_rule is not None,
        "selected_preset_id": selected_id,
        "selected_preset_name": preset_name or selected_id,
        "matched_rule": matched_rule,
        "match_reason": reason
    }


@router.post("/test-whatsapp")
async def test_whatsapp(payload: TestWhatsAppRequest = TestWhatsAppRequest(), db: AsyncSession = Depends(get_db)):
    """
    Mengirimkan pesan uji coba konsolidasi pipeline ke WhatsApp untuk memverifikasi integrasi.
    """
    config = await get_pipeline_config(db)
    target = (payload.target_chat or "").strip() or config.get("whatsapp_target_chat")
    if not target:
        waha_cfg = await get_waha_settings(db)
        target = waha_cfg.get("paired_chat_id")

    if not target:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Chat WhatsApp tujuan belum ditentukan dan belum ada akun WA yang dipasangkan."
        )

    test_msg = (
        "🧪 *Test Pipeline WhatsApp Notification*\n"
        "Halo! Ini adalah contoh notifikasi konsolidasi pipeline Ember Shorts.\n\n"
        "📹 Video: *Contoh Video Tutorial Gaming*\n"
        "Semua klip Shorts untuk video ini telah selesai di-upload ke YouTube:\n\n"
        "1. 🎬 *Momen Clutch Menang 1 vs 5*\n"
        "   🔗 https://youtube.com/shorts/test_sample_1\n\n"
        "2. 🎬 *Tips Headshot Akurat*\n"
        "   🔗 https://youtube.com/shorts/test_sample_2\n\n"
        "📊 *Total:* 2 Shorts Berhasil Di-upload\n"
        "✨ Pipeline otomatisasi Anda telah terhubung dan berfungsi normal!"
    )

    success = await send_waha_message(db, target, test_msg)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Gagal mengirim pesan ke WhatsApp. Pastikan bot WAHA aktif dan terkoneksi."
        )

    return {"ok": True, "message": f"Pesan tes berhasil dikirim ke {target}"}
