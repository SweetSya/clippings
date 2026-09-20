"""Regresi job transkripsi macet selamanya (video >1 jam, progres 0%).

- transcribe_audio wajib menerima timeout_seconds (wait_for).
- compute_transcribe_timeout wajar dari ukuran WAV.
- prewarm tak pernah raise.
"""

import asyncio
import os
import pytest
from app.services import whisper_service
from app.services.whisper_service import (
    compute_transcribe_timeout,
    estimate_wav_seconds,
    prewarm_transcription,
)


def test_estimate_wav_seconds():
    assert estimate_wav_seconds("/tak/ada.wav") == 0.0


def test_compute_transcribe_timeout_bounds(tmp_path):
    small = tmp_path / "a.wav"
    small.write_bytes(b"\x00" * 32000)  # ~1 detik
    assert compute_transcribe_timeout(str(small)) == 1800.0  # batas bawah
    big = tmp_path / "b.wav"
    with open(big, "wb") as f:
        f.seek(32000 * 7200 - 1)  # ~2 jam (sparse)
        f.write(b"\x00")
    assert compute_transcribe_timeout(str(big)) >= 7200 * 6.0


@pytest.mark.asyncio
async def test_transcribe_timeout_raises(monkeypatch, tmp_path):
    import time

    def slow_worker(*a, **k):
        time.sleep(30)

    monkeypatch.setattr(whisper_service, "_transcribe_worker", slow_worker)
    out = tmp_path / "out.json"
    with pytest.raises(TimeoutError):
        await whisper_service.transcribe_audio("/tak/ada.wav", str(out), timeout_seconds=0.2)
    assert not out.exists()


@pytest.mark.asyncio
async def test_transcribe_no_timeout_when_zero(monkeypatch, tmp_path):
    def fast_worker(*a, **k):
        return {"language": "id", "full_text": "halo", "segments": []}

    monkeypatch.setattr(whisper_service, "_transcribe_worker", fast_worker)
    out = tmp_path / "out.json"
    res = await whisper_service.transcribe_audio("/tak/ada.wav", str(out), timeout_seconds=0)
    assert res["full_text"] == "halo"
    assert out.exists()


@pytest.mark.asyncio
async def test_prewarm_never_raises(monkeypatch):
    async def boom(*a, **k):
        raise RuntimeError("model hilang")

    monkeypatch.setattr(whisper_service, "transcribe_audio", boom)
    assert await prewarm_transcription() is False
