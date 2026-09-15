import io
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.database import init_db


async def get_auth_token(ac: AsyncClient) -> str:
    await init_db()
    res = await ac.post("/api/auth/setup", json={"pin": "123456"})
    if res.status_code == 201:
        return res.json()["token"]
    res_login = await ac.post("/api/auth/login", json={"pin": "123456"})
    return res_login.json()["token"]


@pytest.mark.asyncio
async def test_text_presets_crud():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        token = await get_auth_token(ac)
        headers = {"Authorization": f"Bearer {token}"}

        # 1. List presets (should have 5 built-in presets seeded)
        res_list = await ac.get("/api/presets", headers=headers)
        assert res_list.status_code == 200
        presets = res_list.json()
        assert len(presets) >= 5
        builtin = [p for p in presets if p["is_builtin"]]
        assert len(builtin) >= 5

        # 2. Create custom preset
        new_preset_payload = {
            "name": "Neon Green Custom",
            "description": "Custom unified test preset",
            "crop_mode": "smart",
            "smart_deadzone": 0.35,
            "smart_pan_seconds": 0.4,
            "font": "Impact",
            "font_size": 48,
            "primary_color": "#00FF66",
            "active_color": "#FFFFFF",
            "subtitle_position": "middle",
            "margin_v": 920,
            "outline_width": 4,
            "shadow_depth": 2,
            "is_uppercase": True,
            "motion_type": "single_word_pop",
            "highlight_bg_color": "#FFCC00",
            "enable_keyword_color": True,
            "keyword_color": "#10B981",
            "enable_dynamic_scaling": True,
            "enable_emoji_injection": True,
            "glow_effect": True,
            "bgm_volume": 0.3,
            "audio_mode": "mix",
            "use_voiceover": True,
            "narration_voice": "id-ID-GadisNeural",
            "narration_style": "summary"
        }
        res_create = await ac.post("/api/presets", json=new_preset_payload, headers=headers)
        assert res_create.status_code == 201
        created = res_create.json()
        assert created["name"] == "Neon Green Custom"
        assert created["description"] == "Custom unified test preset"
        assert created["crop_mode"] == "smart"
        assert created["smart_deadzone"] == 0.35
        assert created["motion_type"] == "single_word_pop"
        assert created["enable_emoji_injection"] is True
        assert created["glow_effect"] is True
        assert created["bgm_volume"] == 0.3
        assert created["narration_voice"] == "id-ID-GadisNeural"
        assert created["is_builtin"] is False
        assert created["is_uppercase"] is True
        preset_id = created["id"]

        # 3. Update custom preset
        res_update = await ac.put(
            f"/api/presets/{preset_id}",
            json={"name": "Neon Green Updated", "font_size": 52, "crop_mode": "center", "bgm_volume": 0.15},
            headers=headers
        )
        assert res_update.status_code == 200
        updated = res_update.json()
        assert updated["name"] == "Neon Green Updated"
        assert updated["font_size"] == 52
        assert updated["crop_mode"] == "center"
        assert updated["bgm_volume"] == 0.15
        assert updated["font_size"] == 52

        # 4. Attempt to update built-in preset -> 400 Bad Request
        builtin_id = builtin[0]["id"]
        res_fail_update = await ac.put(
            f"/api/presets/{builtin_id}",
            json={"name": "Modified Builtin"},
            headers=headers
        )
        assert res_fail_update.status_code == 400

        # 5. Attempt to delete built-in preset -> 400 Bad Request
        res_fail_delete = await ac.delete(f"/api/presets/{builtin_id}", headers=headers)
        assert res_fail_delete.status_code == 400

        # 6. Delete custom preset -> 204 No Content
        res_del = await ac.delete(f"/api/presets/{preset_id}", headers=headers)
        assert res_del.status_code == 204


@pytest.mark.asyncio
async def test_audio_library_crud():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        token = await get_auth_token(ac)
        headers = {"Authorization": f"Bearer {token}"}

        # 1. List audio tracks
        res_list = await ac.get("/api/audio", headers=headers)
        assert res_list.status_code == 200
        assert isinstance(res_list.json(), list)

        # 2. Upload dummy audio track
        fake_audio_content = b"ID3\x03\x00\x00\x00\x00\x00\x00fake audio mp3 byte payload"
        files = {
            "file": ("test_bgm.mp3", io.BytesIO(fake_audio_content), "audio/mpeg")
        }
        data = {"title": "Lofi Chill Beat"}
        res_upload = await ac.post("/api/audio/upload", files=files, data=data, headers=headers)
        assert res_upload.status_code == 201
        track = res_upload.json()
        assert track["title"] == "Lofi Chill Beat"
        assert track["source_type"] == "upload"
        assert track["stream_url"].startswith("/api/audio/")
        track_id = track["id"]

        # 3. Stream audio file
        res_stream = await ac.get(f"/api/audio/{track_id}/stream", headers=headers)
        assert res_stream.status_code == 200
        assert res_stream.content == fake_audio_content

        # 4. Delete audio track
        res_delete = await ac.delete(f"/api/audio/{track_id}", headers=headers)
        assert res_delete.status_code == 204

        # 5. Verify deleted from stream
        res_stream_after = await ac.get(f"/api/audio/{track_id}/stream", headers=headers)
        assert res_stream_after.status_code == 404


