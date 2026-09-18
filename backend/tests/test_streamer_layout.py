import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
import app.database as db_module
from app.models import SourceVideo, ClipCandidate
from app.services.ffmpeg_service import _build_video_filtergraph


def test_streamer_face_top_graph():
    graph, is_complex = _build_video_filtergraph(
        framing_layout="streamer_face_top",
        crop_mode="center",
        crop_offset_x=0,
        face_cy_ratio=0.25,
        subtitle_filter="subtitles='/tmp/s.ass'",
    )
    assert is_complex is True
    assert "[v_face][v_screen]vstack" in graph
    assert "scale=1080:768" in graph
    assert "scale=1080:1152" in graph
    assert "subtitles='/tmp/s.ass'" in graph


def test_streamer_face_bottom_graph_order():
    graph, is_complex = _build_video_filtergraph(
        framing_layout="streamer_face_bottom",
        crop_mode="center",
        crop_offset_x=0,
        face_cy_ratio=0.8,
        subtitle_filter="subtitles='/tmp/s.ass'",
    )
    assert is_complex is True
    assert "[v_screen][v_face]vstack" in graph


def test_streamer_face_ratios_clamped():
    graph, _ = _build_video_filtergraph(
        framing_layout="streamer_face_top", crop_mode="center", crop_offset_x=0,
        face_cy_ratio=99.0,
    )
    assert "ih*0.6" in graph  # cy dijepit 0.9 → band 0.6
    graph_none, _ = _build_video_filtergraph(
        framing_layout="streamer_face_bottom", crop_mode="center", crop_offset_x=0,
    )
    assert "vstack" in graph_none  # default cy tanpa error


async def _token(ac: AsyncClient) -> str:
    await db_module.init_db()
    res = await ac.post("/api/auth/setup", json={"pin": "123456"})
    if res.status_code == 201:
        return res.json()["token"]
    res_login = await ac.post("/api/auth/login", json={"pin": "123456"})
    return res_login.json()["token"]


@pytest.mark.asyncio
async def test_face_anchor_recommends_streamer_layout(monkeypatch):
    import app.routers.clips as clips_router

    async def fake_anchor(video_path, clip_start, clip_end, sample_fps=0.5):
        return {"avg_cx": 0.5, "avg_cy": 0.2, "face_coverage": 0.9,
                "dominant_zone": "top", "recommended_layout": "split_top_bottom",
                "frames_sampled": 10, "frames_with_face": 9}

    monkeypatch.setattr(clips_router, "analyze_face_anchor", fake_anchor)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        token = await _token(ac)
        headers = {"Authorization": f"Bearer {token}"}
        vid, cid = uuid.uuid4().hex, uuid.uuid4().hex
        async with db_module.AsyncSessionLocal() as session:
            session.add(SourceVideo(
                id=vid, filename="x.mp4", original_name="X",
                local_file_path="uploads/x.mp4", file_size_bytes=10,
                duration_seconds=60.0, status="READY",
            ))
            session.add(ClipCandidate(
                id=cid, video_id=vid, title="K", start_time_seconds=0.0,
                end_time_seconds=10.0, duration_seconds=10.0, hook_score=80,
            ))
            await session.commit()
        try:
            import os
            os.makedirs("storage/uploads", exist_ok=True)
            with open("storage/uploads/x.mp4", "wb") as f:
                f.write(b"\x00" * 64)
            res = await ac.post(f"/api/clips/{cid}/analyze-face-anchor", headers=headers)
            assert res.status_code == 200, res.text
            assert res.json()["recommended_layout"] == "streamer_face_top"
        finally:
            await ac.delete(f"/api/videos/{vid}", headers=headers)
            if os.path.exists("storage/uploads/x.mp4"):
                os.remove("storage/uploads/x.mp4")
