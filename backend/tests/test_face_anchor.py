import os
import tempfile
import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
import app.database as db_module
from app.models import SourceVideo, ClipCandidate
from app.services.reframe_service import (
    classify_face_zone,
    recommend_layout_for_zone,
)


def test_classify_face_zone_boundaries():
    assert classify_face_zone(0.0) == "top"
    assert classify_face_zone(0.349) == "top"
    assert classify_face_zone(0.35) == "center"
    assert classify_face_zone(0.5) == "center"
    assert classify_face_zone(0.65) == "center"
    assert classify_face_zone(0.651) == "bottom"
    assert classify_face_zone(1.0) == "bottom"
    assert classify_face_zone(None) == "center"
    assert classify_face_zone("rusak") == "center"


def test_recommend_layout_for_zone():
    assert recommend_layout_for_zone("top") == "split_top_bottom"
    assert recommend_layout_for_zone("bottom") == "split_bottom_top"
    assert recommend_layout_for_zone("center") == "single"
    assert recommend_layout_for_zone("aneh") == "single"


async def _token(ac: AsyncClient) -> str:
    await db_module.init_db()
    res = await ac.post("/api/auth/setup", json={"pin": "123456"})
    if res.status_code == 201:
        return res.json()["token"]
    res_login = await ac.post("/api/auth/login", json={"pin": "123456"})
    return res_login.json()["token"]


@pytest.mark.asyncio
async def test_face_anchor_endpoint_graceful():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        token = await _token(ac)
        headers = {"Authorization": f"Bearer {token}"}

        # 404 untuk klip tak ada
        res404 = await ac.post("/api/clips/tidak-ada/analyze-face-anchor", headers=headers)
        assert res404.status_code == 404

        # Berkas video kosong: tanpa model/deteksi → 200 graceful coverage 0 + warning
        os.makedirs("storage/uploads", exist_ok=True)
        fake_rel = f"uploads/faceanchor_{uuid.uuid4().hex[:8]}.mp4"
        fake_abs = os.path.abspath(os.path.join("storage", fake_rel))
        with open(fake_abs, "wb") as f:
            f.write(b"\x00" * 64)
        vid, cid = uuid.uuid4().hex, uuid.uuid4().hex
        async with db_module.AsyncSessionLocal() as session:
            session.add(SourceVideo(
                id=vid, filename="x.mp4", original_name="X",
                local_file_path=fake_rel, file_size_bytes=64,
                duration_seconds=60.0, status="READY",
            ))
            session.add(ClipCandidate(
                id=cid, video_id=vid, title="K", start_time_seconds=0.0,
                end_time_seconds=10.0, duration_seconds=10.0, hook_score=80,
            ))
            await session.commit()
        try:
            res = await ac.post(f"/api/clips/{cid}/analyze-face-anchor", headers=headers)
            assert res.status_code == 200, res.text
            data = res.json()
            assert data["clip_id"] == cid
            assert data["dominant_zone"] in ("top", "center", "bottom")
            assert data["face_coverage"] == 0.0
            assert data["warning"] is not None
            # Coverage tersimpan ke klip
            res_clips = await ac.get(f"/api/videos/{vid}/clips", headers=headers)
            assert res_clips.status_code == 200
        finally:
            await ac.delete(f"/api/videos/{vid}", headers=headers)
            if os.path.exists(fake_abs):
                os.remove(fake_abs)
