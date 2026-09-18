import os
import re
import json
import uuid
import secrets
import logging
import httpx
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from sqlalchemy import select, desc, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import AppSetting, SourceVideo, ClipCandidate, RenderedShort, AppJob
from app.services.youtube_service import get_youtube_info
from app.core.crypto import encrypt_setting, decrypt_setting

logger = logging.getLogger("waha")

DEFAULT_WAHA_URL = "http://localhost:3008"
DEFAULT_SESSION_NAME = "default"

async def _get_val(db: AsyncSession, key: str) -> Optional[str]:
    setting = await db.get(AppSetting, key)
    return setting.setting_value if setting else None

async def _set_val(db: AsyncSession, key: str, value: str, is_encrypted: bool = False):
    setting = await db.get(AppSetting, key)
    stored_val = encrypt_setting(value) if (is_encrypted and value) else value
    if setting:
        setting.setting_value = stored_val
        setting.is_encrypted = is_encrypted
    else:
        db.add(AppSetting(setting_key=key, setting_value=stored_val, is_encrypted=is_encrypted))

async def get_or_create_sync_token(db: AsyncSession) -> str:
    token = await _get_val(db, "waha_sync_token")
    if not token or not token.strip():
        # Generate 6-digit pin for embershorts-XXXXXX
        digits = secrets.randbelow(900000) + 100000
        token = f"embershorts-{digits}"
        await _set_val(db, "waha_sync_token", token, is_encrypted=False)
        await db.commit()
    return token

async def regenerate_sync_token(db: AsyncSession) -> str:
    digits = secrets.randbelow(900000) + 100000
    token = f"embershorts-{digits}"
    await _set_val(db, "waha_sync_token", token, is_encrypted=False)
    await db.commit()
    return token

async def get_waha_settings(db: AsyncSession) -> Dict[str, Any]:
    enabled_str = await _get_val(db, "waha_enabled")
    api_url = (await _get_val(db, "waha_api_url")) or os.environ.get("WAHA_BASE_URL", DEFAULT_WAHA_URL)
    api_key_rec = await db.get(AppSetting, "waha_api_key")
    api_key = ""
    if api_key_rec and api_key_rec.setting_value:
        try:
            api_key = decrypt_setting(api_key_rec.setting_value) if api_key_rec.is_encrypted else api_key_rec.setting_value
        except Exception:
            api_key = api_key_rec.setting_value

    if not api_key:
        api_key = os.environ.get("WAHA_API_KEY", "embershorts_waha_secret_key")

    session_name = (await _get_val(db, "waha_session_name")) or DEFAULT_SESSION_NAME
    sync_token = await get_or_create_sync_token(db)
    paired_chat_id = await _get_val(db, "waha_paired_chat_id")
    paired_chat_name = await _get_val(db, "waha_paired_chat_name")
    paired_chat_type = await _get_val(db, "waha_paired_chat_type")
    paired_at = await _get_val(db, "waha_paired_at")

    return {
        "enabled": enabled_str == "true",
        "api_url": api_url,
        "api_key": api_key,
        "session_name": session_name,
        "sync_token": sync_token,
        "paired_chat_id": paired_chat_id,
        "paired_chat_name": paired_chat_name,
        "paired_chat_type": paired_chat_type,
        "paired_at": paired_at,
    }

def get_candidate_urls(api_url: str) -> List[str]:
    """Generate candidate URLs to try for WAHA in case backend is inside Docker or on host."""
    clean = (api_url or "").strip().rstrip("/")
    candidates = []
    if clean:
        candidates.append(clean)
    for alt in ["http://waha:3000", "http://autoshorts-waha:3000", "http://localhost:3008", "http://127.0.0.1:3008", "http://host.docker.internal:3008", "http://localhost:3000"]:
        if alt not in candidates:
            candidates.append(alt)
    return candidates

