import os
import pytest
import pytest_asyncio
import subprocess
from httpx import AsyncClient, ASGITransport
from app.main import app
import app.database as db_module
from app.database import init_db
from app.models import SourceVideo, ClipCandidate, RenderedShort, GoogleDriveExport, TextPreset, AudioTrack
from app.services.pipeline import (
    handle_audio_extract,
    handle_transcribe,
    handle_llm_analyze,
    handle_render,
    handle_gdrive_upload
)
from app.services.ffmpeg_service import render_vertical_clip
from app.services.reframe_service import detect_head_timeline
from app.services.storage_service import resolve_path
from app.models import AppJob
import uuid

TEST_VIDEO_PATH = "storage/test_sample.mp4"


@pytest.fixture(scope="session", autouse=True)
def create_sample_video():
    os.makedirs("storage", exist_ok=True)
    if not os.path.exists(TEST_VIDEO_PATH):
        # Generate 6 seconds test video with audio tone
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "testsrc=duration=6:size=1280x720:rate=30",
            "-f", "lavfi", "-i", "sine=frequency=1000:duration=6",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            TEST_VIDEO_PATH
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    yield
    # Cleanup test video if needed

@pytest.mark.asyncio
async def test_full_pipeline_flow():
    # Seed dulu (termasuk 5 preset bawaan) supaya state DB deterministik dan tidak
    # bergantung pada urutan berkas test.
    await init_db()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Login
        res_login = await ac.post("/api/auth/login", json={"pin": "123456"})
        token = res_login.json()["token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 2. Upload video
        with open(TEST_VIDEO_PATH, "rb") as f:
            res_upload = await ac.post(
                "/api/videos/upload",
                headers=headers,
                files={"file": ("sample.mp4", f, "video/mp4")}
            )
        assert res_upload.status_code == 201
        upload_data = res_upload.json()
        video_id = upload_data["video_id"]
        assert video_id is not None
        assert upload_data["duration_seconds"] > 0

        # Check thumbnail
        res_thumb = await ac.get(f"/api/videos/{video_id}/thumbnail", headers=headers)
        assert res_thumb.status_code == 200

        # 3. Process pipeline step by step
        async with db_module.AsyncSessionLocal() as session:
            # Step A: AUDIO_EXTRACT
            job_extract = AppJob(id=uuid.uuid4().hex, job_type="AUDIO_EXTRACT", ref_id=video_id)
            await handle_audio_extract(job_extract, session)
            video = await session.get(SourceVideo, video_id)
            assert video.duration_seconds > 0
            assert os.path.exists(f"storage/audio/{video_id}.wav")

            # Step B: TRANSCRIBE
            job_transcribe = AppJob(id=uuid.uuid4().hex, job_type="TRANSCRIBE", ref_id=video_id)
            await handle_transcribe(job_transcribe, session)
            assert os.path.exists(f"storage/transcripts/{video_id}.json")

            # Step C: LLM_ANALYZE
            job_llm = AppJob(id=uuid.uuid4().hex, job_type="LLM_ANALYZE", ref_id=video_id)
            await handle_llm_analyze(job_llm, session)
            await session.refresh(video)
            assert video.status == "READY"

        # 4. Fetch clips via API
        res_clips = await ac.get(f"/api/videos/{video_id}/clips", headers=headers)
        assert res_clips.status_code == 200
        clips = res_clips.json()
        assert len(clips) > 0
        clip_id = clips[0]["id"]

        # 5. Trigger render for clip
        res_render = await ac.post(
            f"/api/clips/{clip_id}/render",
            headers=headers,
            json={
                "crop_mode": "center",
                "font": "Helvetica",
                "font_size": 44,
                "active_color": "#FFCC00",
                "primary_color": "#FFFFFF"
            }
        )
        assert res_render.status_code == 202
        short_id = res_render.json()["short_id"]

        # Execute render job
        async with db_module.AsyncSessionLocal() as session:
            job_render = AppJob(id=uuid.uuid4().hex, job_type="RENDER", ref_id=short_id)
            await handle_render(job_render, session)
            short = await session.get(RenderedShort, short_id)
            assert short.render_status == "COMPLETED"
            assert short.render_progress == 100
            assert os.path.exists(f"storage/{short.local_path}")

        # 6. Check shorts download endpoint
        res_dl = await ac.get(f"/api/shorts/{short_id}/download", headers=headers)
        assert res_dl.status_code == 200
        assert res_dl.headers.get("content-type") == "video/mp4"

        # 7. Test Anti-Double Upload to Google Drive
        async with db_module.AsyncSessionLocal() as session:
            short = await session.get(RenderedShort, short_id)
            # Simulate initial successful upload
            short.is_drive_uploaded = True
            export = GoogleDriveExport(
                id=uuid.uuid4().hex,
                short_id=short_id,
                gdrive_file_id="1fake_drive_file_id_12345",
                gdrive_web_view_link="https://drive.google.com/file/d/1fake_drive_file_id_12345/view",
                upload_status="SUCCESS",
                upload_progress=100
            )
            session.add(export)
            await session.commit()

        # Trigger upload API again -> should detect already uploaded and prevent double upload!
        res_gdrive = await ac.post(f"/api/shorts/{short_id}/upload-gdrive", headers=headers)
        assert res_gdrive.status_code == 202
        data_gdrive = res_gdrive.json()
        assert data_gdrive["status"] == "ALREADY_UPLOADED"
        assert "Double-upload dicegah" in data_gdrive["message"]
        assert data_gdrive["gdrive_file_id"] == "1fake_drive_file_id_12345"

        # 8. Smart crop must degrade gracefully on a video without any detectable face
        smart_short_id = uuid.uuid4().hex
        async with db_module.AsyncSessionLocal() as session:
            smart_short = RenderedShort(
                id=smart_short_id,
                clip_id=clip_id,
                output_filename=f"{smart_short_id}_9x16.mp4",
                local_path=f"exports/{smart_short_id}_9x16.mp4",
                render_settings={
                    "crop_mode": "smart",
                    "crop_offset_x": 0,
                    "smart_deadzone": 0.5,
                    "font": "Helvetica",
                    "font_size": 44,
                    "active_color": "#FFCC00",
                    "primary_color": "#FFFFFF",
                    "subtitle_position": "bottom"
                },
                render_status="PENDING",
                render_progress=0
            )
            session.add(smart_short)
            await session.commit()

            job_smart = AppJob(id=uuid.uuid4().hex, job_type="RENDER", ref_id=smart_short_id)
            await handle_render(job_smart, session)
            await session.refresh(smart_short)

            assert smart_short.render_status == "COMPLETED"
            assert os.path.exists(f"storage/{smart_short.local_path}")

        # 9. Reframe preview endpoint reports geometry and falls back to center without faces
        res_preview = await ac.get(
            f"/api/clips/{clip_id}/reframe-preview?deadzone=0.5", headers=headers
        )
        assert res_preview.status_code == 200
        preview = res_preview.json()

        assert preview["src_width"] == 1280
        assert preview["src_height"] == 720
        assert preview["crop_width"] == 405          # round(720 * 9/16)
        assert preview["max_offset_x"] == 875        # 1280 - 405
        assert preview["detected"] is False
        assert len(preview["keyframes"]) == 1
        assert abs(preview["keyframes"][0]["x"] - 437.5) <= 1

        # 10. Preset styling applies, but explicit request values win — including 0
        preset_id = uuid.uuid4().hex
        async with db_module.AsyncSessionLocal() as session:
            session.add(TextPreset(
                id=preset_id,
                name="Uji Presedensi",
                font="Arial",
                font_size=90,
                outline_width=5,
                shadow_depth=4,
                is_uppercase=True,
                is_builtin=False
            ))
            await session.commit()

        precedence_short_id = uuid.uuid4().hex
        async with db_module.AsyncSessionLocal() as session:
            session.add(RenderedShort(
                id=precedence_short_id,
                clip_id=clip_id,
                output_filename=f"{precedence_short_id}_9x16.mp4",
                local_path=f"exports/{precedence_short_id}_9x16.mp4",
                render_settings={
                    "crop_mode": "center",
                    "crop_offset_x": 0,
                    "preset_id": preset_id,
                    "font_size": 30,       # menimpa nilai preset (90)
                    "outline_width": 0     # nilai 0 harus dihormati, bukan ditelan
                },
                render_status="PENDING",
                render_progress=0
            ))
            await session.commit()

        async with db_module.AsyncSessionLocal() as session:
            job_prec = AppJob(id=uuid.uuid4().hex, job_type="RENDER", ref_id=precedence_short_id)
            await handle_render(job_prec, session)
            short_prec = await session.get(RenderedShort, precedence_short_id)
            assert short_prec.render_status == "COMPLETED"

        with open(f"storage/subtitles/{clip_id}.ass", "r", encoding="utf-8") as f:
            ass_content = f.read()
        style_line = next(line for line in ass_content.splitlines() if line.startswith("Style:"))

        assert style_line.startswith("Style: Caption,Arial,30,")   # font dari preset, ukuran dari request
        assert ",100,100,0,0,1,0,4,2," in style_line               # BorderStyle,Outline=0,Shadow=4,Alignment

        # 11. Setiap mode audio harus menyelesaikan render dengan BGM + voiceover terpasang
        track_id = uuid.uuid4().hex
        bgm_rel = f"audio_library/{track_id}.mp3"
        bgm_abs = resolve_path(bgm_rel)
        os.makedirs(os.path.dirname(bgm_abs), exist_ok=True)

        voice_rel = f"tts/{clip_id}_test_voice.mp3"
        voice_abs = resolve_path(voice_rel)
        os.makedirs(os.path.dirname(voice_abs), exist_ok=True)

        for tone_path, freq in ((bgm_abs, 440), (voice_abs, 880)):
            subprocess.run(
                ["ffmpeg", "-y", "-f", "lavfi", "-i", f"sine=frequency={freq}:duration=5",
                 "-c:a", "libmp3lame", tone_path],
                check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )

        async with db_module.AsyncSessionLocal() as session:
            session.add(AudioTrack(
                id=track_id,
                title="Uji BGM",
                source_type="upload",
                local_path=bgm_rel,
                duration_seconds=5.0,
                file_size_bytes=os.path.getsize(bgm_abs)
            ))
            clip_row = await session.get(ClipCandidate, clip_id)
            clip_row.narration_text = "Narasi uji untuk mode audio."
            clip_row.narration_voice = "id-ID-ArdiNeural"
            clip_row.narration_audio_path = voice_rel
            await session.commit()

        for audio_mode in ("mix", "replace", "original"):
            mode_short_id = uuid.uuid4().hex
            async with db_module.AsyncSessionLocal() as session:
                session.add(RenderedShort(
                    id=mode_short_id,
                    clip_id=clip_id,
                    output_filename=f"{mode_short_id}_9x16.mp4",
                    local_path=f"exports/{mode_short_id}_9x16.mp4",
                    render_settings={
                        "crop_mode": "center",
                        "crop_offset_x": 0,
                        "use_voiceover": True,
                        "narration_text": "Narasi uji untuk mode audio.",
                        "audio_track_id": track_id,
                        "bgm_volume": 0.3,
                        "audio_mode": audio_mode
                    },
                    render_status="PENDING",
                    render_progress=0
                ))
                await session.commit()

            async with db_module.AsyncSessionLocal() as session:
                job_mode = AppJob(id=uuid.uuid4().hex, job_type="RENDER", ref_id=mode_short_id)
                await handle_render(job_mode, session)
                short_mode = await session.get(RenderedShort, mode_short_id)

                assert short_mode.render_status == "COMPLETED", f"mode {audio_mode} gagal"
                assert os.path.exists(f"storage/{short_mode.local_path}")


@pytest.mark.asyncio
async def test_reframe_detection_handles_video_without_faces():
    """Deteksi wajah pada video tanpa manusia harus mengembalikan list kosong, bukan error."""
    samples = await detect_head_timeline(TEST_VIDEO_PATH, 0.0, 2.0, src_width=1280)
    assert samples == []


@pytest.mark.asyncio
async def test_render_accepts_dynamic_crop_expression():
    """Ekspresi crop per-frame harus diterima FFmpeg pada pipeline render yang sebenarnya."""
    output_path = "storage/test_smart_expr.mp4"
    if os.path.exists(output_path):
        os.remove(output_path)

    ok = await render_vertical_clip(
        video_path=TEST_VIDEO_PATH,
        ass_path=None,
        output_path=output_path,
        start_time=0.0,
        end_time=3.0,
        crop_mode="center",
        crop_x_expr="if(lt(t,1.000),0,120+(t-1.000)*60)"
    )

    assert ok
    assert os.path.exists(output_path)
    os.remove(output_path)
