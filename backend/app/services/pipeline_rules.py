import re
import json
import logging
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import (
    AppSetting,
    SourceVideo,
    ClipCandidate,
    RenderedShort,
    YouTubeExport,
)
from app.services.waha_service import send_waha_message, get_waha_settings

logger = logging.getLogger("pipeline_rules")

DEFAULT_PIPELINE_RULES: List[Dict[str, Any]] = [
    {
        "id": "rule_gaming",
        "name": "Gaming / Streamer Layout",
        "context": "gaming, streamer, gameplay, esports, wolverine",
        "preset_id": "preset_streamer_pip_circle"
    },
    {
        "id": "rule_podcast",
        "name": "Podcast & Talkshow Minimalist",
        "context": "podcast, talkshow, wawancara, interview, ngobrol",
        "preset_id": "preset_minimalist"
    },
    {
        "id": "rule_edukasi",
        "name": "Edukasi & Tutorial Center",
        "context": "edukasi, tutorial, teknologi, tech, coding, tips",
        "preset_id": "preset_tech_tutorial_center"
    },
    {
        "id": "rule_motivasi",
        "name": "Motivasi & Quotes Golden",
        "context": "motivasi, quotes, inspirasi, sukses, mindset",
        "preset_id": "preset_golden_lux"
    },
    {
        "id": "rule_horror",
        "name": "Horror & Misteri Documentary",
        "context": "horror, misteri, spooky, hantu, creepypasta",
        "preset_id": "preset_documentary"
    },
    {
        "id": "rule_komedi",
        "name": "Komedi & Meme Flash",
        "context": "komedi, lucu, meme, ngakak, humor",
        "preset_id": "preset_impact_meme"
    },
    {
        "id": "rule_bisnis",
        "name": "Bisnis & Keuangan Punch",
        "context": "bisnis, finance, keuangan, cuan, investasi",
        "preset_id": "preset_vocal_bebas"
    },
    {
        "id": "rule_storytelling",
        "name": "Storytelling & Fakta Cyberpunk",
        "context": "storytelling, cerita, fakta, sejarah, sains",
        "preset_id": "preset_cyberpunk"
    }
]


async def _get_val(db: AsyncSession, key: str, default: Optional[str] = None) -> Optional[str]:
    setting = await db.get(AppSetting, key)
    return setting.setting_value if setting and setting.setting_value is not None else default


async def _set_val(db: AsyncSession, key: str, val: str):
    setting = await db.get(AppSetting, key)
    if setting:
        setting.setting_value = val
    else:
        db.add(AppSetting(setting_key=key, setting_value=val, is_encrypted=False))


async def get_pipeline_config(db: AsyncSession) -> Dict[str, Any]:
    """
    Mengambil konfigurasi automated pipeline lengkap beserta status integrasi terkait.
    """
    auto_clip_str = await _get_val(db, "pipeline_auto_clip_enabled", "true")
    min_score_str = await _get_val(db, "pipeline_min_score", "70")
    rules_json = await _get_val(db, "pipeline_context_rules", None)
    default_preset_id = await _get_val(db, "pipeline_default_preset_id", "preset_tiktok_bold")

    auto_yt_str = await _get_val(db, "pipeline_auto_upload_youtube", "false")
    auto_gd_str = await _get_val(db, "pipeline_auto_upload_gdrive", "false")
    auto_wa_str = await _get_val(db, "pipeline_auto_notify_whatsapp", "true")
    wa_target_chat = await _get_val(db, "pipeline_whatsapp_target_chat", "")

    # Parsing rules
    if rules_json:
        try:
            context_rules = json.loads(rules_json)
        except Exception:
            context_rules = list(DEFAULT_PIPELINE_RULES)
    else:
        context_rules = list(DEFAULT_PIPELINE_RULES)

    try:
        min_score = float(min_score_str)
    except (TypeError, ValueError):
        min_score = 70.0

    # Cek koneksi layanan pihak ketiga
    yt_conn = await _get_val(db, "yt_upload_connected", "false")
    waha_cfg = await get_waha_settings(db)
    gd_auth = await _get_val(db, "gdrive_auth_type")
    gd_connected = bool(gd_auth)

    return {
        "auto_clip_enabled": auto_clip_str.lower() == "true",
        "min_score": int(min_score),
        "context_rules": context_rules,
        "default_preset_id": default_preset_id,
        "auto_upload_youtube": auto_yt_str.lower() == "true",
        "auto_upload_gdrive": auto_gd_str.lower() == "true",
        "auto_notify_whatsapp": auto_wa_str.lower() == "true",
        "whatsapp_target_chat": wa_target_chat or "",
        "whatsapp_paired": bool(waha_cfg.get("paired_chat_id")),
        "whatsapp_paired_chat_name": waha_cfg.get("paired_chat_name") or waha_cfg.get("paired_chat_id"),
        "youtube_connected": yt_conn == "true",
        "gdrive_connected": gd_connected,
    }