async def probe_waha_session_status(api_url: str, session_name: str, api_key: Optional[str] = None) -> Dict[str, Any]:
    """
    Connect to WAHA REST API to check session status and retrieve QR code if awaiting scan.
    """
    headers = {}
    if api_key:
        headers["X-Api-Key"] = api_key

    status_result = {
        "session_status": "STOPPED",
        "qr_code": None
    }

    candidates = get_candidate_urls(api_url)

    async with httpx.AsyncClient(timeout=4.0) as client:
        for base_url in candidates:
            try:
                # 1. Check single session or session list
                resp = await client.get(f"{base_url}/api/sessions/{session_name}", headers=headers)
                data = None
                if resp.status_code == 200:
                    data = resp.json()
                elif resp.status_code == 404:
                    # Try GET /api/sessions (list)
                    list_resp = await client.get(f"{base_url}/api/sessions", headers=headers)
                    if list_resp.status_code == 200:
                        sess_list = list_resp.json()
                        if isinstance(sess_list, list):
                            for s in sess_list:
                                if s.get("name") == session_name:
                                    data = s
                                    break

                if data:
                    raw_status = (data.get("status") or "STOPPED").upper()
                    engine_state = (data.get("engine") or {}).get("state", "").upper()

                    if raw_status == "FAILED":
                        status_result["session_status"] = "FAILED"
                    elif raw_status == "WORKING" or engine_state in ["CONNECTED", "PAIRING"]:
                        status_result["session_status"] = "WORKING"
                    elif raw_status == "STARTING" and engine_state == "UNPAIRED":
                        status_result["session_status"] = "SCAN_QR_CODE"
                    elif raw_status in ["SCAN_QR_CODE", "SCAN_QR", "UNPAIRED"]:
                        status_result["session_status"] = "SCAN_QR_CODE"
                    else:
                        status_result["session_status"] = raw_status

                    # 2. If session needs QR scan, fetch QR image/data
                    if status_result["session_status"] in ["SCAN_QR_CODE", "STARTING", "SCAN_QR", "UNPAIRED"]:
                        for qr_path in [
                            f"/api/{session_name}/auth/qr",
                            f"/api/sessions/{session_name}/auth/qr",
                            f"/api/screenshot?session={session_name}",
                            "/api/screenshot"
                        ]:
                            try:
                                qr_resp = await client.get(f"{base_url}{qr_path}", headers=headers)
                                if qr_resp.status_code == 200:
                                    content_type = qr_resp.headers.get("content-type", "")
                                    if "image" in content_type:
                                        import base64
                                        b64 = base64.b64encode(qr_resp.content).decode("utf-8")
                                        status_result["qr_code"] = f"data:{content_type};base64,{b64}"
                                        break
                                    else:
                                        try:
                                            qr_json = qr_resp.json()
                                            status_result["qr_code"] = qr_json.get("qr") or qr_json.get("raw")
                                            if status_result["qr_code"]:
                                                break
                                        except Exception:
                                            status_result["qr_code"] = qr_resp.text
                                            if status_result["qr_code"]:
                                                break
                            except Exception:
                                continue
                    return status_result
            except Exception as e:
                logger.debug(f"WAHA probe error on {base_url}: {e}")
                continue

    return status_result

