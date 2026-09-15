import json
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import AppSetting
from app.schemas import (
    SettingsResponse,
    AISettingsRequest,
    GDriveSettingsRequest,
    GDriveTestResponse,
    GDriveOAuthUrlResponse,
    GDriveOAuthExchangeRequest,
    GeneralSettingsRequest,
    UIPreferencesRequest,
    AITestRequest,
    AITestResponse
)
from app.core.security import get_current_session
from app.core.crypto import encrypt_setting, decrypt_setting
from app.services.gdrive_service import (
    test_gdrive_access,
    parse_google_credentials_json,
    generate_oauth_url,
    exchange_oauth_code
)
from app.services.llm_service import test_llm_connection

router = APIRouter(prefix="/settings", tags=["Settings"], dependencies=[Depends(get_current_session)])
public_router = APIRouter(prefix="/settings", tags=["Settings"])

DEFAULT_REDIRECT_URI = "http://localhost:8000/api/settings/gdrive/oauth/callback"

async def _get_val(db: AsyncSession, key: str) -> str | None:
    setting = await db.get(AppSetting, key)
    return setting.setting_value if setting else None

async def _set_val(db: AsyncSession, key: str, value: str, is_encrypted: bool = False):
    setting = await db.get(AppSetting, key)
    if is_encrypted and value:
        stored_value = encrypt_setting(value)
    else:
        stored_value = value

    if setting:
        setting.setting_value = stored_value
        setting.is_encrypted = is_encrypted
    else:
        new_s = AppSetting(setting_key=key, setting_value=stored_value, is_encrypted=is_encrypted)
        db.add(new_s)

@router.get("", response_model=SettingsResponse)
async def get_settings(db: AsyncSession = Depends(get_db)):
    base_url = await _get_val(db, "llm_base_url")
    model = await _get_val(db, "llm_model")
    api_key = await _get_val(db, "llm_api_key")
    prompt = await _get_val(db, "llm_prompt")
    llm_connected_str = await _get_val(db, "llm_connected")
    llm_connected = (llm_connected_str == "true")

    gd_auth = (await _get_val(db, "gdrive_auth_type")) or "OAUTH2"
    gd_folder = await _get_val(db, "gdrive_folder_id")
    gd_sa = await _get_val(db, "gdrive_sa_json")
    gd_cid = await _get_val(db, "gdrive_client_id")
    gd_rt = await _get_val(db, "gdrive_refresh_token")

    min_dur_s = await _get_val(db, "min_clip_seconds")
    max_dur_s = await _get_val(db, "max_clip_seconds")
    yt_q_s = await _get_val(db, "yt_quality")

    clip_vm = (await _get_val(db, "clip_view_mode")) or "grid"
    shorts_vm = (await _get_val(db, "shorts_view_mode")) or "grid"

    min_clip = int(min_dur_s) if min_dur_s else 10
    max_clip = int(max_dur_s) if max_dur_s else 60
    yt_quality = yt_q_s if yt_q_s else "1080p"

    oauth_connected = bool(gd_cid and gd_rt)
    if gd_auth == "SERVICE_ACCOUNT":
        gdrive_configured = bool(gd_folder and gd_sa)
    else:
        gdrive_configured = bool(gd_folder and gd_cid and gd_rt)

    return SettingsResponse(
        llm_base_url=base_url,
        llm_model=model,
        llm_configured=bool(base_url and (api_key or "localhost" in base_url or "127.0.0.1" in base_url)),
        llm_connected=llm_connected,
        llm_prompt=prompt,
        gdrive_auth_type=gd_auth,
        gdrive_folder_id=gd_folder,
        gdrive_configured=gdrive_configured,
        gdrive_client_id=gd_cid,
        gdrive_oauth_connected=oauth_connected,
        gdrive_redirect_uri=DEFAULT_REDIRECT_URI,
        min_clip_seconds=min_clip,
        max_clip_seconds=max_clip,
        yt_quality=yt_quality,
        clip_view_mode=clip_vm,
        shorts_view_mode=shorts_vm
    )

@router.post("/ui-preferences")
async def update_ui_preferences(payload: UIPreferencesRequest, db: AsyncSession = Depends(get_db)):
    clip_vm = payload.clip_view_mode or (await _get_val(db, "clip_view_mode")) or "grid"
    shorts_vm = payload.shorts_view_mode or (await _get_val(db, "shorts_view_mode")) or "grid"
    if payload.clip_view_mode in ["grid", "list"]:
        await _set_val(db, "clip_view_mode", payload.clip_view_mode, is_encrypted=False)
        clip_vm = payload.clip_view_mode
    if payload.shorts_view_mode in ["grid", "list"]:
        await _set_val(db, "shorts_view_mode", payload.shorts_view_mode, is_encrypted=False)
        shorts_vm = payload.shorts_view_mode
    await db.commit()
    return {
        "status": "saved",
        "ok": True,
        "message": "Preferensi tampilan berhasil disimpan.",
        "clip_view_mode": clip_vm,
        "shorts_view_mode": shorts_vm
    }

