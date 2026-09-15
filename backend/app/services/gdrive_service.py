import json
import os
import urllib.parse
import asyncio
from typing import Dict, Any, Optional, Callable
import httpx
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

OAUTH_SCOPES = [
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive"
]

def parse_google_credentials_json(raw_json: str) -> Dict[str, Any]:
    """
    Parse either an OAuth 2.0 Client credentials JSON (web/installed) or a Service Account JSON.
    """
    try:
        data = json.loads(raw_json.strip())
    except Exception as e:
        raise ValueError(f"Berkas JSON tidak valid: {e}")

    # Check for OAuth2 Web Client format (e.g. {"web": {"client_id": "...", "client_secret": "..."}})
    if "web" in data:
        web = data["web"]
        client_id = web.get("client_id")
        client_secret = web.get("client_secret")
        if not client_id or not client_secret:
            raise ValueError("Kunci 'client_id' atau 'client_secret' tidak ditemukan di dalam objek 'web'.")
        return {
            "type": "OAUTH2",
            "client_id": client_id,
            "client_secret": client_secret,
            "project_id": web.get("project_id", ""),
            "auth_uri": web.get("auth_uri", "https://accounts.google.com/o/oauth2/auth"),
            "token_uri": web.get("token_uri", "https://oauth2.googleapis.com/token"),
            "redirect_uris": web.get("redirect_uris", [])
        }

    # Check for OAuth2 Desktop/Installed Client format ({"installed": {...}})
    if "installed" in data:
        inst = data["installed"]
        client_id = inst.get("client_id")
        client_secret = inst.get("client_secret")
        if not client_id or not client_secret:
            raise ValueError("Kunci 'client_id' atau 'client_secret' tidak ditemukan di dalam objek 'installed'.")
        return {
            "type": "OAUTH2",
            "client_id": client_id,
            "client_secret": client_secret,
            "project_id": inst.get("project_id", ""),
            "auth_uri": inst.get("auth_uri", "https://accounts.google.com/o/oauth2/auth"),
            "token_uri": inst.get("token_uri", "https://oauth2.googleapis.com/token"),
            "redirect_uris": inst.get("redirect_uris", [])
        }

    # Check for Service Account Key format
    if data.get("type") == "service_account":
        client_email = data.get("client_email")
        if not client_email:
            raise ValueError("Kunci 'client_email' tidak ditemukan di JSON Service Account.")
        return {
            "type": "SERVICE_ACCOUNT",
            "client_email": client_email,
            "project_id": data.get("project_id", ""),
            "raw_json": json.dumps(data)
        }

    # Flat OAuth2 format
    if "client_id" in data and "client_secret" in data:
        return {
            "type": "OAUTH2",
            "client_id": data["client_id"],
            "client_secret": data["client_secret"],
            "project_id": data.get("project_id", ""),
            "token_uri": data.get("token_uri", "https://oauth2.googleapis.com/token")
        }

    raise ValueError(
        "Format JSON tidak dikenali sebagai OAuth 2.0 Web Client (memiliki objek 'web') ataupun Service Account."
    )

def generate_oauth_url(client_id: str, redirect_uri: str, state: str = "autoshorts_gdrive") -> str:
    """
    Generate the Google OAuth 2.0 authorization URL for user consent.
    """
    base_auth_url = "https://accounts.google.com/o/oauth2/v2/auth"
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(OAUTH_SCOPES),
        "access_type": "offline",
        "prompt": "consent",
        "state": state
    }
    return f"{base_auth_url}?{urllib.parse.urlencode(params)}"

