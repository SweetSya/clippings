"""Phase 5 — 8.1: YouTube upload flow (tanpa jaringan Google asli)."""

import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
import app.database as db_module
from app.models import SourceVideo, ClipCandidate, RenderedShort, YouTubeExport


async def _token(ac: AsyncClient) -> str:
    await db_module.init_db()
    res = await ac.post("/api/auth/setup", json={"pin": "123456"})
    if res.status_code == 201:
        return res.json()["token"]
    res_login = await ac.post("/api/auth/login", json={"pin": "123456"})
    return res_login.json()["token"]


@pytest.mark.asyncio
async def test_youtube_config_and_auth_url_guards():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        token = await _token(ac)
        headers = {"Authorization": f"Bearer {token}"}

        # Tanpa client id → 400
        res = await ac.post("/api/youtube/auth-url", headers=headers)
        assert res.status_code == 400

        # Simpan config
        res_cfg = await ac.post("/api/youtube/config",
                                json={"client_id": "test-client-id", "client_secret": "s3cr3t"},
                                headers=headers)
        assert res_cfg.status_code == 200

        # Auth URL mengandung scope youtube.upload
        res_url = await ac.post("/api/youtube/auth-url", headers=headers)
        assert res_url.status_code == 200
        body = res_url.json()
        assert "accounts.google.com" in body["auth_url"]
        assert "youtube.upload" in body["auth_url"]

        # Test koneksi tanpa refresh token → 400
        res_test = await ac.post("/api/youtube/test", headers=headers)
        assert res_test.status_code == 400

        # Channel belum terhubung
        res_ch = await ac.get("/api/youtube/channel", headers=headers)
        assert res_ch.status_code == 200
        assert res_ch.json()["ok"] is False


@pytest.mark.asyncio
async def test_youtube_upload_enqueue_and_double_guard():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        token = await _token(ac)
        headers = {"Authorization": f"Bearer {token}"}

        vid, cid, sid = uuid.uuid4().hex, uuid.uuid4().hex, uuid.uuid4().hex
        async with db_module.AsyncSessionLocal() as session:
            session.add(SourceVideo(
                id=vid, filename="v.mp4", original_name="V",
                local_file_path="uploads/v.mp4", file_size_bytes=10,
                duration_seconds=60.0, status="READY",
            ))
            session.add(ClipCandidate(
                id=cid, video_id=vid, title="K", start_time_seconds=0.0,
                end_time_seconds=10.0, duration_seconds=10.0, hook_score=80,
            ))
            session.add(RenderedShort(
                id=sid, clip_id=cid, output_filename="o.mp4",
                local_path="exports/o.mp4", render_status="COMPLETED",
            ))
            await session.commit()

        try:
            # Validasi: judul kosong → 422
            res_bad = await ac.post(f"/api/shorts/{sid}/upload-youtube",
                                    json={"title": ""}, headers=headers)
            assert res_bad.status_code == 422

            # Privacy invalid → 422
            res_priv = await ac.post(f"/api/shorts/{sid}/upload-youtube",
                                     json={"title": "T", "privacy_status": "galaxy"},
                                     headers=headers)
            assert res_priv.status_code == 422

            # Enqueue OK
            res = await ac.post(f"/api/shorts/{sid}/upload-youtube",
                                json={"title": "Judul Short", "privacy_status": "unlisted"},
                                headers=headers)
            assert res.status_code == 202, res.text
            export_id = res.json()["export_id"]

            # Status QUEUED
            res_st = await ac.get(f"/api/shorts/{sid}/youtube-status", headers=headers)
            assert res_st.status_code == 200
            assert res_st.json()["upload_status"] == "QUEUED"

            # Tandai uploaded → double guard
            async with db_module.AsyncSessionLocal() as session:
                short = await session.get(RenderedShort, sid)
                short.is_youtube_uploaded = True
                exp = await session.get(YouTubeExport, export_id)
                exp.upload_status = "SUCCESS"
                exp.youtube_video_id = "abc123"
                await session.commit()
            res2 = await ac.post(f"/api/shorts/{sid}/upload-youtube",
                                 json={"title": "Lagi"}, headers=headers)
            assert res2.status_code == 202
            assert res2.json()["status"] == "ALREADY_UPLOADED"

            # Short tak ada → 404
            res404 = await ac.post("/api/shorts/tidak-ada/upload-youtube",
                                   json={"title": "T"}, headers=headers)
            assert res404.status_code == 404
        finally:
            await ac.delete(f"/api/videos/{vid}", headers=headers)


