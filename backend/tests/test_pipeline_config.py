import pytest
import uuid
from unittest.mock import patch, AsyncMock
import app.database as db_module
from app.models import SourceVideo, ClipCandidate, RenderedShort, YouTubeExport
from app.services.pipeline_rules import (
    get_pipeline_config,
    save_pipeline_config,
    match_pipeline_preset,
    check_and_send_consolidated_whatsapp_summary,
    _set_val
)


@pytest.mark.asyncio
async def test_pipeline_config_defaults_and_save():
    async with db_module.AsyncSessionLocal() as db_session:
        # 1. Check default config
        cfg = await get_pipeline_config(db_session)
        assert cfg["auto_clip_enabled"] is True
        assert cfg["min_score"] >= 0
        assert len(cfg["context_rules"]) > 0
        assert "default_preset_id" in cfg

        # 2. Update config
        new_rules = [
            {"id": "rule-1", "name": "Gaming Custom", "context": "wolverine, brawl", "preset_id": "preset_streamer_pip_circle"},
            {"id": "rule-2", "name": "Podcast Custom", "context": "podcast, curhat", "preset_id": "preset_minimalist"}
        ]
        updated = await save_pipeline_config(db_session, {
            "min_score": 85,
            "auto_upload_youtube": True,
            "auto_upload_gdrive": True,
            "auto_notify_whatsapp": True,
            "whatsapp_target_chat": "6281234567890@c.us",
            "context_rules": new_rules
        })

        assert updated["min_score"] == 85
        assert updated["auto_upload_youtube"] is True
        assert updated["auto_upload_gdrive"] is True
        assert updated["whatsapp_target_chat"] == "6281234567890@c.us"
        assert len(updated["context_rules"]) == 2
        assert updated["context_rules"][0]["context"] == "wolverine, brawl"


def test_match_pipeline_preset():
    rules = [
        {"id": "1", "name": "Gaming", "context": "gaming, streamer, gameplay", "preset_id": "preset_streamer_pip_circle"},
        {"id": "2", "name": "Podcast", "context": "podcast, talkshow, wawancara", "preset_id": "preset_minimalist"},
        {"id": "3", "name": "Edukasi", "context": "edukasi, tutorial, coding", "preset_id": "preset_tech_tutorial_center"},
    ]

    # Test match by video type
    preset, rule, reason = match_pipeline_preset(
        video_type="gaming_streamer",
        video_title="Main Game Santai",
        video_desc=None,
        clip_title="Momen Epic",
        rules=rules
    )
    assert preset == "preset_streamer_pip_circle"
    assert rule["id"] == "1"
    assert "gaming" in reason.lower()

    # Test match by title keyword
    preset2, rule2, reason2 = match_pipeline_preset(
        video_type="umum",
        video_title="Belajar Coding Python untuk Pemula",
        video_desc=None,
        clip_title="Variabel dan Loop",
        rules=rules
    )
    assert preset2 == "preset_tech_tutorial_center"
    assert rule2["id"] == "3"

    # Test fallback to default preset
    preset3, rule3, reason3 = match_pipeline_preset(
        video_type="vlog",
        video_title="Jalan-jalan ke Bali",
        video_desc=None,
        clip_title="Pantai Kuta Indah",
        rules=rules,
        default_preset_id="preset_tiktok_bold"
    )
    assert preset3 == "preset_tiktok_bold"
    assert rule3 is None
    assert "default" in reason3.lower()


