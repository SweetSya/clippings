import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.database import init_db


@pytest.mark.asyncio
async def test_health_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/api/health")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] in ["ok", "degraded"]
        assert "db" in data
        assert "storage_writable" in data

@pytest.mark.asyncio
async def test_auth_flow():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Check initial status
        res = await ac.get("/api/auth/status")
        assert res.status_code == 200

        # Attempt to access protected endpoint without token -> 401
        res_unauth = await ac.get("/api/settings")
        assert res_unauth.status_code == 401

        # Setup PIN
        res_setup = await ac.post("/api/auth/setup", json={"pin": "123456"})
        if res_setup.status_code == 201:
            token = res_setup.json()["token"]
            assert token is not None

            # Trying to setup again should fail with 409 Conflict
            res_setup_2 = await ac.post("/api/auth/setup", json={"pin": "654321"})
            assert res_setup_2.status_code == 409

        # Login with valid PIN
        res_login = await ac.post("/api/auth/login", json={"pin": "123456"})
        assert res_login.status_code == 200
        token = res_login.json()["token"]
        assert token

        # Login with wrong PIN -> 401
        res_wrong = await ac.post("/api/auth/login", json={"pin": "999999"})
        assert res_wrong.status_code == 401

        # Access protected route with Bearer token
        headers = {"Authorization": f"Bearer {token}"}
        res_settings = await ac.get("/api/settings", headers=headers)
        assert res_settings.status_code == 200

async def get_test_token(ac: AsyncClient) -> str:
    st_res = await ac.get("/api/auth/status")
    if not st_res.json().get("is_configured"):
        await ac.post("/api/auth/setup", json={"pin": "123456"})
    res_login = await ac.post("/api/auth/login", json={"pin": "123456"})
    token = res_login.json().get("token")
    if not token:
        await ac.post("/api/auth/setup", json={"pin": "123456"})
        res_login = await ac.post("/api/auth/login", json={"pin": "123456"})
        token = res_login.json()["token"]
    return token

@pytest.mark.asyncio
async def test_tts_endpoints():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        token = await get_test_token(ac)
        headers = {"Authorization": f"Bearer {token}"}

        # List voices
        res_voices = await ac.get("/api/tts/voices", headers=headers)
        assert res_voices.status_code == 200
        voices = res_voices.json()
        assert len(voices) > 0
        assert any("id-ID" in v["id"] for v in voices)

        # Generate TTS audio
        res_gen = await ac.post("/api/tts/generate", headers=headers, json={
            "text": "Halo, ini adalah pengujian suara otomatis untuk video klip.",
            "voice": "id-ID-ArdiNeural"
        })
        assert res_gen.status_code == 201
        data = res_gen.json()
        assert "audio_url" in data
        assert data["file_size_bytes"] > 0
        assert data["duration_seconds"] > 0

        # Stream generated audio
        audio_url = data["audio_url"]
        res_audio = await ac.get(audio_url, headers=headers)
        assert res_audio.status_code == 200
        assert res_audio.headers.get("content-type") == "audio/mpeg"

@pytest.mark.asyncio
async def test_general_settings():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        token = await get_test_token(ac)
        headers = {"Authorization": f"Bearer {token}"}

        # Update general settings
        res_update = await ac.post("/api/settings/general", headers=headers, json={
            "min_clip_seconds": 15,
            "max_clip_seconds": 45,
            "yt_quality": "720p"
        })
        assert res_update.status_code == 200

        # Verify through get_settings
        res_get = await ac.get("/api/settings", headers=headers)
        assert res_get.status_code == 200
        settings_data = res_get.json()
        assert settings_data["min_clip_seconds"] == 15
        assert settings_data["max_clip_seconds"] == 45
        assert settings_data["yt_quality"] == "720p"

@pytest.mark.asyncio
async def test_youtube_info_validation():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        token = await get_test_token(ac)
        headers = {"Authorization": f"Bearer {token}"}

        # Empty URL should return 422
        res_empty = await ac.post("/api/videos/youtube/info", headers=headers, json={"url": ""})
        assert res_empty.status_code == 422