@pytest.mark.asyncio
async def test_youtube_config_auto_upload_and_age():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        token = await _token(ac)
        headers = {"Authorization": f"Bearer {token}"}

        # Simpan config dengan auto_upload=True, default_privacy="unlisted", made_for_kids=False
        res_save = await ac.post(
            "/api/youtube/config",
            json={
                "client_id": "google-client-id-123.apps.googleusercontent.com",
                "client_secret": "my-secret",
                "auto_upload": True,
                "default_privacy": "unlisted",
                "default_category": "22",
                "made_for_kids": False,
            },
            headers=headers,
        )
        assert res_save.status_code == 200

        # Ambil config via GET /api/youtube/config
        res_get = await ac.get("/api/youtube/config", headers=headers)
        assert res_get.status_code == 200
        cfg = res_get.json()
        assert cfg["client_id"] == "google-client-id-123.apps.googleusercontent.com"
        assert cfg["auto_upload"] is True
        assert cfg["default_privacy"] == "unlisted"
        assert cfg["default_category"] == "22"
        assert cfg["made_for_kids"] is False


@pytest.mark.asyncio
async def test_youtube_upload_made_for_kids_and_thumbnail_handling():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        token = await _token(ac)
        headers = {"Authorization": f"Bearer {token}"}

        vid, cid, sid = uuid.uuid4().hex, uuid.uuid4().hex, uuid.uuid4().hex
        async with db_module.AsyncSessionLocal() as session:
            session.add(SourceVideo(
                id=vid, filename="v2.mp4", original_name="Video Gaming",
                local_file_path="uploads/v2.mp4", file_size_bytes=10,
                duration_seconds=30.0, status="READY",
            ))
            session.add(ClipCandidate(
                id=cid, video_id=vid, title="Highlight Momen Lucu", start_time_seconds=0.0,
                end_time_seconds=15.0, duration_seconds=15.0, hook_score=95,
                seo_titles=["Highlight Momen Lucu Banget"],
                seo_description="Deskripsi klip gaming seru",
                seo_tags=["gaming", "lucu"],
                seo_hashtags=["#gaming", "#viral"],
            ))
            session.add(RenderedShort(
                id=sid, clip_id=cid, output_filename="short_game.mp4",
                local_path="exports/short_game.mp4", render_status="COMPLETED",
            ))
            await session.commit()

        try:
            # Enqueue upload with made_for_kids=False and custom_thumbnail_path
            res = await ac.post(
                f"/api/shorts/{sid}/upload-youtube",
                json={
                    "title": "Highlight Momen Lucu #shorts",
                    "description": "Deskripsi klip lengkap",
                    "tags": ["gaming", "shorts"],
                    "hashtags": ["#shorts", "#game"],
                    "privacy_status": "public",
                    "category_id": "20",
                    "made_for_kids": False,
                    "custom_thumbnail_path": "thumbnails/test_thumb.jpg",
                },
                headers=headers,
            )
            assert res.status_code == 202
            export_id = res.json()["export_id"]

            async with db_module.AsyncSessionLocal() as session:
                export = await session.get(YouTubeExport, export_id)
                assert export is not None
                assert export.made_for_kids is False
                assert export.custom_thumbnail_path == "thumbnails/test_thumb.jpg"
                assert export.privacy_status == "public"
                assert export.category_id == "20"
        finally:
            await ac.delete(f"/api/videos/{vid}", headers=headers)