@router.post("/general")
async def update_general_settings(payload: GeneralSettingsRequest, db: AsyncSession = Depends(get_db)):
    await _set_val(db, "min_clip_seconds", str(payload.min_clip_seconds), is_encrypted=False)
    await _set_val(db, "max_clip_seconds", str(payload.max_clip_seconds), is_encrypted=False)
    await _set_val(db, "yt_quality", payload.yt_quality.strip(), is_encrypted=False)
    await db.commit()
    return {"status": "saved", "message": "Pengaturan durasi klip dan YouTube berhasil disimpan."}

@router.post("/ai")
async def update_ai_settings(payload: AISettingsRequest, db: AsyncSession = Depends(get_db)):
    await _set_val(db, "llm_base_url", payload.base_url.strip(), is_encrypted=False)
    if payload.api_key is not None:
        await _set_val(db, "llm_api_key", payload.api_key.strip(), is_encrypted=True)
    await _set_val(db, "llm_model", payload.model_name.strip(), is_encrypted=False)
    await _set_val(db, "llm_temperature", str(payload.temperature), is_encrypted=False)
    if payload.prompt is not None:
        await _set_val(db, "llm_prompt", payload.prompt, is_encrypted=False)
    # Require testing again when credentials or model change
    await _set_val(db, "llm_connected", "false", is_encrypted=False)
    await db.commit()
    return {"status": "saved", "message": "Konfigurasi AI berhasil disimpan. Silakan klik 'Uji Koneksi AI' untuk memverifikasi status koneksi."}

@router.post("/ai/test", response_model=AITestResponse)
async def test_ai_route(payload: AITestRequest = None, db: AsyncSession = Depends(get_db)):
    base_url = (payload.base_url.strip() if payload and payload.base_url else None) or (await _get_val(db, "llm_base_url"))
    model = (payload.model_name.strip() if payload and payload.model_name else None) or (await _get_val(db, "llm_model")) or "gpt-4o-mini"

    api_key = None
    if payload and payload.api_key is not None:
        api_key = payload.api_key.strip()
    else:
        api_key_rec = await db.get(AppSetting, "llm_api_key")
        if api_key_rec and api_key_rec.setting_value:
            api_key = decrypt_setting(api_key_rec.setting_value) if api_key_rec.is_encrypted else api_key_rec.setting_value

    if not base_url:
        await _set_val(db, "llm_connected", "false", is_encrypted=False)
        await db.commit()
        return AITestResponse(ok=False, error="Base URL AI belum ditentukan.")

    res = await test_llm_connection(base_url=base_url, api_key=api_key, model_name=model)
    is_ok = bool(res.get("ok", False))
    await _set_val(db, "llm_connected", "true" if is_ok else "false", is_encrypted=False)
    await db.commit()

    return AITestResponse(
        ok=is_ok,
        message=res.get("message"),
        error=res.get("error"),
        model=res.get("model")
    )

@router.post("/gdrive")
async def update_gdrive_settings(payload: GDriveSettingsRequest, db: AsyncSession = Depends(get_db)):
    auth_type = payload.auth_type
    target_folder_id = payload.target_folder_id.strip()
    await _set_val(db, "gdrive_folder_id", target_folder_id, is_encrypted=False)

    raw_json = payload.credentials_json or payload.service_account_json
    if raw_json and raw_json.strip():
        try:
            parsed = parse_google_credentials_json(raw_json.strip())
            if parsed["type"] == "OAUTH2":
                auth_type = "OAUTH2"
                await _set_val(db, "gdrive_auth_type", "OAUTH2", is_encrypted=False)
                await _set_val(db, "gdrive_client_id", parsed["client_id"].strip(), is_encrypted=False)
                await _set_val(db, "gdrive_client_secret", parsed["client_secret"].strip(), is_encrypted=True)
            elif parsed["type"] == "SERVICE_ACCOUNT":
                auth_type = "SERVICE_ACCOUNT"
                await _set_val(db, "gdrive_auth_type", "SERVICE_ACCOUNT", is_encrypted=False)
                await _set_val(db, "gdrive_sa_json", parsed["raw_json"].strip(), is_encrypted=True)
        except ValueError as ve:
            raise HTTPException(status_code=400, detail=str(ve))
    else:
        await _set_val(db, "gdrive_auth_type", auth_type, is_encrypted=False)
        if payload.client_id:
            await _set_val(db, "gdrive_client_id", payload.client_id.strip(), is_encrypted=False)
        if payload.client_secret:
            await _set_val(db, "gdrive_client_secret", payload.client_secret.strip(), is_encrypted=True)
        if payload.refresh_token:
            await _set_val(db, "gdrive_refresh_token", payload.refresh_token.strip(), is_encrypted=True)

    await db.commit()
    msg = "Konfigurasi Google Drive berhasil disimpan."
    if auth_type == "OAUTH2":
        cid = await _get_val(db, "gdrive_client_id")
        rt = await _get_val(db, "gdrive_refresh_token")
        if cid and not rt:
            msg += " Silakan klik 'Hubungkan Akun Google' untuk melakukan otorisasi login."
    return {"status": "saved", "message": msg, "auth_type": auth_type}

