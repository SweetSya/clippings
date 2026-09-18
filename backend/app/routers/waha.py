import logging
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import AppSetting
from app.schemas import (
    WahaConfigRequest,
    WahaStatusResponse,
    WahaTestMessageRequest
)
from app.core.security import get_current_session
from app.services.waha_service import (
    get_waha_settings,
    probe_waha_session_status,
    start_waha_session,
    logout_waha_session,
    regenerate_sync_token,
    send_waha_message,
    process_incoming_waha_message,
    _set_val
)

logger = logging.getLogger("waha")

router = APIRouter(prefix="/waha", tags=["WhatsApp (WAHA)"], dependencies=[Depends(get_current_session)])
public_router = APIRouter(prefix="/waha", tags=["WhatsApp (WAHA)"])

# ----------------- Public Webhook -----------------
@public_router.post("/webhook")
async def waha_webhook_handler(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Public webhook receiver for incoming WhatsApp events from WAHA container.
    """
    try:
        data = await request.json()
    except Exception as e:
        logger.warning(f"Invalid JSON received on WAHA webhook: {e}")
        return {"ok": False, "error": "Invalid JSON"}

    try:
        result = await process_incoming_waha_message(db, data)
        return result
    except Exception as e:
        logger.error(f"Error handling WAHA webhook: {e}", exc_info=True)
        return {"ok": False, "error": str(e)}

# ----------------- Protected API Endpoints -----------------

@router.get("/status", response_model=WahaStatusResponse)
async def get_status(db: AsyncSession = Depends(get_db)):
    """
    Get WAHA service status, live QR code (if pending scan), paired chat info, and pairing token.
    """
    cfg = await get_waha_settings(db)
    session_status_data = await probe_waha_session_status(
        api_url=cfg["api_url"],
        session_name=cfg["session_name"],
        api_key=cfg["api_key"]
    )

    return WahaStatusResponse(
        enabled=cfg["enabled"],
        api_url=cfg["api_url"],
        session_name=cfg["session_name"],
        session_status=session_status_data["session_status"],
        qr_code=session_status_data["qr_code"],
        sync_token=cfg["sync_token"],
        paired_chat_id=cfg["paired_chat_id"],
        paired_chat_name=cfg["paired_chat_name"],
        paired_chat_type=cfg["paired_chat_type"],
        paired_at=cfg["paired_at"]
    )

@router.post("/config")
async def update_config(payload: WahaConfigRequest, db: AsyncSession = Depends(get_db)):
    """
    Update WAHA connection configuration and enablement toggle.
    """
    if payload.api_url is not None:
        await _set_val(db, "waha_api_url", payload.api_url.strip(), is_encrypted=False)
    if payload.api_key is not None:
        await _set_val(db, "waha_api_key", payload.api_key.strip(), is_encrypted=True)
    if payload.session_name is not None:
        await _set_val(db, "waha_session_name", payload.session_name.strip(), is_encrypted=False)
    if payload.enabled is not None:
        await _set_val(db, "waha_enabled", "true" if payload.enabled else "false", is_encrypted=False)

    await db.commit()
    return {"ok": True, "message": "Konfigurasi WhatsApp (WAHA) berhasil disimpan."}

@router.post("/session/start")
async def start_session_endpoint(db: AsyncSession = Depends(get_db)):
    """
    Start WAHA WhatsApp session to generate QR code.
    """
    cfg = await get_waha_settings(db)
    res = await start_waha_session(
        api_url=cfg["api_url"],
        session_name=cfg["session_name"],
        api_key=cfg["api_key"]
    )
    if not res.get("ok"):
        raise HTTPException(status_code=400, detail=res.get("error", "Gagal memulai sesi WAHA."))
    return {"ok": True, "message": "Sesi WAHA berhasil dimulai. Silakan scan QR code."}

@router.post("/session/logout")
async def logout_session_endpoint(db: AsyncSession = Depends(get_db)):
    """
    Logout or stop current WAHA session.
    """
    cfg = await get_waha_settings(db)
    res = await logout_waha_session(
        api_url=cfg["api_url"],
        session_name=cfg["session_name"],
        api_key=cfg["api_key"]
    )
    return {"ok": True, "message": "Sesi WAHA berhasil di-logout."}

@router.post("/token/regenerate")
async def regenerate_token_endpoint(db: AsyncSession = Depends(get_db)):
    """
    Regenerate new pairing token (e.g. embershorts-XXXXXX).
    """
    new_token = await regenerate_sync_token(db)
    return {"ok": True, "token": new_token, "message": "Token pairing baru berhasil dibuat."}

@router.post("/unpair")
async def unpair_endpoint(db: AsyncSession = Depends(get_db)):
    """
    Disconnect/unpair the current linked WhatsApp chat or group.
    """
    await _set_val(db, "waha_paired_chat_id", "", is_encrypted=False)
    await _set_val(db, "waha_paired_chat_name", "", is_encrypted=False)
    await _set_val(db, "waha_paired_chat_type", "", is_encrypted=False)
    await _set_val(db, "waha_paired_at", "", is_encrypted=False)
    await db.commit()
    return {"ok": True, "message": "Akun / Grup WhatsApp berhasil diputuskan dari EmberShorts."}

@router.post("/test-message")
async def send_test_message_endpoint(payload: WahaTestMessageRequest = None, db: AsyncSession = Depends(get_db)):
    """
    Send a test message to the currently paired chat.
    """
    cfg = await get_waha_settings(db)
    paired_chat_id = cfg["paired_chat_id"]
    if not paired_chat_id:
        raise HTTPException(
            status_code=400,
            detail="Belum ada nomor atau grup WhatsApp yang terhubung. Silakan lakukan pairing token terlebih dahulu."
        )

    msg_text = (payload.message if payload and payload.message else None) or "🤖 Pesan uji coba dari EmberShorts via WAHA berhasil diterima!"
    sent = await send_waha_message(db, paired_chat_id, msg_text)
    if not sent:
        raise HTTPException(status_code=500, detail="Gagal mengirim pesan ke WAHA. Periksa status koneksi WAHA.")
    return {"ok": True, "message": f"Pesan uji coba berhasil dikirim ke {cfg.get('paired_chat_name') or paired_chat_id}!"}