@pytest.mark.asyncio
async def test_shorts_thumbnail_endpoints():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        token = await _token(ac)
        headers = {"Authorization": f"Bearer {token}"}

        vid, cid, sid = uuid.uuid4().hex, uuid.uuid4().hex, uuid.uuid4().hex
        async with db_module.AsyncSessionLocal() as session:
            session.add(SourceVideo(
                id=vid, filename="vt.mp4", original_name="Video Thumb",
                local_file_path="uploads/vt.mp4", file_size_bytes=10,
                duration_seconds=10.0, status="READY",
            ))
            session.add(ClipCandidate(
                id=cid, video_id=vid, title="Clip Thumb", start_time_seconds=0.0,
                end_time_seconds=5.0, duration_seconds=5.0, hook_score=80,
            ))
            session.add(RenderedShort(
                id=sid, clip_id=cid, output_filename="thumb_test.mp4",
                local_path="exports/thumb_test.mp4", render_status="COMPLETED",
            ))
            await session.commit()

        try:
            # Upload custom thumbnail image
            fake_jpeg = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00\xff\xdb"
            files = {"file": ("thumb.jpg", fake_jpeg, "image/jpeg")}
            res_up = await ac.post(f"/api/shorts/{sid}/thumbnail", files=files, headers=headers)
            assert res_up.status_code == 200
            data = res_up.json()
            assert data["ok"] is True
            assert "thumbnails/" in data["custom_thumbnail_path"]

            # Ambil thumbnail via GET
            res_get = await ac.get(f"/api/shorts/{sid}/thumbnail")
            assert res_get.status_code == 200
            assert res_get.headers["content-type"] == "image/jpeg"
        finally:
            await ac.delete(f"/api/videos/{vid}", headers=headers)


@pytest.mark.asyncio
async def test_youtube_upload_service_payload_and_thumbnail(monkeypatch):
    """Verifikasi bahwa upload_video_to_youtube mengirim status.selfDeclaredMadeForKids dan set_youtube_thumbnail memakai MediaFileUpload."""
    from unittest.mock import MagicMock
    import app.services.youtube_upload_service as yt_service

    captured_body = {}

    class MockRequest:
        def next_chunk(self, num_retries=5):
            return None, {"id": "yt_video_999"}

    class MockVideos:
        def insert(self, part, body, media_body):
            nonlocal captured_body
            captured_body = body
            return MockRequest()

    class MockThumbnails:
        def set(self, videoId, media_body):
            mock_set = MagicMock()
            mock_set.execute.return_value = {"status": "ok"}
            return mock_set

    class MockYT:
        def videos(self):
            return MockVideos()
        def thumbnails(self):
            return MockThumbnails()

    monkeypatch.setattr(yt_service, "get_youtube_service", lambda creds: MockYT())

    # Test upload_video_to_youtube dengan made_for_kids=False
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".mp4") as tmp_video:
        res = await yt_service.upload_video_to_youtube(
            file_path=tmp_video.name,
            title="Judul Shorts Keren",
            description="Deskripsi",
            tags=["a", "b"],
            category_id="22",
            privacy_status="public",
            made_for_kids=False,
            credentials_data={"client_id": "c", "client_secret": "s", "refresh_token": "r"},
        )
        assert res["video_id"] == "yt_video_999"
        assert "status" in captured_body
        assert captured_body["status"]["selfDeclaredMadeForKids"] is False
        assert captured_body["status"]["privacyStatus"] == "public"

    # Test set_youtube_thumbnail dengan image file
    with tempfile.NamedTemporaryFile(suffix=".jpg") as tmp_thumb:
        ok = await yt_service.set_youtube_thumbnail(
            video_id="yt_video_999",
            thumbnail_path=tmp_thumb.name,
            credentials_data={"client_id": "c", "client_secret": "s", "refresh_token": "r"},
        )
        assert ok is True