async def save_pipeline_config(db: AsyncSession, config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Menyimpan konfigurasi pipeline ke AppSetting.
    """
    if "auto_clip_enabled" in config:
        await _set_val(db, "pipeline_auto_clip_enabled", "true" if config["auto_clip_enabled"] else "false")

    if "min_score" in config:
        try:
            score = max(0, min(100, int(config["min_score"])))
            await _set_val(db, "pipeline_min_score", str(score))
        except (ValueError, TypeError):
            pass

    if "context_rules" in config:
        rules = config["context_rules"]
        if isinstance(rules, list):
            await _set_val(db, "pipeline_context_rules", json.dumps(rules, ensure_ascii=False))

    if "default_preset_id" in config:
        await _set_val(db, "pipeline_default_preset_id", str(config["default_preset_id"] or ""))

    if "auto_upload_youtube" in config:
        val = "true" if config["auto_upload_youtube"] else "false"
        await _set_val(db, "pipeline_auto_upload_youtube", val)
        # sinkronkan juga dengan setting youtube_auto_upload yang sudah ada
        await _set_val(db, "youtube_auto_upload", val)

    if "auto_upload_gdrive" in config:
        await _set_val(db, "pipeline_auto_upload_gdrive", "true" if config["auto_upload_gdrive"] else "false")

    if "auto_notify_whatsapp" in config:
        await _set_val(db, "pipeline_auto_notify_whatsapp", "true" if config["auto_notify_whatsapp"] else "false")

    if "whatsapp_target_chat" in config:
        await _set_val(db, "pipeline_whatsapp_target_chat", str(config["whatsapp_target_chat"] or "").strip())

    await db.commit()
    return await get_pipeline_config(db)


def match_pipeline_preset(
    video_type: Optional[str],
    video_title: Optional[str],
    video_desc: Optional[str],
    clip_title: Optional[str],
    rules: List[Dict[str, Any]],
    default_preset_id: Optional[str] = None,
    rec_preset_id: Optional[str] = None,
) -> Tuple[Optional[str], Optional[Dict[str, Any]], str]:
    """
    Mengevaluasi rules konteks secara berurutan terhadap metadata video.
    Return: (selected_preset_id, matched_rule, reason_explanation)
    """
    v_type = (video_type or "").strip().lower()
    v_title = (video_title or "").strip().lower()
    v_desc = (video_desc or "").strip().lower()
    c_title = (clip_title or "").strip().lower()

    combined_text = f"{v_type} {v_title} {c_title} {v_desc}".strip()

    for rule in rules:
        ctx_raw = str(rule.get("context") or "").strip().lower()
        if not ctx_raw:
            continue

        target_preset = rule.get("preset_id")
        rule_name = rule.get("name") or ctx_raw

        # Pecah context menjadi keyword individual jika dipisahkan tanda koma / garis miring / spasi
        keywords = [k.strip() for k in re.split(r"[,/|;]+", ctx_raw) if k.strip()]

        for kw in keywords:
            # 1. Kecocokan tepat atau substring dengan tipe video
            if v_type and (kw in v_type or v_type in kw):
                reason = f"Cocok dengan tipe video '{video_type}' via keyword '{kw}' (Rule: {rule_name})"
                return target_preset, rule, reason

            # 2. Kecocokan kata pada judul video
            if v_title and re.search(rf"\b{re.escape(kw)}\b", v_title):
                reason = f"Keyword '{kw}' ditemukan di judul video (Rule: {rule_name})"
                return target_preset, rule, reason

            # 3. Kecocokan kata pada judul klip
            if c_title and re.search(rf"\b{re.escape(kw)}\b", c_title):
                reason = f"Keyword '{kw}' ditemukan di judul klip (Rule: {rule_name})"
                return target_preset, rule, reason

            # 4. Fallback substring pada combined text
            if len(kw) >= 4 and kw in combined_text:
                reason = f"Keyword '{kw}' ditemukan di konteks video (Rule: {rule_name})"
                return target_preset, rule, reason

    # Bila tidak ada rule yang cocok:
    if default_preset_id and default_preset_id.strip():
        return default_preset_id.strip(), None, "Tidak ada rule cocok, menggunakan preset default pipeline"

    if rec_preset_id and rec_preset_id.strip():
        return rec_preset_id.strip(), None, "Tidak ada rule cocok, menggunakan preset rekomendasi AI"

    return None, None, "Tidak ada preset yang cocok"


async def check_and_send_consolidated_whatsapp_summary(video_id: str, db: AsyncSession) -> bool:
    """
    Memeriksa apakah seluruh Shorts untuk SourceVideo ini telah selesai di-upload ke YouTube.
    Bila ya dan belum pernah dinotifikasi, kirim 1 chat WhatsApp konsolidasi berisi
    seluruh link YouTube Shorts untuk video tersebut.
    """
    video = await db.get(SourceVideo, video_id)
    if not video:
        return False

    # 1. Cek apakah notifikasi WhatsApp pipeline diaktifkan
    wa_enabled_str = await _get_val(db, "pipeline_auto_notify_whatsapp", "true")
    if wa_enabled_str.lower() != "true":
        logger.debug("Auto notify WhatsApp dinonaktifkan di pipeline config.")
        return False

    # 2. Tentukan target chat WhatsApp
    custom_target = await _get_val(db, "pipeline_whatsapp_target_chat", "")
    waha_cfg = await get_waha_settings(db)
    target_chat = custom_target.strip() if custom_target and custom_target.strip() else waha_cfg.get("paired_chat_id")
    if not target_chat:
        logger.info("Chat WhatsApp tujuan belum dipasangkan/dikonfigurasi untuk video %s", video_id)
        return False

    # 3. Dapatkan seluruh clips untuk video ini
    clips_res = await db.execute(select(ClipCandidate).where(ClipCandidate.video_id == video_id))
    clips = clips_res.scalars().all()
    if not clips:
        return False
    clip_map = {c.id: c for c in clips}

    # 4. Dapatkan seluruh rendered shorts
    shorts_res = await db.execute(select(RenderedShort).where(RenderedShort.clip_id.in_(list(clip_map.keys()))))
    shorts = shorts_res.scalars().all()
    if not shorts:
        return False

    # 5. Cek apakah masih ada short yang sedang dirender
    pending_renders = [s for s in shorts if s.render_status in ("PENDING", "RENDERING", "PROCESSING")]
    if pending_renders:
        logger.info("Masih ada %d short yang sedang dirender untuk video %s, menunda notifikasi WA.", len(pending_renders), video_id)
        return False

    # 6. Dapatkan seluruh YouTubeExport records untuk shorts ini
    short_ids = [s.id for s in shorts]
    exports_res = await db.execute(select(YouTubeExport).where(YouTubeExport.short_id.in_(short_ids)))
    exports = exports_res.scalars().all()

    # Cek apakah masih ada YouTube export yang sedang dalam proses
    pending_uploads = [exp for exp in exports if exp.upload_status in ("QUEUED", "UPLOADING")]
    if pending_uploads:
        logger.info("Masih ada %d upload YouTube yang sedang berjalan untuk video %s, menunda notifikasi WA.", len(pending_uploads), video_id)
        return False

    # 7. Ambil upload yang sukses dengan link/ID video YouTube
    success_uploads = [
        exp for exp in exports
        if exp.upload_status == "SUCCESS" and (exp.youtube_video_id or exp.youtube_url)
    ]
    if not success_uploads:
        logger.debug("Belum ada upload YouTube yang sukses untuk video %s", video_id)
        return False

    # 8. Idempotensi: periksa apakah batch ini sudah pernah dikirimkan
    current_export_ids = sorted([exp.id for exp in success_uploads])
    current_hash = ",".join(current_export_ids)
    notified_key = f"pipeline_wa_notified_{video_id}"
    previously_notified = await _get_val(db, notified_key)
    if previously_notified == current_hash:
        logger.debug("Notifikasi konsolidasi WhatsApp untuk video %s batch ini sudah pernah dikirim.", video_id)
        return False

    # 9. Format pesan ringkasan konsolidasi (1 chat WhatsApp untuk seluruh video)
    v_name = video.original_name or "Video"
    lines = [
        "🎉 *Pipeline Selesai: Upload YouTube Berhasil!*",
        f"📹 Video: *{v_name}*",
        "",
        f"Semua klip Shorts untuk video ini telah berhasil diproses dan di-upload ke YouTube ({len(success_uploads)} klip):",
        ""
    ]

    for idx, exp in enumerate(success_uploads, 1):
        sh = next((s for s in shorts if s.id == exp.short_id), None)
        c = clip_map.get(sh.clip_id) if sh else None
        clip_title = exp.title or (c.title if c else f"Short #{idx}")

        yt_id = exp.youtube_video_id
        if yt_id:
            yt_url = f"https://youtube.com/shorts/{yt_id}"
        elif exp.youtube_url:
            yt_url = exp.youtube_url
        else:
            yt_url = "-"

        lines.append(f"{idx}. 🎬 *{clip_title}*")
        lines.append(f"   🔗 {yt_url}")
        lines.append("")

    lines.append(f"📊 *Total:* {len(success_uploads)} Shorts Berhasil Di-upload")
    lines.append("✨ Kunjungi YouTube Studio untuk melihat performa & analitik.")

    message_text = "\n".join(lines)

    # 10. Kirim pesan via WAHA
    try:
        sent = await send_waha_message(db, target_chat, message_text)
        if sent:
            await _set_val(db, notified_key, current_hash)
            await db.commit()
            logger.info("Berhasil mengirim chat konsolidasi WhatsApp untuk video %s ke chat %s", video_id, target_chat)
            return True
        else:
            logger.warning("Gagal mengirim chat WhatsApp ke %s untuk video %s", target_chat, video_id)
            return False
    except Exception as exc:
        logger.error("Error mengirim notifikasi WhatsApp konsolidasi: %s", exc)
        return False