async def start_waha_session(api_url: str, session_name: str, api_key: Optional[str] = None) -> Dict[str, Any]:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["X-Api-Key"] = api_key

    payload = {"name": session_name}
    candidates = get_candidate_urls(api_url)

    async with httpx.AsyncClient(timeout=10.0) as client:
        for base_url in candidates:
            try:
                # 1. Check current session status
                check_resp = await client.get(f"{base_url}/api/sessions/{session_name}", headers=headers)
                if check_resp.status_code == 200:
                    st = check_resp.json().get("status", "").upper()
                    if st in ["WORKING", "SCAN_QR_CODE", "STARTING", "SCAN_QR"]:
                        return {"ok": True, "data": check_resp.json()}
                    elif st in ["FAILED", "STOPPED"]:
                        # Try restart first
                        restart_resp = await client.post(f"{base_url}/api/sessions/{session_name}/restart", headers=headers)
                        if restart_resp.status_code in [200, 201]:
                            return {"ok": True, "data": restart_resp.json()}
                        # Fallback to start
                        start_named = await client.post(f"{base_url}/api/sessions/{session_name}/start", headers=headers)
                        if start_named.status_code in [200, 201]:
                            return {"ok": True, "data": start_named.json()}

                # 2. If session doesn't exist, create it
                resp = await client.post(f"{base_url}/api/sessions", headers=headers, json=payload)
                if resp.status_code in [200, 201]:
                    # Then trigger start
                    await client.post(f"{base_url}/api/sessions/{session_name}/start", headers=headers)
                    return {"ok": True, "data": resp.json()}

                # 3. Try restart or start named directly
                restart_resp = await client.post(f"{base_url}/api/sessions/{session_name}/restart", headers=headers)
                if restart_resp.status_code in [200, 201]:
                    return {"ok": True, "data": restart_resp.json()}

                resp_named = await client.post(f"{base_url}/api/sessions/{session_name}/start", headers=headers)
                if resp_named.status_code in [200, 201]:
                    return {"ok": True, "data": resp_named.json()}

                # 4. Try POST /api/sessions/start
                resp_start = await client.post(f"{base_url}/api/sessions/start", headers=headers, json=payload)
                if resp_start.status_code in [200, 201]:
                    return {"ok": True, "data": resp_start.json()}

                # Check if error is just "already exists" / "already started"
                err_text = ((resp.text if 'resp' in locals() else "") or (resp_start.text if 'resp_start' in locals() else "")).lower()
                if "already" in err_text or "exist" in err_text or "running" in err_text:
                    return {"ok": True, "data": {"status": "STARTING"}}
            except Exception as e:
                logger.debug(f"WAHA start error on {base_url}: {e}")
                continue

        return {"ok": False, "error": "Tidak dapat terhubung ke WAHA server. Pastikan container WAHA sudah berjalan (docker compose up -d)."}

async def logout_waha_session(api_url: str, session_name: str, api_key: Optional[str] = None) -> Dict[str, Any]:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["X-Api-Key"] = api_key

    payload = {"name": session_name}
    candidates = get_candidate_urls(api_url)

    async with httpx.AsyncClient(timeout=8.0) as client:
        for base_url in candidates:
            try:
                resp = await client.post(f"{base_url}/api/sessions/logout", headers=headers, json=payload)
                if resp.status_code in [200, 201]:
                    return {"ok": True}

                resp_named = await client.post(f"{base_url}/api/sessions/{session_name}/logout", headers=headers)
                if resp_named.status_code in [200, 201]:
                    return {"ok": True}

                # Fallback stop
                stop_resp = await client.post(f"{base_url}/api/sessions/stop", headers=headers, json=payload)
                if stop_resp.status_code in [200, 201]:
                    return {"ok": True}
            except Exception:
                continue

    return {"ok": True}

async def send_waha_message(db: AsyncSession, chat_id: str, text: str) -> bool:
    cfg = await get_waha_settings(db)
    api_url = cfg["api_url"].rstrip("/")
    api_key = cfg["api_key"]
    session_name = cfg["session_name"]

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["X-Api-Key"] = api_key

    payload = {
        "session": session_name,
        "chatId": chat_id,
        "text": text
    }

    candidates = get_candidate_urls(api_url)

    async with httpx.AsyncClient(timeout=10.0) as client:
        for base_url in candidates:
            try:
                resp = await client.post(f"{base_url}/api/sendText", headers=headers, json=payload)
                if resp.status_code in [200, 201]:
                    return True
                # Try fallback /api/send/text
                resp2 = await client.post(f"{base_url}/api/send/text", headers=headers, json=payload)
                if resp2.status_code in [200, 201]:
                    return True
            except Exception as e:
                logger.debug(f"WAHA sendText error on {base_url}: {e}")
                continue

    return False

