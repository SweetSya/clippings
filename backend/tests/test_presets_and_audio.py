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


@pytest.mark.asyncio
async def test_preset_export_duplicate_import():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        token = await get_auth_token(ac)
        headers = {"Authorization": f"Bearer {token}"}

        res_list = await ac.get("/api/presets", headers=headers)
        assert res_list.status_code == 200
        presets = res_list.json()
        builtin = [p for p in presets if p["is_builtin"]][0]

        # 1. Export builtin
        res_exp = await ac.get(f"/api/presets/{builtin['id']}/export", headers=headers)
        assert res_exp.status_code == 200
        exported = res_exp.json()
        assert "preset" in exported
        assert exported["preset"]["name"] == builtin["name"]
        assert "is_builtin" not in exported["preset"]
        assert "created_at" not in exported["preset"]

        # 2. Export 404
        res_exp404 = await ac.get("/api/presets/does-not-exist/export", headers=headers)
        assert res_exp404.status_code == 404

        # 3. Duplicate builtin → custom baru
        res_dup = await ac.post(f"/api/presets/{builtin['id']}/duplicate", headers=headers)
        assert res_dup.status_code == 201
        dup = res_dup.json()
        assert dup["is_builtin"] is False
        assert dup["name"] == f"Salinan dari {builtin['name']}"[:100]
        assert dup["font"] == builtin["font"]

        # 4. Duplicate 404
        res_dup404 = await ac.post("/api/presets/does-not-exist/duplicate", headers=headers)
        assert res_dup404.status_code == 404

        # 5. Import hasil export → custom baru
        res_imp = await ac.post("/api/presets/import", json=exported, headers=headers)
        assert res_imp.status_code == 201
        imported = res_imp.json()
        assert imported["is_builtin"] is False
        assert imported["name"] == builtin["name"]

        # 6. Import raw (tanpa wrapper) juga bisa
        res_imp2 = await ac.post("/api/presets/import", json=exported["preset"], headers=headers)
        assert res_imp2.status_code == 201

        # 7. Import invalid → 422
        res_bad = await ac.post("/api/presets/import", json={"preset": {"name": ""}}, headers=headers)
        assert res_bad.status_code == 422

        # cleanup
        for pid in [dup["id"], imported["id"], res_imp2.json()["id"]]:
            await ac.delete(f"/api/presets/{pid}", headers=headers)


@pytest.mark.asyncio
async def test_preset_categories_and_seeds():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        token = await get_auth_token(ac)
        headers = {"Authorization": f"Bearer {token}"}

        # Reset builtins menanam 19 preset (11 lama + 8 baru)
        res_reset = await ac.post("/api/presets/reset-builtins", headers=headers)
        assert res_reset.status_code == 200
        all_presets = res_reset.json()
        assert len(all_presets) >= 19
        cats = {p["category"] for p in all_presets if p["is_builtin"]}
        for expected in ["streamer", "podcast", "educational", "motivational", "gaming"]:
            assert expected in cats, f"kategori {expected} hilang"

        # Filter kategori
        res_streamer = await ac.get("/api/presets?category=streamer", headers=headers)
        assert res_streamer.status_code == 200
        streamer = res_streamer.json()
        assert len(streamer) >= 6
        assert all(p["category"] == "streamer" for p in streamer)
        ids = {p["id"] for p in streamer}
        assert "preset_streamer_face_top" in ids
        assert "preset_streamer_face_bottom" in ids

        # Kategori bertahan lewat export→import (jadi custom)
        face_top = next(p for p in streamer if p["id"] == "preset_streamer_face_top")
        res_exp = await ac.get(f"/api/presets/{face_top['id']}/export", headers=headers)
        assert res_exp.status_code == 200
        assert res_exp.json()["preset"]["category"] == "streamer"
        res_imp = await ac.post("/api/presets/import", json=res_exp.json(), headers=headers)
        assert res_imp.status_code == 201
        assert res_imp.json()["category"] == "streamer"
        assert res_imp.json()["is_builtin"] is False
        await ac.delete(f"/api/presets/{res_imp.json()['id']}", headers=headers)


@pytest.mark.asyncio
async def test_video_reanalyze_guards():
    import uuid
    import app.database as db_module
    from app.models import SourceVideo

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        token = await get_auth_token(ac)
        headers = {"Authorization": f"Bearer {token}"}

        # 1. Video tak ada → 404
        res404 = await ac.post("/api/videos/does-not-exist/reanalyze", json={}, headers=headers)
        assert res404.status_code == 404

        # 2. Tanpa transkrip → 404 TRANSCRIPT_NOT_FOUND
        vid = uuid.uuid4().hex
        async with db_module.AsyncSessionLocal() as session:
            session.add(SourceVideo(
                id=vid, filename="x.mp4", original_name="X",
                local_file_path="uploads/x.mp4", file_size_bytes=10,
                duration_seconds=60.0, status="READY",
            ))
            await session.commit()
        try:
            res_no_t = await ac.post(f"/api/videos/{vid}/reanalyze", json={}, headers=headers)
            assert res_no_t.status_code == 404

            # 3. Validasi max < min → 422
            res_bad = await ac.post(
                f"/api/videos/{vid}/reanalyze",
                json={"min_dur": 60, "max_dur": 10},
                headers=headers,
            )
            assert res_bad.status_code == 422
        finally:
            await ac.delete(f"/api/videos/{vid}", headers=headers)

        # 4. Status processing → 409
        vid2 = uuid.uuid4().hex
        async with db_module.AsyncSessionLocal() as session:
            session.add(SourceVideo(
                id=vid2, filename="y.mp4", original_name="Y",
                local_file_path="uploads/y.mp4", file_size_bytes=10,
                duration_seconds=60.0, status="ANALYZING",
            ))
            await session.commit()
        try:
            res409 = await ac.post(f"/api/videos/{vid2}/reanalyze", json={}, headers=headers)
            assert res409.status_code == 409
        finally:
            async with db_module.AsyncSessionLocal() as session:
                v = await session.get(SourceVideo, vid2)
                if v:
                    await session.delete(v)
                    await session.commit()