@pytest.mark.asyncio
async def test_gdrive_oauth_flow():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        token = await get_test_token(ac)
        headers = {"Authorization": f"Bearer {token}"}

        # User's exact JSON format:
        user_json = '''{
            "web": {
                "client_id": "1001207721542-ojp5dnp7q8bkcq82qep5ic5hbhr74ugp.apps.googleusercontent.com",
                "project_id": "clipping-508702",
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                "client_secret": "GOCSPX-iNN9itelIcKBt0PHkksnV-test"
            }
        }'''

        # Save GDrive settings with the JSON
        res_save = await ac.post("/api/settings/gdrive", headers=headers, json={
            "auth_type": "OAUTH2",
            "credentials_json": user_json,
            "target_folder_id": "1BxiMVs0XR_FAVT_test"
        })
        assert res_save.status_code == 200
        save_data = res_save.json()
        assert save_data["status"] == "saved"
        assert save_data["auth_type"] == "OAUTH2"

        # Verify through get_settings
        res_get = await ac.get("/api/settings", headers=headers)
        assert res_get.status_code == 200
        settings = res_get.json()
        assert settings["gdrive_auth_type"] == "OAUTH2"
        assert settings["gdrive_folder_id"] == "1BxiMVs0XR_FAVT_test"
        assert settings["gdrive_client_id"] == "1001207721542-ojp5dnp7q8bkcq82qep5ic5hbhr74ugp.apps.googleusercontent.com"

        # Generate OAuth URL
        res_url = await ac.get("/api/settings/gdrive/oauth/url", headers=headers)
        assert res_url.status_code == 200
        url_data = res_url.json()
        assert "accounts.google.com/o/oauth2/v2/auth" in url_data["auth_url"]
        assert "1001207721542-ojp5dnp7q8bkcq82qep5ic5hbhr74ugp" in url_data["auth_url"]
        assert "redirect_uri" in url_data

@pytest.mark.asyncio
async def test_ui_preferences():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        token = await get_test_token(ac)
        headers = {"Authorization": f"Bearer {token}"}

        # Update UI preferences
        res_ui = await ac.post("/api/settings/ui-preferences", headers=headers, json={
            "clip_view_mode": "list",
            "shorts_view_mode": "list"
        })
        assert res_ui.status_code == 200
        assert res_ui.json()["clip_view_mode"] == "list"
        assert res_ui.json()["shorts_view_mode"] == "list"

        # Verify through get_settings
        res_get = await ac.get("/api/settings", headers=headers)
        assert res_get.status_code == 200
        data = res_get.json()
        assert data["clip_view_mode"] == "list"
        assert data["shorts_view_mode"] == "list"

@pytest.mark.asyncio
async def test_batch_endpoints_validation():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        token = await get_test_token(ac)
        headers = {"Authorization": f"Bearer {token}"}

        # Empty IDs should return 422
        res_empty = await ac.post("/api/videos/batch-delete", headers=headers, json={"ids": []})
        assert res_empty.status_code == 422

        res_empty_shorts = await ac.post("/api/shorts/batch-delete", headers=headers, json={"ids": []})
        assert res_empty_shorts.status_code == 422

        # Non-existent IDs
        res_batch = await ac.post("/api/videos/batch-delete", headers=headers, json={"ids": ["fake-id-1", "fake-id-2"]})
        assert res_batch.status_code == 200
        assert res_batch.json()["success_count"] == 0
        assert res_batch.json()["failed_count"] == 2

        res_batch_shorts = await ac.post("/api/shorts/batch-delete", headers=headers, json={"ids": ["fake-short-1"]})
        assert res_batch_shorts.status_code == 200
        assert res_batch_shorts.json()["success_count"] == 0
        assert res_batch_shorts.json()["failed_count"] == 1

        # Single delete non-existent short returns 404
        res_del = await ac.delete("/api/shorts/fake-short-1", headers=headers)
        assert res_del.status_code == 404

@pytest.mark.asyncio
async def test_youtube_background_download_and_batch_clip_render():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        token = await get_test_token(ac)
        headers = {"Authorization": f"Bearer {token}"}

        # 1. Test background YouTube download endpoint
        res_yt = await ac.post("/api/videos/youtube/download", headers=headers, json={
            "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "quality": "1080p",
            "auto_generate": True
        })
        assert res_yt.status_code == 201
        data_yt = res_yt.json()
        assert "video_id" in data_yt
        vid = data_yt["video_id"]

        # Check status endpoint shows DOWNLOADING (or progress)
        res_st = await ac.get(f"/api/videos/{vid}/status", headers=headers)
        assert res_st.status_code == 200
        assert res_st.json()["status"] == "DOWNLOADING"

        # 2. Test batch render clips endpoint
        res_batch_empty = await ac.post("/api/clips/batch-render", headers=headers, json={"clip_ids": []})
        assert res_batch_empty.status_code == 422

        res_batch_clips = await ac.post("/api/clips/batch-render", headers=headers, json={
            "clip_ids": ["non-existent-1", "non-existent-2"]
        })
        assert res_batch_clips.status_code == 202
        assert res_batch_clips.json()["success_count"] == 0
        assert res_batch_clips.json()["failed_count"] == 2