async def exchange_oauth_code(client_id: str, client_secret: str, code: str, redirect_uri: str) -> Dict[str, Any]:
    """
    Exchange authorization code for access_token and refresh_token.
    """
    token_url = "https://oauth2.googleapis.com/token"
    payload = {
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code"
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        res = await client.post(token_url, data=payload)
        if res.status_code != 200:
            err_data = res.json() if res.headers.get("content-type", "").startswith("application/json") else {"error": res.text}
            error_desc = err_data.get("error_description") or err_data.get("error") or str(res.status_code)
            raise ValueError(f"Gagal menukar kode otorisasi: {error_desc}")

        data = res.json()
        refresh_token = data.get("refresh_token")
        access_token = data.get("access_token")
        return {
            "refresh_token": refresh_token,
            "access_token": access_token,
            "expires_in": data.get("expires_in")
        }

def get_drive_service(auth_type: str, credentials_data: Dict[str, Any]):
    """
    Build authenticated Google Drive API v3 resource.
    Supports SERVICE_ACCOUNT or OAUTH2 (with refresh_token).
    """
    if auth_type == "SERVICE_ACCOUNT":
        sa_info = credentials_data.get("service_account_json")
        if not sa_info:
            raise ValueError("Kredensial Service Account JSON belum disimpan.")
        if isinstance(sa_info, str):
            sa_info = json.loads(sa_info)
        creds = service_account.Credentials.from_service_account_info(sa_info, scopes=OAUTH_SCOPES)
        return build("drive", "v3", credentials=creds, cache_discovery=False)
    else:  # OAUTH2
        refresh_token = credentials_data.get("refresh_token")
        client_id = credentials_data.get("client_id")
        client_secret = credentials_data.get("client_secret")

        if not client_id or not client_secret:
            raise ValueError("Client ID atau Client Secret OAuth 2.0 belum dikonfigurasi.")
        if not refresh_token:
            raise ValueError("Akun Google belum diotorisasi via OAuth. Silakan klik tombol 'Hubungkan Akun Google' terlebih dahulu.")

        creds = Credentials(
            token=credentials_data.get("access_token"),
            refresh_token=refresh_token,
            client_id=client_id,
            client_secret=client_secret,
            token_uri="https://oauth2.googleapis.com/token",
            scopes=OAUTH_SCOPES
        )
        return build("drive", "v3", credentials=creds, cache_discovery=False)

async def test_gdrive_access(auth_type: str, credentials_data: Dict[str, Any], folder_id: str) -> Dict[str, Any]:
    """
    Test access to the target Google Drive folder.
    """
    def _test():
        try:
            drive = get_drive_service(auth_type, credentials_data)
            folder = drive.files().get(fileId=folder_id, fields="id, name, mimeType").execute()
            if folder.get("mimeType") != "application/vnd.google-apps.folder":
                return {"ok": False, "error": f"ID '{folder_id}' ditemukan tetapi bukan merupakan folder Google Drive."}
            return {"ok": True, "folder_name": folder.get("name", "Unknown Folder")}
        except Exception as e:
            err_msg = str(e)
            if "404" in err_msg:
                if auth_type == "SERVICE_ACCOUNT":
                    err_msg += " (Folder tidak ditemukan. Pastikan folder sudah di-share ke email Service Account dengan izin Editor)."
                else:
                    err_msg += " (Folder tidak ditemukan atau akun Google yang Anda hubungkan tidak memiliki akses ke folder ini)."
            elif "403" in err_msg:
                err_msg += " (Izin akses ditolak. Pastikan Google Drive API telah diaktifkan di Google Cloud Console dan akun memiliki akses ke folder)."
            return {"ok": False, "error": err_msg}

    return await asyncio.to_thread(_test)

async def upload_file_to_drive(
    file_path: str,
    filename: str,
    folder_id: str,
    auth_type: str,
    credentials_data: Dict[str, Any],
    progress_callback: Optional[Callable[[int], Any]] = None
) -> Dict[str, Any]:
    """
    Perform resumable chunk upload of short video to Google Drive.
    """
    def _upload():
        drive = get_drive_service(auth_type, credentials_data)
        media = MediaFileUpload(
            file_path,
            mimetype="video/mp4",
            resumable=True,
            chunksize=8 * 1024 * 1024  # 8MB chunk
        )
        request = drive.files().create(
            body={"name": filename, "parents": [folder_id]},
            media_body=media,
            fields="id, webViewLink"
        )
        response = None
        last_pct = 0
        while response is None:
            status, response = request.next_chunk(num_retries=5)
            if status and progress_callback:
                pct = int(status.progress() * 100)
                if pct >= last_pct + 5:
                    last_pct = pct
                    progress_callback(pct)

        return {
            "file_id": response.get("id"),
            "web_view_link": response.get("webViewLink", f"https://drive.google.com/file/d/{response.get('id')}/view")
        }

    return await asyncio.to_thread(_upload)
