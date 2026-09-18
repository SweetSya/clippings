import pytest
import json
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.services.video_type_service import get_all_video_types, get_video_type_by_id, build_video_types_prompt_guide
from app.services.llm_service import extract_highlights_with_llm
from app.services.waha_service import (
    get_or_create_sync_token,
    regenerate_sync_token,
    get_waha_settings,
    process_incoming_waha_message,
    send_waha_message,
    probe_waha_session_status
)
import app.database as db_module
from app.models import AppSetting, SourceVideo

@pytest.mark.asyncio
async def test_video_types_taxonomy_service():
    """Test loading and prompting of video_types taxonomy."""
    types_list = get_all_video_types()
    assert len(types_list) >= 8

    # Verify key genres are present
    type_keys = [t["id"] for t in types_list]
    assert "horror_misteri" in type_keys
    assert "motivasi_quotes" in type_keys
    assert "gaming_streamer" in type_keys
    assert "edukasi_tech" in type_keys
    assert "podcast_talkshow" in type_keys

    # Verify prompt builder output
    prompt_section = build_video_types_prompt_guide()
    assert "TIPE 'horror_misteri'" in prompt_section
    assert "Panduan Kurasi" in prompt_section
    assert "Preset Default" in prompt_section

    # Test single type lookup
    horror_type = get_video_type_by_id("horror_misteri")
    assert horror_type is not None
    assert "Horror" in horror_type["name"]
    assert horror_type["recommended_preset_id"] == "preset_documentary"

@pytest.mark.asyncio
async def test_two_tier_context_llm_highlight_extraction():
    """Test two-tier context parsing with up to 10 highlights limit."""
    mock_segments = [
        {"id": i, "start": i * 15.0, "end": (i + 1) * 15.0, "text": f"Momen ke-{i} dari cerita misteri seram malam hari."}
        for i in range(12)
    ]

    mock_llm_response = {
        "video_type": "horror",
        "recommended_preset_id": "preset-dark-horror",
        "highlights": [
            {
                "title": f"Momen Menegangkan Bagian {i+1}",
                "start_time": i * 15.0,
                "end_time": (i + 1) * 15.0,
                "hook_score": 90 - i,
                "virality_reason": f"Alasan seram {i+1}"
            }
            for i in range(12)  # LLM returns 12, code should cap at max 10
        ]
    }

    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.return_value = AsyncMock(
            status_code=200,
            json=lambda: {
                "choices": [{
                    "message": {
                        "content": json.dumps(mock_llm_response)
                    }
                }]
            }
        )

        highlights = await extract_highlights_with_llm(
            segments=mock_segments,
            video_duration=180.0,
            video_title="Eksplorasi Rumah Hantu Terseram",
            video_description="Kisah penelusuran lokasi angker.",
            full_text="Cerita misteri lengkap...",
            llm_base_url="http://mock-llm.local",
            llm_api_key="mock-key",
            min_dur=10.0,
            max_dur=60.0
        )

        # Must cap at max 10 candidate clips
        assert len(highlights) <= 10
        assert getattr(highlights, "video_type", "") == "horror"
        assert getattr(highlights, "recommended_preset_id", "") == "preset-dark-horror"

