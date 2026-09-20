"""Transcript subtitle editor + whisper language override."""

import json
import os
import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
import app.database as db_module
from app.models import SourceVideo
from app.services import whisper_service


async def _token(ac: AsyncClient) -> str:
    await db_module.init_db()
    res = await ac.post("/api/auth/setup", json={"pin": "123456"})
    if res.status_code == 201:
        return res.json()["token"]
    res_login = await ac.post("/api/auth/login", json={"pin": "123456"})
    return res_login.json()["token"]


@pytest.mark.asyncio
async def test_whisper_language_forwarded_to_worker(monkeypatch):
    seen = {}

    def fake_worker(audio_path, model_name, device, compute_type, language=None):
        seen["language"] = language
        return {"language": language or "id", "full_text": "halo", "segments": []}

    monkeypatch.setattr(whisper_service, "_transcribe_worker", fake_worker)
    await whisper_service.transcribe_audio("/x.wav", "/tmp/t_out.json", language="id")
    assert seen["language"] == "id"
    if os.path.exists("/tmp/t_out.json"):
        os.remove("/tmp/t_out.json")


@pytest.mark.asyncio
async def test_transcript_segments_crud():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        token = await _token(ac)
        headers = {"Authorization": f"Bearer {token}"}
        vid = uuid.uuid4().hex
        async with db_module.AsyncSessionLocal() as session:
            session.add(SourceVideo(
                id=vid, filename="v.mp4", original_name="V",
                local_file_path="uploads/v.mp4", file_size_bytes=10,
                duration_seconds=60.0, status="READY", language="id",
            ))
            await session.commit()
        t_path = os.path.abspath(os.path.join("storage", f"transcripts/{vid}.json"))
        os.makedirs(os.path.dirname(t_path), exist_ok=True)
        with open(t_path, "w", encoding="utf-8") as f:
            json.dump({"full_text": "halo dunia", "segments": [
                {"start": 0.0, "end": 2.0, "text": "halo",
                 "words": [{"word": "halo", "start": 0.0, "end": 1.0, "probability": 0.9}]},
                {"start": 2.0, "end": 4.0, "text": "dunia", "words": []},
            ]}, f)
        try:
            # GET
            res = await ac.get(f"/api/videos/{vid}/transcript/segments", headers=headers)
            assert res.status_code == 200, res.text
            assert res.json()["count"] == 2
            assert res.json()["language"] == "id"

            # PUT validasi: end <= start → 422
            res_bad = await ac.put(f"/api/videos/{vid}/transcript/segments",
                                   json={"segments": [{"start": 5.0, "end": 5.0, "text": "x"}]},
                                   headers=headers)
            assert res_bad.status_code == 422

            # PUT: ubah teks segmen 1 (words harus dibersihkan), segmen 2 sama (words kept)
            res_put = await ac.put(f"/api/videos/{vid}/transcript/segments", headers=headers, json={"segments": [
                {"start": 0.0, "end": 2.0, "text": "halo semua"},
                {"start": 2.0, "end": 4.0, "text": "dunia"},
            ]})
            assert res_put.status_code == 200, res_put.text
            assert res_put.json()["count"] == 2
            with open(t_path, encoding="utf-8") as f:
                saved = json.load(f)
            assert saved["segments"][0]["words"] == []
            assert saved["segments"][0]["text"] == "halo semua"
            assert saved["full_text"] == "halo semua dunia"

            # 404 video tak ada
            res404 = await ac.get("/api/videos/tidak-ada/transcript/segments", headers=headers)
            assert res404.status_code == 404
        finally:
            await ac.delete(f"/api/videos/{vid}", headers=headers)
            if os.path.exists(t_path):
                os.remove(t_path)


@pytest.mark.asyncio
async def test_retranscribe_guards_and_queue():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        token = await _token(ac)
        headers = {"Authorization": f"Bearer {token}"}

        res404 = await ac.post("/api/videos/tidak-ada/retranscribe", json={}, headers=headers)
        assert res404.status_code == 404

        vid = uuid.uuid4().hex
        async with db_module.AsyncSessionLocal() as session:
            session.add(SourceVideo(
                id=vid, filename="v.mp4", original_name="V",
                local_file_path="uploads/v.mp4", file_size_bytes=10,
                duration_seconds=60.0, status="READY",
            ))
            await session.commit()
        try:
            # Tanpa berkas audio → 404
            res_noaudio = await ac.post(f"/api/videos/{vid}/retranscribe", json={}, headers=headers)
            assert res_noaudio.status_code == 404

            # Sediakan audio dummy → antre OK dengan bahasa
            a_path = os.path.abspath(os.path.join("storage", f"audio/{vid}.wav"))
            os.makedirs(os.path.dirname(a_path), exist_ok=True)
            with open(a_path, "wb") as f:
                f.write(b"\x00" * 64)
            res = await ac.post(f"/api/videos/{vid}/retranscribe",
                                json={"language": "en"}, headers=headers)
            assert res.status_code == 202, res.text
            assert res.json()["language"] == "en"
            if os.path.exists(a_path):
                os.remove(a_path)
        finally:
            await ac.delete(f"/api/videos/{vid}", headers=headers)
