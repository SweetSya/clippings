"""Endpoint antrean jobs untuk Queue view."""

import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
import app.database as db_module
from app.models import AppJob, SourceVideo, ClipCandidate, RenderedShort


async def _token(ac: AsyncClient) -> str:
    await db_module.init_db()
    res = await ac.post("/api/auth/setup", json={"pin": "123456"})
    if res.status_code == 201:
        return res.json()["token"]
    res_login = await ac.post("/api/auth/login", json={"pin": "123456"})
    return res_login.json()["token"]


@pytest.mark.asyncio
async def test_jobs_list_enriched_and_filtered():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        token = await _token(ac)
        headers = {"Authorization": f"Bearer {token}"}

        vid, cid, sid = uuid.uuid4().hex, uuid.uuid4().hex, uuid.uuid4().hex
        async with db_module.AsyncSessionLocal() as session:
            session.add(SourceVideo(
                id=vid, filename="v.mp4", original_name="Video Antrean",
                local_file_path="uploads/v.mp4", file_size_bytes=10,
                duration_seconds=60.0, status="ANALYZING",
            ))
            session.add(ClipCandidate(
                id=cid, video_id=vid, title="Klip Antrean", start_time_seconds=0.0,
                end_time_seconds=10.0, duration_seconds=10.0, hook_score=80,
            ))
            session.add(RenderedShort(
                id=sid, clip_id=cid, output_filename="o.mp4",
                local_path="exports/o.mp4", render_status="RENDERING",
            ))
            session.add(AppJob(id=uuid.uuid4().hex, job_type="LLM_ANALYZE", ref_id=vid, status="RUNNING", progress=50))
            session.add(AppJob(id=uuid.uuid4().hex, job_type="RENDER", ref_id=sid, status="QUEUED"))
            await session.commit()

        try:
            res = await ac.get("/api/jobs", headers=headers)
            assert res.status_code == 200, res.text
            items = res.json()
            by_type = {j["job_type"]: j for j in items if j["ref_id"] in (vid, sid)}
            assert by_type["LLM_ANALYZE"]["ref_kind"] == "video"
            assert by_type["LLM_ANALYZE"]["ref_label"] == "Video Antrean"
            assert by_type["LLM_ANALYZE"]["progress"] == 50
            assert by_type["RENDER"]["ref_kind"] == "short"
            assert "Klip Antrean" in by_type["RENDER"]["ref_label"]

            res_q = await ac.get("/api/jobs", params={"status": "QUEUED"}, headers=headers)
            assert res_q.status_code == 200
            assert all(j["status"] == "QUEUED" for j in res_q.json())

            res_t = await ac.get("/api/jobs", params={"job_type": "render"}, headers=headers)
            assert res_t.status_code == 200
            assert all(j["job_type"] == "RENDER" for j in res_t.json())
        finally:
            await ac.delete(f"/api/videos/{vid}", headers=headers)