def format_duration(seconds: float) -> str:
    secs = int(seconds)
    mins = secs // 60
    rem_sec = secs % 60
    if mins > 0:
        return f"{mins}m {rem_sec}s"
    return f"{rem_sec}s"

async def enqueue_youtube_video(db: AsyncSession, url: str, auto_generate: bool) -> SourceVideo:
    """Helper to register and enqueue YouTube video background download."""
    setting = await db.get(AppSetting, "yt_quality")
    quality = setting.setting_value if setting and setting.setting_value else "1080p"

    video_id = uuid.uuid4().hex
    saved_filename = f"{video_id}.mp4"
    rel_path = f"uploads/{saved_filename}"

    try:
        info = await get_youtube_info(url)
    except Exception:
        info = {"title": "YouTube Video", "duration_seconds": 0.0, "description": ""}

    title = info.get("title") or "YouTube Video"
    clean_title = re.sub(r'[\\/*?:"<>|]', "", title).strip() or "youtube_video"
    original_name = f"{clean_title}.mp4"
    duration = float(info.get("duration_seconds") or 0.0)

    video_record = SourceVideo(
        id=video_id,
        filename=saved_filename,
        original_name=original_name,
        local_file_path=rel_path,
        file_size_bytes=0,
        duration_seconds=duration,
        status="DOWNLOADING",
        description=info.get("description") or None,
        auto_generate_shorts=auto_generate
    )
    db.add(video_record)

    job = AppJob(
        id=uuid.uuid4().hex,
        job_type="YOUTUBE_DOWNLOAD",
        ref_id=video_id,
        status="QUEUED",
        payload={
            "url": url,
            "quality": quality,
            "auto_generate": auto_generate
        }
    )
    db.add(job)
    await db.commit()
    return video_record

_PROCESSED_MESSAGE_CACHE: Dict[str, float] = {}

def _is_duplicate_message(msg_id: str, from_jid: str, text: str) -> bool:
    import time
    now = time.time()
    # Expire entries older than 180 seconds
    stale_keys = [k for k, ts in _PROCESSED_MESSAGE_CACHE.items() if now - ts > 180.0]
    for k in stale_keys:
        _PROCESSED_MESSAGE_CACHE.pop(k, None)

    key = f"{msg_id}:{from_jid}:{text}" if msg_id else f"{from_jid}:{text}"
    if key in _PROCESSED_MESSAGE_CACHE:
        return True

    _PROCESSED_MESSAGE_CACHE[key] = now
    return False