@pytest.mark.asyncio
async def test_pipeline_auto_youtube_upload_enqueued_on_render(monkeypatch):
    """Verifikasi bahwa ketika render short selesai dan youtube_auto_upload aktif, job YOUTUBE_UPLOAD otomatis diantrekan."""
    from app.services.pipeline import handle_render
    from app.models import AppSetting, AppJob
    from sqlalchemy import select

    # Mock render_vertical_clip dan generate_thumbnail agar instan
    async def mock_render(*args, **kwargs):
        out_p = kwargs.get("output_path") or (args[2] if len(args) > 2 else None)
        if out_p:
            import os
            os.makedirs(os.path.dirname(out_p), exist_ok=True)
            with open(out_p, "wb") as f:
                f.write(b"fake_mp4_bytes")
        return True

    async def mock_thumb(*args, **kwargs):
        # Buat file dummy thumb
        thumb_p = kwargs.get("thumb_path") or (args[1] if len(args) > 1 else None)
        if thumb_p:
            import os
            os.makedirs(os.path.dirname(thumb_p), exist_ok=True)
            with open(thumb_p, "wb") as f:
                f.write(b"fake_jpeg")
        return True

    import app.services.pipeline as pipeline_module
    monkeypatch.setattr(pipeline_module, "render_vertical_clip", mock_render)
    monkeypatch.setattr(pipeline_module, "generate_thumbnail", mock_thumb)

    vid, cid, sid, jid = uuid.uuid4().hex, uuid.uuid4().hex, uuid.uuid4().hex, uuid.uuid4().hex

    async with db_module.AsyncSessionLocal() as session:
        # Aktifkan auto upload & connect status
        await session.merge(AppSetting(setting_key="youtube_auto_upload", setting_value="true"))
        await session.merge(AppSetting(setting_key="yt_upload_connected", setting_value="true"))
        await session.merge(AppSetting(setting_key="youtube_default_privacy", setting_value="public"))
        await session.merge(AppSetting(setting_key="youtube_default_made_for_kids", setting_value="false"))

        session.add(SourceVideo(
            id=vid, filename="v_auto.mp4", original_name="Game Clip",
            local_file_path="uploads/v_auto.mp4", file_size_bytes=10,
            duration_seconds=20.0, status="READY",
        ))
        session.add(ClipCandidate(
            id=cid, video_id=vid, title="Boss Fight Epic", start_time_seconds=0.0,
            end_time_seconds=10.0, duration_seconds=10.0, hook_score=92,
            seo_titles=["Epic Boss Fight Climax"],
            seo_description="Pertarungan epik melawan boss",
            seo_tags=["boss", "gaming"],
            seo_hashtags=["#boss", "#gameplay"],
        ))
        session.add(RenderedShort(
            id=sid, clip_id=cid, output_filename="short_boss.mp4",
            local_path="exports/short_boss.mp4", render_status="PENDING",
        ))
        render_job = AppJob(id=jid, job_type="RENDER", ref_id=sid, status="QUEUED")
        session.add(render_job)
        await session.commit()

        # Eksekusi handle_render
        await handle_render(render_job, session)

        # Verifikasi short COMPLETED
        short = await session.get(RenderedShort, sid)
        assert short.render_status == "COMPLETED"

        # Verifikasi YouTubeExport dibuat otomatis
        yt_export = await session.scalar(select(YouTubeExport).where(YouTubeExport.short_id == sid))
        assert yt_export is not None
        assert "Epic Boss Fight Climax" in yt_export.title
        assert "#shorts" in yt_export.title
        assert "Pertarungan epik" in yt_export.description
        assert yt_export.made_for_kids is False
        assert yt_export.privacy_status == "public"
        assert yt_export.custom_thumbnail_path == f"thumbnails/{sid}.jpg"

        # Verifikasi AppJob YOUTUBE_UPLOAD di-enqueue
        yt_job = await session.scalar(select(AppJob).where(AppJob.job_type == "YOUTUBE_UPLOAD", AppJob.ref_id == yt_export.id))
        assert yt_job is not None
        assert yt_job.status == "QUEUED"

