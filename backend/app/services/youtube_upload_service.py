"""YouTube Data API v3 integration (Phase 5 — 8.1): OAuth 2.0 + resumable upload.

Mirror pola gdrive_service.py: OAuth via httpx, upload via google-api-python-client
(MediaFileUpload resumable + next_chunk) yang dijalankan di thread agar tak blokir loop.
"""

import asyncio
import urllib.parse
from typing import Dict, Any, Optional, Callable
import httpx
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

YOUTUBE_SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]

YOUTUBE_REDIRECT_URI = "http://localhost:8000/api/youtube/callback"
CHUNK_SIZE = 8 * 1024 * 1024  # 8MB per chunk resumable

PRIVACY_STATUSES = ("public", "unlisted", "private")


def generate_youtube_oauth_url(client_id: str, redirect_uri: str = YOUTUBE_REDIRECT_URI,
                               state: str = "autoshorts_youtube") -> str:
    """Bangun URL otorisasi OAuth 2.0 YouTube (scope upload + readonly)."""
    base_auth_url = "https://accounts.google.com/o/oauth2/v2/auth"
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(YOUTUBE_SCOPES),
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    return f"{base_auth_url}?{urllib.parse.urlencode(params)}"


async def exchange_youtube_code(client_id: str, client_secret: str, code: str,
                                redirect_uri: str = YOUTUBE_REDIRECT_URI) -> Dict[str, Any]:
    """Tukar authorization code → {access_token, refresh_token, expires_in}."""
    token_url = "https://oauth2.googleapis.com/token"
    payload = {
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        res = await client.post(token_url, data=payload)
        if res.status_code != 200:
            err_data = res.json() if res.headers.get("content-type", "").startswith("application/json") else {"error": res.text}
            error_desc = err_data.get("error_description") or err_data.get("error") or str(res.status_code)
            raise ValueError(f"Gagal menukar kode otorisasi YouTube: {error_desc}")
        data = res.json()
        return {
            "refresh_token": data.get("refresh_token"),
            "access_token": data.get("access_token"),
            "expires_in": data.get("expires_in"),
        }


async def refresh_youtube_token(client_id: str, client_secret: str, refresh_token: str) -> Dict[str, Any]:
    """Refresh access_token yang expired."""
    token_url = "https://oauth2.googleapis.com/token"
    payload = {
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        res = await client.post(token_url, data=payload)
        if res.status_code != 200:
            raise ValueError(f"Gagal refresh token YouTube: HTTP {res.status_code}")
        data = res.json()
        return {"access_token": data.get("access_token"), "expires_in": data.get("expires_in")}


def get_youtube_service(credentials_data: Dict[str, Any]):
    """Bangun resource YouTube API v3 dari kredensial OAuth2."""
    client_id = credentials_data.get("client_id")
    client_secret = credentials_data.get("client_secret")
    refresh_token = credentials_data.get("refresh_token")
    if not client_id or not client_secret:
        raise ValueError("Client ID atau Client Secret YouTube belum dikonfigurasi.")
    if not refresh_token:
        raise ValueError("Akun YouTube belum diotorisasi. Klik 'Hubungkan YouTube' terlebih dahulu.")
    creds = Credentials(
        token=credentials_data.get("access_token"),
        refresh_token=refresh_token,
        client_id=client_id,
        client_secret=client_secret,
        token_uri="https://oauth2.googleapis.com/token",
        scopes=YOUTUBE_SCOPES,
    )
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


async def test_youtube_access(credentials_data: Dict[str, Any]) -> Dict[str, Any]:
    """Test koneksi: ambil info channel sendiri."""
    def _test():
        try:
            yt = get_youtube_service(credentials_data)
            res = yt.channels().list(mine=True, part="snippet,statistics").execute()
            items = res.get("items", [])
            if not items:
                return {"ok": False, "error": "Tidak ada channel YouTube pada akun ini."}
            ch = items[0]
            return {
                "ok": True,
                "channel_name": ch.get("snippet", {}).get("title", "Unknown"),
                "channel_id": ch.get("id"),
                "subscriber_count": ch.get("statistics", {}).get("subscriberCount"),
            }
        except Exception as e:
            return {"ok": False, "error": str(e)[-300:]}
    return await asyncio.to_thread(_test)


async def upload_video_to_youtube(
    file_path: str,
    title: str,
    description: str = "",
    tags: Optional[list] = None,
    category_id: str = "22",
    privacy_status: str = "public",
    made_for_kids: bool = False,
    credentials_data: Optional[Dict[str, Any]] = None,
    progress_callback: Optional[Callable[[int], Any]] = None,
) -> Dict[str, Any]:
    """
    Resumable upload ke YouTube. Chunk gagal → retry otomatis (num_retries=5).
    Status selfDeclaredMadeForKids diset sesuai made_for_kids (default False = untuk semua kalangan umur).
    Returns: {video_id, youtube_url}.
    """
    if privacy_status not in PRIVACY_STATUSES:
        raise ValueError(f"privacy_status harus salah satu: {PRIVACY_STATUSES}")
    creds = dict(credentials_data or {})

    def _upload():
        yt = get_youtube_service(creds)
        body = {
            "snippet": {
                "title": (title or "Untitled Short")[:100],
                "description": (description or "")[:5000],
                "tags": (tags or [])[:15],
                "categoryId": category_id or "22",
            },
            "status": {
                "privacyStatus": privacy_status,
                "selfDeclaredMadeForKids": bool(made_for_kids),
            },
        }
        media = MediaFileUpload(file_path, mimetype="video/mp4", resumable=True, chunksize=CHUNK_SIZE)
        request = yt.videos().insert(part="snippet,status", body=body, media_body=media)
        response = None
        last_pct = 0
        while response is None:
            status, response = request.next_chunk(num_retries=5)
            if status and progress_callback:
                pct = int(status.progress() * 100)
                if pct >= last_pct + 5:
                    last_pct = pct
                    progress_callback(pct)
        video_id = response.get("id")
        return {"video_id": video_id, "youtube_url": f"https://www.youtube.com/shorts/{video_id}"}

    return await asyncio.to_thread(_upload)


async def set_youtube_thumbnail(video_id: str, thumbnail_path: str,
                                credentials_data: Dict[str, Any]) -> bool:
    """
    Upload custom thumbnail. Best-effort: return False (bukan raise) agar
    kegagalan thumbnail tak menggagalkan upload video.
    MediaFileUpload digunakan untuk membungkus gambar (.jpg / .png).
    """
    def _set():
        try:
            yt = get_youtube_service(credentials_data)
            mimetype = "image/png" if str(thumbnail_path).lower().endswith(".png") else "image/jpeg"
            media = MediaFileUpload(thumbnail_path, mimetype=mimetype, resumable=False)
            yt.thumbnails().set(videoId=video_id, media_body=media).execute()
            return True
        except Exception:
            return False
    return await asyncio.to_thread(_set)
