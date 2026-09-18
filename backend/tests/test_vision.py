"""Phase 4 — 2.1: vision-aware clipping."""

import os
import pytest
import app.services.vision_service as vision
from app.services.llm_service import validate_and_filter_candidates


def test_build_vision_boost_pure():
    assert vision.build_vision_boost([]) == {}
    assert vision.build_vision_boost(None) == {}
    boost = vision.build_vision_boost([
        {"timestamp": 10.0, "visual_score": 80, "description": "a"},
        {"timestamp": 10.0, "visual_score": 95, "description": "b"},
        {"timestamp": "rusak", "visual_score": 90},
        {"timestamp": -5.0, "visual_score": 90},
    ])
    assert boost == {10.0: 95}


def test_batch_frames_to_grid_shape():
    import cv2
    import numpy as np
    import tempfile
    tmp = tempfile.mkdtemp()
    try:
        paths = []
        for i in range(5):
            p = os.path.join(tmp, f"f{i:03d}.jpg")
            cv2.imwrite(p, (np.ones((90, 160, 3)) * (i * 40 % 255)).astype("uint8"))
            paths.append((p, float(i * 2)))
        grids = vision.batch_frames_to_grid(paths)
        assert len(grids) == 1
        grid, stamps = grids[0]
        assert stamps == [0.0, 2.0, 4.0, 6.0, 8.0]
        assert grid.shape[0] > 0 and grid.shape[1] > 0
        assert vision._grid_to_data_uri(grid).startswith("data:image/jpeg;base64,")
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)


def test_validate_vision_boost_reranks():
    segs = [{"start": float(i), "end": float(i + 1), "text": "kata biasa saja"} for i in range(60)]
    cands = [
        {"title": "Awal", "start_time_seconds": 0.0, "end_time_seconds": 15.0,
         "hook_score": 90, "virality_reason": "ok"},
        {"title": "Visual", "start_time_seconds": 30.0, "end_time_seconds": 45.0,
         "hook_score": 70, "virality_reason": "ok"},
    ]
    plain = validate_and_filter_candidates(cands, 60.0, 10.0, 60.0, segments=segs)
    assert plain[0]["title"] == "Awal"
    boosted = validate_and_filter_candidates(
        cands, 60.0, 10.0, 60.0, segments=segs,
        vision_boost={35.0: 100.0}, vision_weight=0.3,
    )
    assert boosted[0]["title"] == "Visual"
    assert boosted[0]["composite_score"] <= 100


def test_validate_vision_boost_off_identical():
    segs = [{"start": 0.0, "end": 10.0, "text": "halo dunia"}]
    cands = [{"title": "A", "start_time_seconds": 0.0, "end_time_seconds": 10.0,
              "hook_score": 80, "virality_reason": "ok"}]
    a = validate_and_filter_candidates(cands, 60.0, 5.0, 60.0, segments=segs)
    b = validate_and_filter_candidates(cands, 60.0, 5.0, 60.0, segments=segs,
                                       vision_boost=None, vision_weight=0.3)
    assert a[0]["composite_score"] == b[0]["composite_score"]


@pytest.mark.asyncio
async def test_extract_visual_highlights_no_config():
    assert await vision.extract_visual_highlights("/tak/ada.mp4", 60.0, None) == []
    assert await vision.extract_visual_highlights("", 60.0, "http://x") == []
