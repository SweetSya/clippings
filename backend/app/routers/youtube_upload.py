import os
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import HTMLResponse
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import RenderedShort, YouTubeExport, AppJob, AppSetting, ClipCandidate, SourceVideo
from app.schemas import (
    BatchDeleteRequest,
    BatchActionResponse,
    YouTubeSettingsRequest,
    YouTubeConfigResponse,
    YouTubeOAuthUrlResponse,
    YouTubeOAuthExchangeRequest,
    YouTubeChannelInfo,
    YouTubeUploadRequest,
    YouTubeExportResponse,
    YouTubeUploadStatusResponse,
)
from app.core.security import get_current_session
from app.core.crypto import decrypt_setting
from app.services.storage_service import resolve_path
from app.routers.settings import _get_val, _set_val
from app.services.youtube_upload_service import (
    generate_youtube_oauth_url,
    exchange_youtube_code,
    test_youtube_access,
    YOUTUBE_REDIRECT_URI,
)

router = APIRouter(tags=["YouTube Upload"])
public_router = APIRouter(tags=["YouTube Upload"])


def _redirect_uri(payload_uri: Optional[str] = None) -> str:
    return (payload_uri or "").strip() or YOUTUBE_REDIRECT_URI


@router.post("/youtube/config", dependencies=[Depends(get_current_session)])
async def save_youtube_config(payload: YouTubeSettingsRequest, db: AsyncSession = Depends(get_db)):
    if payload.client_id is not None:
        await _set_val(db, "yt_upload_client_id", payload.client_id.strip(), is_encrypted=False)
    if payload.client_secret is not None:
        await _set_val(db, "yt_upload_client_secret", payload.client_secret.strip(), is_encrypted=True)
    if payload.auto_upload is not None:
        await _set_val(db, "youtube_auto_upload", "true" if payload.auto_upload else "false", is_encrypted=False)
    if payload.default_privacy is not None:
        await _set_val(db, "youtube_default_privacy", payload.default_privacy.strip().lower(), is_encrypted=False)
    if payload.default_category is not None:
        await _set_val(db, "youtube_default_category", payload.default_category.strip(), is_encrypted=False)
    if payload.made_for_kids is not None:
        await _set_val(db, "youtube_default_made_for_kids", "true" if payload.made_for_kids else "false", is_encrypted=False)
    await db.commit()
    return {"status": "saved", "message": "Konfigurasi YouTube berhasil disimpan."}


@router.get("/youtube/config", response_model=YouTubeConfigResponse, dependencies=[Depends(get_current_session)])
async def get_youtube_config(db: AsyncSession = Depends(get_db)):
    client_id = await _get_val(db, "yt_upload_client_id")
    auto_upload = (await _get_val(db, "youtube_auto_upload")) == "true"
    default_privacy = (await _get_val(db, "youtube_default_privacy")) or "public"
    default_category = (await _get_val(db, "youtube_default_category")) or "22"
    made_for_kids = (await _get_val(db, "youtube_default_made_for_kids")) == "true"
    connected = (await _get_val(db, "yt_upload_connected")) == "true"
    channel_name = await _get_val(db, "yt_upload_channel_name")
    channel_id = await _get_val(db, "yt_upload_channel_id")
    return YouTubeConfigResponse(
        client_id=client_id,
        auto_upload=auto_upload,
        default_privacy=default_privacy,
        default_category=default_category,
        made_for_kids=made_for_kids,
        connected=connected,
        channel_name=channel_name,
        channel_id=channel_id,
    )


@router.post("/youtube/auth-url", response_model=YouTubeOAuthUrlResponse,
             dependencies=[Depends(get_current_session)])
async def get_youtube_auth_url(redirect_uri: str = YOUTUBE_REDIRECT_URI, db: AsyncSession = Depends(get_db)):
    client_id = await _get_val(db, "yt_upload_client_id")
    if not client_id:
        raise HTTPException(status_code=400, detail="Client ID YouTube belum dikonfigurasi.")
    return YouTubeOAuthUrlResponse(
        auth_url=generate_youtube_oauth_url(client_id, redirect_uri),
        redirect_uri=redirect_uri,
    )


