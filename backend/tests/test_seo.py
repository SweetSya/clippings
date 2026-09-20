"""Phase 5 — 9.1 + 9.2: AI SEO generator & platform templates."""

import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
import app.database as db_module
from app.models import SourceVideo, ClipCandidate
from app.services.seo_service import (
    apply_platform_rules,
    heuristic_seo,
    generate_youtube_seo,
    PLATFORM_SEO_RULES,
)
import uuid


def test_platform_rules_youtube():
    out = apply_platform_rules("youtube_shorts", {
        "titles": ["A" * 120, "B"],
        "description": "x",
        "tags": ["a", "a", "B ", "c"],
        "hashtags": ["viral", "#SHORTS", "#viral"],
    })
    assert len(out["titles"][0]) <= 100
    assert out["hashtags"][0] == "#shorts"
    assert len(out["hashtags"]) <= 6
    assert len(out["tags"]) <= 15


def test_platform_rules_tiktok_reels():
    out = apply_platform_rules("tiktok", {"titles": ["T"], "tags": [], "hashtags": []})
    assert "#fyp" in out["hashtags"] and "#foryou" in out["hashtags"]
    out2 = apply_platform_rules("instagram_reels", {"titles": ["T"], "tags": [], "hashtags": []})
    assert "#reels" in out2["hashtags"]
    # Platform asing → fallback youtube
    out3 = apply_platform_rules("galaxy", {"titles": ["T"], "tags": [], "hashtags": []})
    assert "#shorts" in out3["hashtags"]


def test_heuristic_seo_shape():
    seo = heuristic_seo("Rahasia Sukses", "uang modal profit cuan besar sekali", "Video Bisnis")
    assert len(seo["titles"]) == 3
    assert all(len(t) <= 60 for t in seo["titles"])
    assert "#shorts" in seo["hashtags"]
    assert "Like & Subscribe" in seo["description"]


@pytest.mark.asyncio
async def test_generate_youtube_seo_falls_back_without_llm():
    seo = await generate_youtube_seo("Judul", "teks klip", llm_base_url="")
    assert len(seo["titles"]) == 3


async def _token(ac: AsyncClient) -> str:
    await db_module.init_db()
    res = await ac.post("/api/auth/setup", json={"pin": "123456"})
    if res.status_code == 201:
        return res.json()["token"]
    res_login = await ac.post("/api/auth/login", json={"pin": "123456"})
    return res_login.json()["token"]


@pytest.mark.asyncio
async def test_generate_seo_endpoint_heuristic():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        token = await _token(ac)
        headers = {"Authorization": f"Bearer {token}"}
        vid, cid = uuid.uuid4().hex, uuid.uuid4().hex
        async with db_module.AsyncSessionLocal() as session:
            session.add(SourceVideo(
                id=vid, filename="v.mp4", original_name="V",
                local_file_path="uploads/v.mp4", file_size_bytes=10,
                duration_seconds=60.0, status="READY",
            ))
            session.add(ClipCandidate(
                id=cid, video_id=vid, title="Momen Penting", start_time_seconds=0.0,
                end_time_seconds=10.0, duration_seconds=10.0, hook_score=80,
            ))
            await session.commit()
        try:
            res = await ac.post(f"/api/clips/{cid}/generate-seo",
                                json={"platform": "youtube_shorts", "language": "id"},
                                headers=headers)
            assert res.status_code == 200, res.text
            data = res.json()
            assert len(data["titles"]) == 3
            assert "#shorts" in data["hashtags"]
            # Tersimpan ke klip
            res_clips = await ac.get(f"/api/videos/{vid}/clips", headers=headers)
            clip = [c for c in res_clips.json() if c["id"] == cid][0]
            assert clip["seo_titles"] and len(clip["seo_titles"]) == 3

            # Platform asing → dinormalisasi youtube
            res2 = await ac.post(f"/api/clips/{cid}/generate-seo",
                                 json={"platform": "galaxy"}, headers=headers)
            assert res2.status_code == 200

            # Klip tak ada → 404
            res404 = await ac.post("/api/clips/tidak-ada/generate-seo",
                                   json={}, headers=headers)
            assert res404.status_code == 404
        finally:
            await ac.delete(f"/api/videos/{vid}", headers=headers)
