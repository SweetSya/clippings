import io
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.database import init_db
from app.services.sfx_service import build_sfx_chain


def test_build_sfx_chain_filters():
    triggers = [
        {"abs_path": "/s/a.mp3", "start_t": 0.5, "volume": 0.8},
        {"abs_path": "/s/b.mp3", "start_t": 2.0, "volume": 1.5},
        {"abs_path": "", "start_t": 1.0, "volume": 1.0},  # skip: tanpa path
        {"abs_path": "/s/c.mp3", "start_t": "rusak", "volume": 1.0},  # skip: tak valid
    ]
    extra, chains, labels, nxt = build_sfx_chain(triggers, 1)
    assert extra == ["-i", "/s/a.mp3", "-i", "/s/b.mp3"]
    assert chains[0] == "[1:a]adelay=500|500,volume=0.8[asfx0]"
    assert chains[1] == "[2:a]adelay=2000|2000,volume=1.5[asfx1]"
    assert labels == ["[asfx0]", "[asfx1]"]
    assert nxt == 3


def test_build_sfx_chain_empty():
    assert build_sfx_chain([], 3) == ([], [], [], 3)


async def _token(ac: AsyncClient) -> str:
    await init_db()
    res = await ac.post("/api/auth/setup", json={"pin": "123456"})
    if res.status_code == 201:
        return res.json()["token"]
    res_login = await ac.post("/api/auth/login", json={"pin": "123456"})
    return res_login.json()["token"]


@pytest.mark.asyncio
async def test_sfx_crud():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        token = await _token(ac)
        headers = {"Authorization": f"Bearer {token}"}

        # List kosong awal (boleh ada sisa, minimal list ok)
        res_list = await ac.get("/api/sfx", headers=headers)
        assert res_list.status_code == 200
        assert isinstance(res_list.json(), list)

        # Upload format tak didukung → 400
        res_bad = await ac.post(
            "/api/sfx/upload",
            files={"file": ("x.txt", io.BytesIO(b"hi"), "text/plain")},
            headers=headers,
        )
        assert res_bad.status_code == 400

        # Upload mp3 palsu (probe gagal graceful, durasi 0)
        fake = b"ID3\x03\x00\x00\x00\x00\x00\x00fake sfx payload"
        res_up = await ac.post(
            "/api/sfx/upload",
            files={"file": ("ding.mp3", io.BytesIO(fake), "audio/mpeg")},
            data={"title": "Ding Test"},
            headers=headers,
        )
        assert res_up.status_code == 201
        track = res_up.json()
        assert track["title"] == "Ding Test"
        assert track["stream_url"].startswith("/api/sfx/")
        sfx_id = track["id"]

        # Stream balik isi sama
        res_stream = await ac.get(f"/api/sfx/{sfx_id}/stream", headers=headers)
        assert res_stream.status_code == 200
        assert res_stream.content == fake

        # Hapus
        res_del = await ac.delete(f"/api/sfx/{sfx_id}", headers=headers)
        assert res_del.status_code == 204
        res_gone = await ac.get(f"/api/sfx/{sfx_id}/stream", headers=headers)
        assert res_gone.status_code == 404
