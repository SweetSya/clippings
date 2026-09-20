import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.services.tts_service import get_available_voices, POPULAR_VOICES
from app.database import init_db


async def get_auth_token(ac: AsyncClient) -> str:
    await init_db()
    res = await ac.post("/api/auth/setup", json={"pin": "123456"})
    if res.status_code == 201:
        return res.json()["token"]
    res_login = await ac.post("/api/auth/login", json={"pin": "123456"})
    return res_login.json()["token"]


def test_popular_voices_structure():
    voices = get_available_voices()
    assert len(voices) >= 10
    voice_ids = [v["id"] for v in voices]
    # Check Indonesian
    assert "id-ID-ArdiNeural" in voice_ids
    assert "id-ID-GadisNeural" in voice_ids
    # Check regional
    assert "jv-ID-DimasNeural" in voice_ids
    assert "su-ID-JajangNeural" in voice_ids
    # Check English
    assert "en-US-ChristopherNeural" in voice_ids
    assert "en-US-JennyNeural" in voice_ids

    for v in voices:
        assert "id" in v
        assert "name" in v
        assert "lang" in v
        assert "gender" in v
        assert "description" in v


@pytest.mark.asyncio
async def test_voices_api_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        token = await get_auth_token(ac)
        res = await ac.get("/api/tts/voices", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200
        data = res.json()
        assert isinstance(data, list)
        assert len(data) >= 10
        assert any(v["id"] == "id-ID-ArdiNeural" for v in data)