async def process_incoming_waha_message(db: AsyncSession, webhook_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process incoming message event from WAHA webhook.
    Handles token pairing and commands (help, process, process all, status).
    """
    # If explicit event is passed, only accept "message" or "message.create" event (ignore "message.any", "message.ack", "session.status", etc.)
    event_type = webhook_data.get("event")
    if event_type and event_type not in ["message", "message.create"]:
        return {"ok": True, "detail": f"Ignored event type: {event_type}"}

    # WAHA can send {"event": "message", "session": "...", "payload": {...}} or direct object
    payload = webhook_data.get("payload", webhook_data)
    if not isinstance(payload, dict):
        return {"ok": False, "detail": "Invalid payload format"}

    # Ignore messages sent by the bot itself
    from_me = payload.get("fromMe", False)
    if from_me:
        return {"ok": True, "detail": "Ignored message from self"}

    # Extract sender chatId and body
    from_jid = payload.get("from") or payload.get("chatId") or payload.get("fromJid") or ""
    if not from_jid:
        return {"ok": False, "detail": "Missing from chatId"}

    body = payload.get("body") or payload.get("text") or ""
    push_name = payload.get("_data", {}).get("notifyName") or payload.get("pushName") or ""
    mentioned_ids = payload.get("mentionedIds") or []

    clean_text = body.strip()
    if not clean_text:
        return {"ok": True, "detail": "Empty message body"}

    # Deduplicate repeated deliveries of the same message (e.g. webhook retries or parallel event triggers)
    raw_id = payload.get("id")
    msg_id = ""
    if isinstance(raw_id, str):
        msg_id = raw_id
    elif isinstance(raw_id, dict):
        msg_id = raw_id.get("_serialized") or raw_id.get("id") or ""

    if _is_duplicate_message(msg_id, from_jid, clean_text):
        logger.info(f"Duplicate WhatsApp message ignored: id={msg_id} chat={from_jid}")
        return {"ok": True, "detail": "Duplicate message ignored"}

    cfg = await get_waha_settings(db)
    current_token = cfg["sync_token"]
    paired_chat_id = cfg["paired_chat_id"]
    is_group = from_jid.endswith("@g.us")

    # 1. Check for pairing command: `connect embershorts-XXXXXX`
    pair_match = re.match(r"^connect\s+(embershorts-[\w\-]+)", clean_text, re.IGNORECASE)
    if pair_match:
        sent_token = pair_match.group(1).strip()
        if sent_token.lower() == current_token.lower():
            # Successfully pair this chat
            chat_type = "group" if is_group else "direct"
            display_name = push_name or ("Grup WhatsApp" if is_group else f"Kontak ({from_jid})")
            now_iso = datetime.now(timezone.utc).isoformat()

            await _set_val(db, "waha_paired_chat_id", from_jid, is_encrypted=False)
            await _set_val(db, "waha_paired_chat_type", chat_type, is_encrypted=False)
            await _set_val(db, "waha_paired_chat_name", display_name, is_encrypted=False)
            await _set_val(db, "waha_paired_at", now_iso, is_encrypted=False)
            await _set_val(db, "waha_enabled", "true", is_encrypted=False)
            await db.commit()

            reply_msg = (
                "✅ *EmberShorts Berhasil Terhubung!*\n\n"
                f"Halo! Obrolan ini telah berhasil ditautkan sebagai kontrol resmi EmberShorts ({'Grup' if is_group else 'Kontak'}).\n\n"
                "📌 *Panduan Perintah:*\n"
                "• `#help` : Menampilkan daftar bantuan perintah.\n"
                "• `#process <link_youtube>` : Download + Transcribe + AI Klip Studio (tanpa auto-render).\n"
                "• `#process all <link_youtube>` : Download + Transcribe + AI Klip + Auto Render Shorts (9:16) dengan preset genre otomatis.\n"
                "• `#status` : Cek status 10 video antrean terakhir.\n\n"
                "💡 *Tips:* Di dalam grup, Anda dapat menggunakan awalan `#shorts` (misal: `#shorts process <link>` atau `#shorts process all <link>`)."
            )
            await send_waha_message(db, from_jid, reply_msg)
            return {"ok": True, "action": "paired", "chat_id": from_jid}
        else:
            fail_msg = (
                "❌ *Token Pairing Tidak Valid.*\n\n"
                "Token yang Anda kirimkan tidak sesuai. Silakan periksa kembali token pairing pada menu Settings aplikasi EmberShorts."
            )
            await send_waha_message(db, from_jid, fail_msg)
            return {"ok": True, "action": "pair_failed"}

    # 2. Verify sender is the paired chat
    if not paired_chat_id or from_jid != paired_chat_id:
        # Ignore messages from un-paired chats
        return {"ok": True, "detail": "Ignored non-paired sender"}

    # 3. For group chat, check if bot is addressed
    if is_group:
        # Check if the message starts with or contains bot tag / hashtag / prefix
        is_bot_targeted = (
            clean_text.startswith("#") or
            clean_text.startswith("/") or
            clean_text.startswith("!") or
            re.search(r"@\w+", clean_text) is not None or
            re.search(r"#shorts\b", clean_text, re.IGNORECASE) is not None or
            re.search(r"#tag\b", clean_text, re.IGNORECASE) is not None or
            len(mentioned_ids) > 0
        )
        if not is_bot_targeted:
            return {"ok": True, "detail": "Group message not directed to bot"}

    # Clean command string (strip mentions, #shorts, #tag, #, /, !)
    clean_cmd = re.sub(r"^(?:@\w+\s+|#shorts\s+|#tag\s+|[#!\/])", "", clean_text, flags=re.IGNORECASE).strip()

    # 4. Command Dispatching
    cmd_lower = clean_cmd.lower()

    # Command: HELP
    if cmd_lower.startswith("help") or cmd_lower.startswith("bantuan") or cmd_lower == "menu":
        help_msg = (
            "🤖 *EmberShorts AI Bot Assistant*\n\n"
            "Daftar perintah yang dapat Anda gunakan:\n\n"
            "✂️ *`#process <link_youtube>`* atau *`#shorts process <link_youtube>`*\n"
            "Memproses video menjadi kandidat klip AI di Clip Studio (tanpa auto-render).\n\n"
            "🎬 *`#process all <link_youtube>`* atau *`#shorts process all <link_youtube>`*\n"
            "Memproses video & langsung merender semua klip menjadi Shorts (9:16) vertikal dengan preset otomatis berdasarkan tipe konten (Horror, Motivasi, Edukasi, Gaming, Podcast, dll).\n\n"
            "📊 *`#status`* atau *`#shorts status`*\n"
            "Melihat status dan progres dari 10 video terakhir di antrean sistem.\n\n"
            "💡 *Tips:* Untuk grup, Anda dapat mengetik `#shorts <perintah>` (misal: `#shorts process all <link>`) atau tag bot secara langsung."
        )
        await send_waha_message(db, from_jid, help_msg)
        return {"ok": True, "command": "help"}

    # Command: PROCESS ALL (Auto-render all shorts)
    if cmd_lower.startswith("process all") or cmd_lower.startswith("proses all") or cmd_lower.startswith("render all"):
        url_match = re.search(r"https?://\S+", clean_cmd)
        if not url_match:
            err_msg = "⚠️ *Format Perintah Salah.*\nGunakan format: `#process all <link_youtube>`"
            await send_waha_message(db, from_jid, err_msg)
            return {"ok": True, "error": "missing_url"}

        yt_url = url_match.group(0)
        try:
            video_rec = await enqueue_youtube_video(db, yt_url, auto_generate=True)
            ack_msg = (
                "🎬 *Memulai Pemrosesan Video (Full Auto Shorts)*\n\n"
                f"📹 *Judul:* {video_rec.original_name}\n"
                f"⏱️ *Durasi:* {format_duration(video_rec.duration_seconds)}\n"
                "⚡ *Pipeline:* Download ➔ Transcribe ➔ Analisis AI ➔ Auto Render Shorts (9:16)\n\n"
                "Video telah dimasukkan ke antrean background worker. Ketik `#status` untuk memantau progres!"
            )
            await send_waha_message(db, from_jid, ack_msg)
            return {"ok": True, "command": "process_all", "video_id": video_rec.id}
        except Exception as e:
            logger.error(f"Error initiating process all: {e}")
            await send_waha_message(db, from_jid, f"❌ *Gagal memproses video:* {str(e)[:200]}")
            return {"ok": False, "error": str(e)}

    # Command: PROCESS (Candidate Clip Studio mode)
    if cmd_lower.startswith("process") or cmd_lower.startswith("proses") or cmd_lower.startswith("clip"):
        url_match = re.search(r"https?://\S+", clean_cmd)
        if not url_match:
            err_msg = "⚠️ *Format Perintah Salah.*\nGunakan format: `#process <link_youtube>`"
            await send_waha_message(db, from_jid, err_msg)
            return {"ok": True, "error": "missing_url"}

        yt_url = url_match.group(0)
        try:
            video_rec = await enqueue_youtube_video(db, yt_url, auto_generate=False)
            ack_msg = (
                "✂️ *Memulai Pemrosesan Video (Clip Studio Mode)*\n\n"
                f"📹 *Judul:* {video_rec.original_name}\n"
                f"⏱️ *Durasi:* {format_duration(video_rec.duration_seconds)}\n"
                "⚡ *Pipeline:* Download ➔ Transcribe ➔ Analisis AI Highlight (Kandidat Klip)\n\n"
                "Setelah analisis selesai, klip kandidat akan siap di Clip Studio web. Ketik `#status` untuk memantau progres!"
            )
            await send_waha_message(db, from_jid, ack_msg)
            return {"ok": True, "command": "process", "video_id": video_rec.id}
        except Exception as e:
            logger.error(f"Error initiating process: {e}")
            await send_waha_message(db, from_jid, f"❌ *Gagal memproses video:* {str(e)[:200]}")
            return {"ok": False, "error": str(e)}

    # Command: STATUS
    if cmd_lower.startswith("status") or cmd_lower.startswith("antrean") or cmd_lower.startswith("queue"):
        # Query top 10 latest videos
        stmt = select(SourceVideo).order_by(desc(SourceVideo.created_at)).limit(10)
        videos = (await db.execute(stmt)).scalars().all()

        if not videos:
            await send_waha_message(db, from_jid, "📊 *Status Antrean:* Belum ada video yang diproses di sistem.")
            return {"ok": True, "command": "status", "count": 0}

        status_icons = {
            "DOWNLOADING": "⏳ Download",
            "UPLOADED": "📦 Uploaded",
            "EXTRACTING_AUDIO": "🎵 Ekstrak Audio",
            "TRANSCRIBING": "✍️ Transcribing",
            "ANALYZING": "🤖 AI Analisis",
            "READY": "✅ Siap",
            "FAILED": "❌ Gagal"
        }

        lines = ["📊 *Status 10 Video Terakhir EmberShorts:*\n"]
        for idx, v in enumerate(videos, start=1):
            st_text = status_icons.get(v.status, v.status)
            dur_str = format_duration(v.duration_seconds)

            # Count clips & rendered shorts
            clips_count = await db.scalar(
                select(func.count(ClipCandidate.id)).where(ClipCandidate.video_id == v.id)
            ) or 0
            shorts_count = await db.scalar(
                select(func.count(RenderedShort.id))
                .join(ClipCandidate, RenderedShort.clip_id == ClipCandidate.id)
                .where(ClipCandidate.video_id == v.id, RenderedShort.render_status == "COMPLETED")
            ) or 0

            type_tag = f" • Tipe: _{v.video_type}_" if getattr(v, "video_type", None) else ""
            stats_str = f" ({clips_count} klip, {shorts_count} shorts)" if clips_count > 0 else ""

            # Truncate title if long
            title = v.original_name
            if len(title) > 35:
                title = title[:32] + "..."

            lines.append(f"{idx}. *{title}*\n   • Status: {st_text}{stats_str}{type_tag}\n   • Durasi: {dur_str}")

        lines.append("\n_Kirim `#help` untuk bantuan perintah lainnya._")
        status_msg = "\n".join(lines)
        await send_waha_message(db, from_jid, status_msg)
        return {"ok": True, "command": "status", "count": len(videos)}

    # Fallback for unrecognized command with bot prefix
    if clean_text.startswith("#") or is_group:
        fallback_msg = (
            "❓ *Perintah Tidak Dikenali.*\n\n"
            "Kirim *`#help`* untuk melihat daftar perintah yang didukung oleh EmberShorts bot."
        )
        await send_waha_message(db, from_jid, fallback_msg)

    return {"ok": True, "detail": "Unrecognized command"}
