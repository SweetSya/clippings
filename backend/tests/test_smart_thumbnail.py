import os
import subprocess
import pytest
from app.services.ffmpeg_service import (
    score_thumbnail_frame,
    select_best_thumbnail,
    generate_thumbnail,
)

SAMPLE = "storage/test_smartthumb_src.mp4"


@pytest.fixture(scope="module", autouse=True)
def _sample_video():
    os.makedirs("storage", exist_ok=True)
    if not os.path.exists(SAMPLE):
        subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=duration=12:size=640x360:rate=30",
             "-c:v", "libx264", "-pix_fmt", "yuv420p", SAMPLE],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    yield


def test_score_thumbnail_frame_math():
    # Wajah penuh + tajam maksimal → 1.0
    assert score_thumbnail_frame(1.0, 100.0, 0.0, 100.0) == 1.0
    # Tanpa wajah + tajam minimal → 0.0
    assert score_thumbnail_frame(0.0, 0.0, 0.0, 100.0) == 0.0
    # Wajah 0.5 + tajam tengah → 0.5
    assert score_thumbnail_frame(0.5, 50.0, 0.0, 100.0) == 0.5
    # Input rusak → fallback 0 wajah
    assert score_thumbnail_frame("x", 50.0, 0.0, 100.0) == 0.2


@pytest.mark.asyncio
async def test_select_best_thumbnail_real_video():
    best = await select_best_thumbnail(SAMPLE, seek_seconds=5.0, n_candidates=6)
    try:
        assert best is not None
        assert os.path.exists(best)
        assert os.path.getsize(best) > 0
    finally:
        if best and os.path.exists(best):
            os.remove(best)


@pytest.mark.asyncio
async def test_generate_thumbnail_smart_and_fallback():
    out = "storage/test_smartthumb_out.jpg"
    try:
        ok = await generate_thumbnail(SAMPLE, out, seek_seconds=5.0, smart=True)
        assert ok and os.path.exists(out)
    finally:
        if os.path.exists(out):
            os.remove(out)

    # Video tak ada → tetap raise (perilaku lama terjaga)
    with pytest.raises(RuntimeError):
        await generate_thumbnail("storage/tidak_ada_xyz.mp4", out, seek_seconds=1.0, smart=True)