@pytest.mark.asyncio
async def test_waha_pairing_and_message_handling():
    """Test WAHA webhook pairing with connect token and command handling."""
    async with db_module.AsyncSessionLocal() as db:
        token = await get_or_create_sync_token(db)
        assert token.startswith("embershorts-")

        # Mock send_waha_message to capture bot replies
        with patch("app.services.waha_service.send_waha_message", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True

            # 1. Test pairing with WRONG token
            wrong_pair_payload = {
                "event": "message",
                "session": "default",
                "payload": {
                    "from": "628123456789@c.us",
                    "body": "connect embershorts-000000",
                    "fromMe": False,
                    "pushName": "User Tester"
                }
            }
            res_wrong = await process_incoming_waha_message(db, wrong_pair_payload)
            assert res_wrong["ok"] is True
            assert res_wrong.get("action") == "pair_failed"
            mock_send.assert_called_once()
            assert "❌ *Token Pairing Tidak Valid" in mock_send.call_args[0][2]

            mock_send.reset_mock()

            # 2. Test pairing with VALID token
            valid_pair_payload = {
                "event": "message",
                "session": "default",
                "payload": {
                    "from": "628123456789@c.us",
                    "body": f"connect {token}",
                    "fromMe": False,
                    "pushName": "User Tester"
                }
            }
            res_valid = await process_incoming_waha_message(db, valid_pair_payload)
            assert res_valid["ok"] is True
            assert res_valid.get("action") == "paired"
            assert res_valid.get("chat_id") == "628123456789@c.us"
            mock_send.assert_called_once()
            assert "✅ *EmberShorts Berhasil Terhubung!*" in mock_send.call_args[0][2]

            # Verify settings saved in DB
            cfg = await get_waha_settings(db)
            assert cfg["paired_chat_id"] == "628123456789@c.us"
            assert cfg["paired_chat_type"] == "direct"

            mock_send.reset_mock()

            # 3. Test #help command
            help_payload = {
                "event": "message",
                "payload": {
                    "from": "628123456789@c.us",
                    "body": "#help",
                    "fromMe": False
                }
            }
            res_help = await process_incoming_waha_message(db, help_payload)
            assert res_help["command"] == "help"
            mock_send.assert_called_once()
            assert "EmberShorts AI Bot Assistant" in mock_send.call_args[0][2]

            mock_send.reset_mock()

            # 4. Test #status command
            status_payload = {
                "event": "message",
                "payload": {
                    "from": "628123456789@c.us",
                    "body": "#status",
                    "fromMe": False
                }
            }
            res_status = await process_incoming_waha_message(db, status_payload)
            assert res_status["command"] == "status"
            mock_send.assert_called_once()
            assert "Status" in mock_send.call_args[0][2]

            mock_send.reset_mock()

            # 5. Test #process and #process all commands
            with patch("app.services.waha_service.get_youtube_info", new_callable=AsyncMock) as mock_info:
                mock_info.return_value = {
                    "title": "Video Horor Nyata",
                    "duration_seconds": 120.0,
                    "description": "Deskripsi misteri"
                }

                # #process mode (clip studio candidate)
                process_payload = {
                    "event": "message",
                    "payload": {
                        "from": "628123456789@c.us",
                        "body": "#process https://youtu.be/abcdef12345",
                        "fromMe": False
                    }
                }
                res_proc = await process_incoming_waha_message(db, process_payload)
                assert res_proc["command"] == "process"
                assert "video_id" in res_proc

                # Verify source video was created in DB
                video = await db.get(SourceVideo, res_proc["video_id"])
                assert video is not None
                assert video.auto_generate_shorts is False

                mock_send.reset_mock()

                # #process all mode (auto shorts render)
                process_all_payload = {
                    "event": "message",
                    "payload": {
                        "from": "628123456789@c.us",
                        "body": "#process all https://youtu.be/abcdef12345",
                        "fromMe": False
                    }
                }
                res_proc_all = await process_incoming_waha_message(db, process_all_payload)
                assert res_proc_all["command"] == "process_all"
                assert "video_id" in res_proc_all

                video_all = await db.get(SourceVideo, res_proc_all["video_id"])
                assert video_all is not None
                assert video_all.auto_generate_shorts is True

@pytest.mark.asyncio
async def test_waha_group_chat_tag_detection():
    """Test group chat pairing and tag/mention command routing."""
    async with db_module.AsyncSessionLocal() as db:
        token = await get_or_create_sync_token(db)

        with patch("app.services.waha_service.send_waha_message", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True

            group_jid = "120363028392819283@g.us"

            # Pair group chat
            group_pair_payload = {
                "payload": {
                    "from": group_jid,
                    "body": f"connect {token}",
                    "fromMe": False,
                    "pushName": "Video Clipper Group"
                }
            }
            res = await process_incoming_waha_message(db, group_pair_payload)
            assert res["action"] == "paired"

            cfg = await get_waha_settings(db)
            assert cfg["paired_chat_id"] == group_jid
            assert cfg["paired_chat_type"] == "group"

            mock_send.reset_mock()

            # Normal chat in group (untagged) should be ignored
            untagged_payload = {
                "payload": {
                    "from": group_jid,
                    "body": "Halo teman-teman apa kabar hari ini?",
                    "fromMe": False
                }
            }
            res_untagged = await process_incoming_waha_message(db, untagged_payload)
            assert res_untagged.get("detail") == "Group message not directed to bot"
            mock_send.assert_not_called()

            # Tagged with #shorts help in group should trigger command
            tagged_payload = {
                "payload": {
                    "from": group_jid,
                    "body": "#shorts help",
                    "fromMe": False
                }
            }
            res_tagged = await process_incoming_waha_message(db, tagged_payload)
            assert res_tagged["command"] == "help"
            mock_send.assert_called_once()

            mock_send.reset_mock()

            # Tagged with #shorts status in group
            status_payload = {
                "payload": {
                    "from": group_jid,
                    "body": "#shorts status",
                    "fromMe": False
                }
            }
            res_status = await process_incoming_waha_message(db, status_payload)
            assert res_status["command"] == "status"
            mock_send.assert_called_once()

@pytest.mark.asyncio
async def test_waha_api_endpoints():
    """Test protected WAHA REST endpoints."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Ensure auth PIN is configured
        st_res = await ac.get("/api/auth/status")
        if not st_res.json().get("is_configured"):
            await ac.post("/api/auth/setup", json={"pin": "123456"})

        res_login = await ac.post("/api/auth/login", json={"pin": "123456"})
        token = res_login.json().get("token")
        if not token:
            await ac.post("/api/auth/setup", json={"pin": "123456"})
            res_login = await ac.post("/api/auth/login", json={"pin": "123456"})
            token = res_login.json()["token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 2. Get status
        res_status = await ac.get("/api/waha/status", headers=headers)
        assert res_status.status_code == 200
        data = res_status.json()
        assert "sync_token" in data
        assert "session_status" in data

        # 3. Update config
        res_cfg = await ac.post("/api/waha/config", headers=headers, json={
            "api_url": "http://localhost:3008",
            "session_name": "test_session",
            "enabled": True
        })
        assert res_cfg.status_code == 200
        assert res_cfg.json()["ok"] is True

        # 4. Regenerate token
        res_regen = await ac.post("/api/waha/token/regenerate", headers=headers)
        assert res_regen.status_code == 200
        new_token = res_regen.json()["token"]
        assert new_token.startswith("embershorts-")

        # 5. Unpair
        res_unpair = await ac.post("/api/waha/unpair", headers=headers)
        assert res_unpair.status_code == 200
        assert res_unpair.json()["ok"] is True

@pytest.mark.asyncio
async def test_waha_message_deduplication_and_event_filtering():
    """Test that message.any events and duplicate message payloads are ignored."""
    async with db_module.AsyncSessionLocal() as db:
        token = await get_or_create_sync_token(db)
        with patch("app.services.waha_service.send_waha_message", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True

            # 1. Event 'message.any' should be ignored
            msg_any_payload = {
                "event": "message.any",
                "payload": {
                    "from": "6289999999@c.us",
                    "body": "#help",
                    "fromMe": False
                }
            }
            res1 = await process_incoming_waha_message(db, msg_any_payload)
            assert res1["ok"] is True
            assert "Ignored event type" in res1["detail"]
            mock_send.assert_not_called()

            # 2. First delivery of 'message' event with unique ID
            msg_payload = {
                "event": "message",
                "payload": {
                    "id": "MSG_UNIQUE_123456",
                    "from": "6289999999@c.us",
                    "body": f"connect {token}",
                    "fromMe": False
                }
            }
            res2 = await process_incoming_waha_message(db, msg_payload)
            assert res2["action"] == "paired"
            mock_send.assert_called_once()

            mock_send.reset_mock()

            # 3. Duplicate delivery with same ID should be ignored
            res3 = await process_incoming_waha_message(db, msg_payload)
            assert res3["ok"] is True
            assert res3["detail"] == "Duplicate message ignored"
            mock_send.assert_not_called()