@router.post("/youtube/exchange", dependencies=[Depends(get_current_session)])
async def exchange_youtube_code_route(payload: YouTubeOAuthExchangeRequest, db: AsyncSession = Depends(get_db)):
    client_id = await _get_val(db, "yt_upload_client_id")
    csec_rec = await db.get(AppSetting, "yt_upload_client_secret")
    if not client_id or not csec_rec:
        raise HTTPException(status_code=400, detail="Client ID atau Secret YouTube belum dikonfigurasi.")
    client_secret = decrypt_setting(csec_rec.setting_value) if csec_rec.is_encrypted else csec_rec.setting_value
    try:
        tokens = await exchange_youtube_code(
            client_id=client_id, client_secret=client_secret,
            code=payload.code.strip(), redirect_uri=_redirect_uri(payload.redirect_uri),
        )
        refresh_token = tokens.get("refresh_token")
        if not refresh_token:
            raise HTTPException(status_code=400, detail="Google tidak mengembalikan refresh_token. Pastikan prompt=consent diizinkan.")
        await _set_val(db, "yt_upload_refresh_token", refresh_token, is_encrypted=True)
        await _set_val(db, "yt_upload_connected", "true", is_encrypted=False)
        await db.commit()
        return {"ok": True, "message": "Akun YouTube berhasil diotorisasi!"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Gagal menukar kode otorisasi: {e}")


async def _youtube_creds(db: AsyncSession) -> dict:
    cid = await _get_val(db, "yt_upload_client_id")
    csec_rec = await db.get(AppSetting, "yt_upload_client_secret")
    rt_rec = await db.get(AppSetting, "yt_upload_refresh_token")
    if not cid or not csec_rec or not rt_rec:
        raise HTTPException(status_code=400, detail="Akun YouTube belum terhubung. Hubungkan di Pengaturan → YouTube.")
    return {
        "client_id": cid,
        "client_secret": decrypt_setting(csec_rec.setting_value) if csec_rec.is_encrypted else csec_rec.setting_value,
        "refresh_token": decrypt_setting(rt_rec.setting_value) if rt_rec.is_encrypted else rt_rec.setting_value,
    }


@router.post("/youtube/test", response_model=YouTubeChannelInfo, dependencies=[Depends(get_current_session)])
async def test_youtube(db: AsyncSession = Depends(get_db)):
    creds = await _youtube_creds(db)
    res = await test_youtube_access(creds)
    if res.get("ok"):
        await _set_val(db, "yt_upload_connected", "true", is_encrypted=False)
        await _set_val(db, "yt_upload_channel_name", res.get("channel_name") or "", is_encrypted=False)
        await _set_val(db, "yt_upload_channel_id", res.get("channel_id") or "", is_encrypted=False)
        await db.commit()
    else:
        await _set_val(db, "yt_upload_connected", "false", is_encrypted=False)
        await db.commit()
    return YouTubeChannelInfo(**res)


@router.get("/youtube/channel", response_model=YouTubeChannelInfo, dependencies=[Depends(get_current_session)])
async def get_youtube_channel(db: AsyncSession = Depends(get_db)):
    connected = (await _get_val(db, "yt_upload_connected")) == "true"
    if not connected:
        return YouTubeChannelInfo(ok=False, error="Belum terhubung.")
    return YouTubeChannelInfo(
        ok=True,
        channel_name=await _get_val(db, "yt_upload_channel_name"),
        channel_id=await _get_val(db, "yt_upload_channel_id"),
    )


@public_router.get("/youtube/callback", response_class=HTMLResponse)
async def youtube_oauth_callback(code: str = Query(None), error: str = Query(None),
                                 db: AsyncSession = Depends(get_db)):
    if error:
        return HTMLResponse(f"""<!DOCTYPE html><html><body style="font-family:sans-serif;text-align:center;padding:50px;">
            <h2 style="color:#DC2626;">Otorisasi Dibatalkan atau Gagal</h2><p>{error}</p>
            <button onclick="window.close()">Tutup</button></div></body></html>""", status_code=400)
    if not code:
        return HTMLResponse("<!DOCTYPE html><html><body><h3>Parameter 'code' tidak ditemukan.</h3></body></html>",
                            status_code=400)
    client_id = await _get_val(db, "yt_upload_client_id")
    csec_rec = await db.get(AppSetting, "yt_upload_client_secret")
    if not client_id or not csec_rec:
        return HTMLResponse("<!DOCTYPE html><html><body><h3>Client ID / Secret belum disimpan.</h3></body></html>",
                            status_code=400)
    try:
        client_secret = decrypt_setting(csec_rec.setting_value) if csec_rec.is_encrypted else csec_rec.setting_value
        tokens = await exchange_youtube_code(client_id, client_secret, code.strip(), YOUTUBE_REDIRECT_URI)
        if tokens.get("refresh_token"):
            await _set_val(db, "yt_upload_refresh_token", tokens["refresh_token"], is_encrypted=True)
            await _set_val(db, "yt_upload_connected", "true", is_encrypted=False)
            await db.commit()
        return HTMLResponse("""<!DOCTYPE html><html><head><title>YouTube Terhubung</title></head>
            <body style="font-family:system-ui,sans-serif;text-align:center;padding:60px 20px;background:#FAFAF9;">
              <div style="max-width:460px;margin:0 auto;background:#fff;padding:36px;border-radius:16px;border:1px solid #E7E5E4;">
                <div style="font-size:44px;">🎉</div>
                <h2 style="color:#C2410C;">YouTube Berhasil Terhubung!</h2>
                <p style="color:#57534E;font-size:14px;">Tutup jendela ini dan kembali ke aplikasi.</p>
                <button onclick="window.close()" style="padding:10px 24px;background:#C2410C;color:#fff;border:none;border-radius:8px;cursor:pointer;">Tutup</button>
              </div>
              <script>if(window.opener){window.opener.postMessage({type:'youtube_oauth_success'},'*');setTimeout(function(){window.close();},1500);}</script>
            </body></html>""")
    except Exception as e:
        return HTMLResponse(f"<!DOCTYPE html><html><body><h2>Gagal: {e}</h2></body></html>", status_code=400)


@router.post("/shorts/{short_id}/upload-youtube", response_model=YouTubeExportResponse,
             status_code=status.HTTP_202_ACCEPTED, dependencies=[Depends(get_current_session)])
async def upload_short_to_youtube(short_id: str, payload: YouTubeUploadRequest, db: AsyncSession = Depends(get_db)):
    short = await db.get(RenderedShort, short_id)
    if not short:
        raise HTTPException(status_code=404, detail="Short tidak ditemukan.")
    if short.render_status != "COMPLETED":
        raise HTTPException(status_code=400, detail="Short belum selesai dirender.")
    if short.is_youtube_uploaded:
        existing = await db.scalar(select(YouTubeExport).where(
            YouTubeExport.short_id == short_id,
            YouTubeExport.upload_status == "SUCCESS").order_by(desc(YouTubeExport.uploaded_at)))
        return YouTubeExportResponse(
            export_id=existing.id if existing else short_id, status="ALREADY_UPLOADED")

    custom_thumb = (payload.custom_thumbnail_path or "").strip() or None
    if not custom_thumb:
        cand_short_thumb = f"thumbnails/{short.id}.jpg"
        if os.path.exists(resolve_path(cand_short_thumb)):
            custom_thumb = cand_short_thumb
        elif hasattr(short, "thumbnail_path") and short.thumbnail_path and os.path.exists(resolve_path(short.thumbnail_path)):
            custom_thumb = short.thumbnail_path

    export = YouTubeExport(
        id=uuid.uuid4().hex,
        short_id=short_id,
        title=payload.title.strip(),
        description=(payload.description or "").strip() or None,
        tags=list(payload.tags or []),
        hashtags=list(payload.hashtags or []),
        privacy_status=payload.privacy_status,
        category_id=payload.category_id,
        made_for_kids=bool(payload.made_for_kids),
        custom_thumbnail_path=custom_thumb,
        upload_status="QUEUED",
        upload_progress=0,
    )
    db.add(export)
    db.add(AppJob(id=uuid.uuid4().hex, job_type="YOUTUBE_UPLOAD", ref_id=export.id, status="QUEUED"))
    await db.commit()
    return YouTubeExportResponse(export_id=export.id, status="QUEUED")


@router.get("/shorts/{short_id}/youtube-status", response_model=YouTubeUploadStatusResponse,
            dependencies=[Depends(get_current_session)])
async def get_youtube_upload_status(short_id: str, db: AsyncSession = Depends(get_db)):
    export = await db.scalar(select(YouTubeExport).where(
        YouTubeExport.short_id == short_id).order_by(desc(YouTubeExport.created_at)))
    if not export:
        raise HTTPException(status_code=404, detail="Belum ada upload YouTube untuk short ini.")
    return YouTubeUploadStatusResponse(
        export_id=export.id,
        upload_status=export.upload_status,
        upload_progress=export.upload_progress or 0,
        youtube_video_id=export.youtube_video_id,
        youtube_url=export.youtube_url,
        error_message=export.error_message,
    )


@router.post("/shorts/batch-upload-youtube", response_model=BatchActionResponse,
             dependencies=[Depends(get_current_session)])
async def batch_upload_shorts_to_youtube(payload: BatchDeleteRequest, db: AsyncSession = Depends(get_db)):
    success = 0
    priv_rec = await db.get(AppSetting, "youtube_default_privacy")
    default_priv = priv_rec.setting_value if priv_rec and priv_rec.setting_value in ("public", "unlisted", "private") else "public"
    cat_rec = await db.get(AppSetting, "youtube_default_category")
    default_cat = cat_rec.setting_value if cat_rec and cat_rec.setting_value else "22"
    kids_rec = await db.get(AppSetting, "youtube_default_made_for_kids")
    default_kids = (kids_rec.setting_value == "true") if kids_rec else False

    for s_id in payload.ids:
        try:
            short = await db.get(RenderedShort, s_id)
            if short and short.render_status == "COMPLETED" and not short.is_youtube_uploaded:
                clip = await db.get(ClipCandidate, short.clip_id) if short.clip_id else None
                video = await db.get(SourceVideo, clip.video_id) if clip and clip.video_id else None

                raw_title = ""
                if clip and clip.seo_titles and isinstance(clip.seo_titles, list) and len(clip.seo_titles) > 0:
                    raw_title = str(clip.seo_titles[0]).strip()
                if not raw_title:
                    raw_title = clip.title if clip else short.output_filename

                if "#shorts" not in raw_title.lower() and len(raw_title) <= 92:
                    yt_title = f"{raw_title} #shorts"[:100]
                else:
                    yt_title = raw_title[:100]

                desc_parts = []
                if video and video.source_url:
                    desc_parts.append(f"🎬 Video asli: {video.original_name or (clip.title if clip else 'YouTube')}\n🔗 {video.source_url}")
                if clip and clip.seo_description:
                    desc_parts.append(clip.seo_description.strip())

                tags_list = []
                if clip and clip.seo_tags and isinstance(clip.seo_tags, list):
                    tags_list = [str(t).strip() for t in clip.seo_tags if str(t).strip()][:15]

                hashtags_list = []
                if clip and clip.seo_hashtags and isinstance(clip.seo_hashtags, list):
                    hashtags_list = [str(h).strip() if str(h).startswith("#") else f"#{str(h).strip()}" for h in clip.seo_hashtags][:10]
                elif tags_list:
                    hashtags_list = [f"#{t.replace(' ', '')}" for t in tags_list[:5]]

                if "#shorts" not in [h.lower() for h in hashtags_list]:
                    hashtags_list.insert(0, "#shorts")

                if hashtags_list:
                    desc_parts.append(" ".join(hashtags_list))

                yt_desc = "\n\n".join(desc_parts)[:5000] if desc_parts else None

                thumb_rel = f"thumbnails/{short.id}.jpg"
                custom_thumb = thumb_rel if os.path.exists(resolve_path(thumb_rel)) else None

                export = YouTubeExport(
                    id=uuid.uuid4().hex,
                    short_id=s_id,
                    title=yt_title,
                    description=yt_desc,
                    tags=tags_list,
                    hashtags=hashtags_list,
                    privacy_status=default_priv,
                    category_id=default_cat,
                    made_for_kids=default_kids,
                    custom_thumbnail_path=custom_thumb,
                    upload_status="QUEUED",
                    upload_progress=0,
                )
                db.add(export)
                db.add(AppJob(id=uuid.uuid4().hex, job_type="YOUTUBE_UPLOAD", ref_id=export.id, status="QUEUED"))
                success += 1
        except Exception:
            continue
    await db.commit()
    return BatchActionResponse(
        success_count=success,
        failed_count=len(payload.ids) - success,
        message=f"{success} shorts dimasukkan ke antrean upload YouTube.",
    )