@pytest.mark.asyncio
async def test_clip_narration_and_voiceover(monkeypatch):
    import json
    import os
    import uuid
    import app.database as db_module
    from app.models import SourceVideo, ClipCandidate, AppSetting

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        token = await get_auth_token(ac)
        headers = {"Authorization": f"Bearer {token}"}

        # Create test video and clip candidate
        video_id = uuid.uuid4().hex
        clip_id = uuid.uuid4().hex
        async with db_module.AsyncSessionLocal() as session:
            v = SourceVideo(
                id=video_id,
                filename="test.mp4",
                original_name="Test Context Video",
                local_file_path="storage/test.mp4",
                duration_seconds=60.0,
                file_size_bytes=1000,
                status="READY"
            )
            c = ClipCandidate(
                id=clip_id,
                video_id=video_id,
                title="Amazing Moment",
                start_time_seconds=10.0,
                end_time_seconds=25.0,
                duration_seconds=15.0,
                hook_score=90,
                is_selected=True
            )
            setting_conn = AppSetting(
                setting_key="llm_connected",
                setting_value="true"
            )
            # Base URL yang menolak koneksi: service asli dijalankan sampai ke fallback-nya
            # tanpa menyentuh jaringan luar. Ini yang menangkap ketidakcocokan signature.
            setting_base = AppSetting(
                setting_key="llm_base_url",
                setting_value="http://127.0.0.1:9/v1"
            )
            session.add(v)
            session.add(c)
            await session.merge(setting_conn)
            await session.merge(setting_base)
            await session.commit()

        # Transkrip nyata di storage supaya clip_text terisi dari segmen di dalam rentang klip
        transcript_path = f"storage/transcripts/{video_id}.json"
        os.makedirs("storage/transcripts", exist_ok=True)
        with open(transcript_path, "w", encoding="utf-8") as f:
            json.dump({
                "full_text": "Konteks besar video ini membahas strategi konten.",
                "segments": [
                    {"start": 12.0, "end": 16.0, "text": "Ini adalah kalimat penting di dalam klip."},
                    {"start": 40.0, "end": 44.0, "text": "Kalimat ini di luar rentang klip."},
                ],
            }, f)

        try:
            # 1. Test generate-narration melalui service asli, bukan monkeypatch
            res_narr = await ac.post(
                f"/api/clips/{clip_id}/generate-narration",
                json={"style": "hook_story"},
                headers=headers
            )
            assert res_narr.status_code == 200, res_narr.text
            narr_data = res_narr.json()
            assert narr_data["clip_id"] == clip_id
            assert "Ini adalah kalimat penting" in narr_data["narration_text"]
            assert "di luar rentang klip" not in narr_data["narration_text"]
            assert narr_data["estimated_duration_seconds"] > 0
        finally:
            if os.path.exists(transcript_path):
                os.remove(transcript_path)

        # Mock TTS speech generation (edge-tts memerlukan jaringan)
        async def mock_generate_speech(text, output_path, **kwargs):
            import os
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, "wb") as f:
                f.write(b"fake_voice_data")
            return 5.5

        monkeypatch.setattr("app.routers.clips.generate_speech", mock_generate_speech)

        # 2. Test synthesize-voice
        res_voice = await ac.post(
            f"/api/clips/{clip_id}/synthesize-voice",
            json={"text": narr_data["narration_text"], "voice": "id-ID-ArdiNeural"},
            headers=headers
        )
        assert res_voice.status_code == 200
        voice_data = res_voice.json()
        assert voice_data["clip_id"] == clip_id
        assert voice_data["duration_seconds"] == 5.5
        assert voice_data["audio_url"] == f"/api/clips/{clip_id}/narration-audio"

        # 3. Test stream narration audio
        res_audio = await ac.get(f"/api/clips/{clip_id}/narration-audio", headers=headers)
        assert res_audio.status_code == 200
        assert res_audio.content == b"fake_voice_data"

