"""Phase 4 — 7.2: transcript cache (hash + reuse)."""

import json
import os
import subprocess
import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from app.main import app
import app.database as db_module
from app.models import SourceVideo, Transcript, AppJob
from app.services.storage_service import hash_file_head, HASH_HEAD_BYTES

SAMPLE = "storage/test_cache_src.mp4"


@pytest.fixture(scope="module", autouse=True)
def _sample_video():
    os.makedirs("storage", exist_ok=True)
    if not os.path.exists(SAMPLE):
        subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=duration=4:size=640x360:rate=30",
             "-f", "lavfi", "-i", "sine=frequency=800:duration=4",
             "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", SAMPLE],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    yield


def test_hash_file_head_deterministic():
    h1 = hash_file_head(SAMPLE)
    h2 = hash_file_head(SAMPLE)
    assert h1 and h1 == h2 and len(h1) == 64
    assert hash_file_head("storage/tidak_ada_xyz.mp4") is None
    # Hanya baca head: file besar vs head sama → hash sama
    assert HASH_HEAD_BYTES == 1024 * 1024


async def _token(ac: AsyncClient) -> str:
    await db_module.init_db()
    res = await ac.post("/api/auth/setup", json={"pin": "123456"})
    if res.status_code == 201:
        return res.json()["token"]
    res_login = await ac.post("/api/auth/login", json={"pin": "123456"})
    return res_login.json()["token"]


@pytest.mark.asyncio
async def test_upload_duplicate_reuses_transcript():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        token = await _token(ac)
        headers = {"Authorization": f"Bearer {token}"}

        async def _upload():
            with open(SAMPLE, "rb") as f:
                res = await ac.post(
                    "/api/videos/upload", headers=headers,
                    files={"file": ("cache.mp4", f, "video/mp4")},
                )
            assert res.status_code == 201, res.text
            return res.json()["video_id"]

        vid1 = await _upload()

        # Simulasi video1 sudah ditranskripsi (tanpa whisper asli)
        t_rel = f"transcripts/{vid1}.json"
        t_abs = os.path.abspath(os.path.join("storage", t_rel))
        os.makedirs(os.path.dirname(t_abs), exist_ok=True)
        with open(t_abs, "w", encoding="utf-8") as f:
            json.dump({"full_text": "halo dunia", "segments": []}, f)
        async with db_module.AsyncSessionLocal() as session:
            session.add(Transcript(id=uuid.uuid4().hex, video_id=vid1,
                                   full_text="halo dunia", transcript_json_path=t_rel))
            await session.commit()

        # Upload berkas SAMA → reuse: langsung LLM_ANALYZE, tanpa AUDIO_EXTRACT
        vid2 = await _upload()
        assert vid2 != vid1

        async with db_module.AsyncSessionLocal() as session:
            jobs = (await session.execute(
                select(AppJob).where(AppJob.ref_id == vid2))).scalars().all()
            types = [j.job_type for j in jobs]
            assert "LLM_ANALYZE" in types
            assert "AUDIO_EXTRACT" not in types
            assert "TRANSCRIBE" not in types
            assert os.path.exists(os.path.abspath(os.path.join("storage", f"transcripts/{vid2}.json")))

        # Bersih-bersih
        await ac.delete(f"/api/videos/{vid1}", headers=headers)
        await ac.delete(f"/api/videos/{vid2}", headers=headers)