@router.get("/gdrive/oauth/url", response_model=GDriveOAuthUrlResponse)
async def get_gdrive_oauth_url(redirect_uri: str = DEFAULT_REDIRECT_URI, db: AsyncSession = Depends(get_db)):
    client_id = await _get_val(db, "gdrive_client_id")
    if not client_id:
        raise HTTPException(
            status_code=400,
            detail="Client ID OAuth 2.0 belum dikonfigurasi. Silakan masukkan JSON OAuth terlebih dahulu."
        )
    auth_url = generate_oauth_url(client_id=client_id, redirect_uri=redirect_uri)
    return GDriveOAuthUrlResponse(auth_url=auth_url, redirect_uri=redirect_uri)

@router.post("/gdrive/oauth/exchange")
async def exchange_gdrive_oauth_code_route(payload: GDriveOAuthExchangeRequest, db: AsyncSession = Depends(get_db)):
    client_id = await _get_val(db, "gdrive_client_id")
    csec_rec = await db.get(AppSetting, "gdrive_client_secret")
    if not client_id or not csec_rec:
        raise HTTPException(status_code=400, detail="Client ID atau Secret OAuth 2.0 belum dikonfigurasi.")

    client_secret = decrypt_setting(csec_rec.setting_value) if csec_rec.is_encrypted else csec_rec.setting_value
    redirect_uri = payload.redirect_uri or DEFAULT_REDIRECT_URI

    try:
        tokens = await exchange_oauth_code(
            client_id=client_id,
            client_secret=client_secret,
            code=payload.code.strip(),
            redirect_uri=redirect_uri
        )
        refresh_token = tokens.get("refresh_token")
        if not refresh_token:
            # If re-consenting without offline prompt, try checking if token exists
            raise HTTPException(
                status_code=400,
                detail="Google tidak mengembalikan refresh_token. Pastikan prompt=consent diizinkan."
            )

        await _set_val(db, "gdrive_refresh_token", refresh_token, is_encrypted=True)
        await _set_val(db, "gdrive_auth_type", "OAUTH2", is_encrypted=False)
        await db.commit()
        return {"ok": True, "message": "Akun Google berhasil diotorisasi via OAuth 2.0!"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Gagal menukar kode otorisasi: {e}")

@router.post("/gdrive/test", response_model=GDriveTestResponse)
async def test_gdrive(db: AsyncSession = Depends(get_db)):
    auth_type = (await _get_val(db, "gdrive_auth_type")) or "OAUTH2"
    folder_id = await _get_val(db, "gdrive_folder_id")
    if not folder_id:
        return GDriveTestResponse(ok=False, error="Target folder ID belum ditentukan.")

    creds_data = {}
    if auth_type == "SERVICE_ACCOUNT":
        sa_rec = await db.get(AppSetting, "gdrive_sa_json")
        if not sa_rec:
            return GDriveTestResponse(ok=False, error="JSON Service Account belum disimpan.")
        try:
            creds_data["service_account_json"] = decrypt_setting(sa_rec.setting_value) if sa_rec.is_encrypted else sa_rec.setting_value
        except Exception as e:
            return GDriveTestResponse(ok=False, error=f"Gagal mendeskripsi kredensial: {e}")
    else:  # OAUTH2
        cid = await _get_val(db, "gdrive_client_id")
        csec_rec = await db.get(AppSetting, "gdrive_client_secret")
        rt_rec = await db.get(AppSetting, "gdrive_refresh_token")
        if not cid or not csec_rec:
            return GDriveTestResponse(ok=False, error="Kredensial OAuth2 (Client ID & Secret) belum disimpan.")
        if not rt_rec:
            return GDriveTestResponse(ok=False, error="Akun Google belum diotorisasi. Silakan klik 'Hubungkan Akun Google' untuk login.")

        creds_data["client_id"] = cid
        creds_data["client_secret"] = decrypt_setting(csec_rec.setting_value) if csec_rec.is_encrypted else csec_rec.setting_value
        creds_data["refresh_token"] = decrypt_setting(rt_rec.setting_value) if rt_rec.is_encrypted else rt_rec.setting_value

    res = await test_gdrive_access(auth_type, creds_data, folder_id)
    return GDriveTestResponse(
        ok=res.get("ok", False),
        folder_name=res.get("folder_name"),
        error=res.get("error")
    )

# ----------------- Public OAuth Callback Route -----------------
@public_router.get("/gdrive/oauth/callback", response_class=HTMLResponse)
async def gdrive_oauth_callback(
    code: str = Query(None),
    error: str = Query(None),
    db: AsyncSession = Depends(get_db)
):
    if error:
        return HTMLResponse(
            f"""<!DOCTYPE html><html><body style="font-family:sans-serif;text-align:center;padding:50px;background:#FAFAF9;">
            <div style="max-width:480px;margin:0 auto;background:#fff;padding:24px;border-radius:12px;border:1px solid #E7E5E4;">
            <h2 style="color:#DC2626;">Otorisasi Dibatalkan atau Gagal</h2>
            <p style="color:#57534E;">Error dari Google: {error}</p>
            <button onclick="window.close()" style="padding:8px 16px;background:#C2410C;color:#fff;border:none;border-radius:6px;cursor:pointer;">Tutup</button>
            </div></body></html>""",
            status_code=400
        )

    if not code:
        return HTMLResponse(
            """<!DOCTYPE html><html><body style="font-family:sans-serif;text-align:center;padding:50px;">
            <h3>Parameter 'code' tidak ditemukan dalam URL pengalihan.</h3>
            </body></html>""",
            status_code=400
        )

    client_id = await _get_val(db, "gdrive_client_id")
    csec_rec = await db.get(AppSetting, "gdrive_client_secret")
    if not client_id or not csec_rec:
        return HTMLResponse(
            """<!DOCTYPE html><html><body style="font-family:sans-serif;text-align:center;padding:50px;">
            <h3>Client ID / Secret belum disimpan di sistem. Silakan simpan JSON terlebih dahulu di aplikasi.</h3>
            </body></html>""",
            status_code=400
        )

    client_secret = decrypt_setting(csec_rec.setting_value) if csec_rec.is_encrypted else csec_rec.setting_value
    try:
        tokens = await exchange_oauth_code(
            client_id=client_id,
            client_secret=client_secret,
            code=code.strip(),
            redirect_uri=DEFAULT_REDIRECT_URI
        )
        refresh_token = tokens.get("refresh_token")
        if refresh_token:
            await _set_val(db, "gdrive_refresh_token", refresh_token, is_encrypted=True)
            await _set_val(db, "gdrive_auth_type", "OAUTH2", is_encrypted=False)
            await db.commit()

        return HTMLResponse(
            """<!DOCTYPE html>
            <html>
            <head><title>Otorisasi Berhasil</title></head>
            <body style="font-family:system-ui,-apple-system,sans-serif;text-align:center;padding:60px 20px;background:#FAFAF9;color:#1C1917;">
              <div style="max-width:460px;margin:0 auto;background:#fff;padding:36px;border-radius:16px;box-shadow:0 4px 24px rgba(0,0,0,0.08);border:1px solid #E7E5E4;">
                <div style="font-size:44px;margin-bottom:12px;">🎉</div>
                <h2 style="margin:0 0 8px;color:#C2410C;">Akun Google Berhasil Terhubung!</h2>
                <p style="color:#57534E;font-size:14px;line-height:1.5;">Otorisasi Google Drive berhasil disimpan. Anda dapat menutup jendela ini dan kembali ke aplikasi AutoShorts.</p>
                <button onclick="window.close()" style="margin-top:20px;padding:10px 24px;background:#C2410C;color:#fff;border:none;border-radius:8px;font-weight:600;cursor:pointer;">Tutup Jendela</button>
              </div>
              <script>
                if (window.opener) {
                  window.opener.postMessage({ type: 'gdrive_oauth_success' }, '*');
                  setTimeout(function() { window.close(); }, 1500);
                } else {
                  setTimeout(function() { window.location.href = 'http://localhost:3000/'; }, 2500);
                }
              </script>
            </body>
            </html>"""
        )
    except Exception as e:
        return HTMLResponse(
            f"""<!DOCTYPE html><html><body style="font-family:sans-serif;text-align:center;padding:50px;">
            <h2 style="color:#DC2626;">Gagal Menukar Token Google</h2>
            <p>{e}</p>
            </body></html>""",
            status_code=400
        )