@pytest.mark.asyncio
async def test_consolidated_whatsapp_summary_notification():
    async with db_module.AsyncSessionLocal() as db_session:
        # Setup video
        v_id = uuid.uuid4().hex
        video = SourceVideo(
            id=v_id,
            filename="wolverine.mp4",
            original_name="Marvel's Wolverine GAMEPLAY Walkthrough.mp4",
            local_file_path="uploads/wolverine.mp4",
            file_size_bytes=1024,
            status="READY"
        )
        db_session.add(video)

        # Setup 2 clips
        c1 = ClipCandidate(
            id=uuid.uuid4().hex,
            video_id=v_id,
            title="Wolverine Cakar Robot Sentinel",
            start_time_seconds=10.0,
            end_time_seconds=40.0,
            duration_seconds=30.0,
            hook_score=90
        )
        c2 = ClipCandidate(
            id=uuid.uuid4().hex,
            video_id=v_id,
            title="Cara Menghindar Laser Musuh",
            start_time_seconds=50.0,
            end_time_seconds=80.0,
            duration_seconds=30.0,
            hook_score=85
        )
        db_session.add_all([c1, c2])

        # Setup 2 rendered shorts
        s1 = RenderedShort(id=uuid.uuid4().hex, clip_id=c1.id, output_filename="s1.mp4", local_path="exports/s1.mp4", render_status="COMPLETED")
        s2 = RenderedShort(id=uuid.uuid4().hex, clip_id=c2.id, output_filename="s2.mp4", local_path="exports/s2.mp4", render_status="COMPLETED")
        db_session.add_all([s1, s2])

        # Case A: One YouTube upload is finished, but the other is still QUEUED
        yt1 = YouTubeExport(id=uuid.uuid4().hex, short_id=s1.id, title="Wolverine Cakar Robot Sentinel", upload_status="SUCCESS", youtube_video_id="yt_vid_1")
        yt2 = YouTubeExport(id=uuid.uuid4().hex, short_id=s2.id, title="Cara Menghindar Laser Musuh", upload_status="QUEUED")
        db_session.add_all([yt1, yt2])

        await _set_val(db_session, "pipeline_whatsapp_target_chat", "")
        await _set_val(db_session, "waha_paired_chat_id", "628999@c.us")
        await _set_val(db_session, "pipeline_auto_notify_whatsapp", "true")
        await db_session.commit()

        with patch("app.services.pipeline_rules.send_waha_message", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True

            # Should NOT send because yt2 is still QUEUED
            res_early = await check_and_send_consolidated_whatsapp_summary(v_id, db_session)
            assert res_early is False
            mock_send.assert_not_called()

            # Now yt2 finishes upload
            yt2.upload_status = "SUCCESS"
            yt2.youtube_video_id = "yt_vid_2"
            await db_session.commit()

            # Should send 1 single consolidated message containing both links!
            res_done = await check_and_send_consolidated_whatsapp_summary(v_id, db_session)
            assert res_done is True
            assert mock_send.call_count == 1

            args = mock_send.call_args[0]
            sent_chat = args[1]
            sent_text = args[2]

            assert sent_chat == "628999@c.us"
            assert "Wolverine Cakar Robot Sentinel" in sent_text
            assert "https://youtube.com/shorts/yt_vid_1" in sent_text
            assert "Cara Menghindar Laser Musuh" in sent_text
            assert "https://youtube.com/shorts/yt_vid_2" in sent_text
            assert "Total:* 2 Shorts" in sent_text

            # Test idempotency: Calling it again must NOT send duplicate message
            res_repeat = await check_and_send_consolidated_whatsapp_summary(v_id, db_session)
            assert res_repeat is False
            assert mock_send.call_count == 1  # Still 1, not called again


async def get_auth_token(ac) -> str:
    res = await ac.post("/api/auth/setup", json={"pin": "123456"})
    if res.status_code == 201:
        return res.json()["token"]
    res_login = await ac.post("/api/auth/login", json={"pin": "123456"})
    return res_login.json()["token"]


@pytest.mark.asyncio
async def test_pipeline_api_endpoints():
    from httpx import AsyncClient, ASGITransport
    from app.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        token = await get_auth_token(ac)
        headers = {"Authorization": f"Bearer {token}"}

        # 1. GET /api/pipeline/config
        res = await ac.get("/api/pipeline/config", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert "min_score" in data
        assert "context_rules" in data

        # 2. POST /api/pipeline/config
        update_payload = {
            "min_score": 78,
            "auto_clip_enabled": True,
            "auto_upload_youtube": True,
            "context_rules": [
                {"id": "r1", "name": "Gaming Streamer", "context": "gaming", "preset_id": "preset_streamer_pip_circle"}
            ]
        }
        res_post = await ac.post("/api/pipeline/config", json=update_payload, headers=headers)
        assert res_post.status_code == 200
        assert res_post.json()["ok"] is True
        assert res_post.json()["config"]["min_score"] == 78

        # 3. POST /api/pipeline/test-match
        match_req = {
            "title": "Gameplay Walkthrough Final Boss",
            "video_type": "gaming_streamer"
        }
        res_match = await ac.post("/api/pipeline/test-match", json=match_req, headers=headers)
        assert res_match.status_code == 200
        m_data = res_match.json()
        assert m_data["matched"] is True
        assert m_data["selected_preset_id"] == "preset_streamer_pip_circle"
