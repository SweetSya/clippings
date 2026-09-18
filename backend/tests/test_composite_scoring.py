from app.services.llm_service import (
    compute_composite_score,
    compute_speech_rate_score,
    compute_keyword_density_score,
    check_hook_position_score,
    validate_and_filter_candidates,
)


def _segs():
    # 60 detik, 1 kata/detik; kata kunci di detik 10-12 ("gratis", "rahasia")
    segments = []
    filler = ["saya", "dan", "besok", "kita", "semua"]
    for i in range(60):
        if 10 <= i < 13:
            text = ["gratis", "rahasia", "uang"][i - 10]
        else:
            text = filler[i % len(filler)]
        segments.append({"start": float(i), "end": float(i + 1), "text": text})
    return segments


def test_composite_weights_math():
    # Tanpa segmen: speech 50, keyword 0, hook MISS 30 → 100*.4 + 50*.2 + 0 + 30*.2 = 56
    res = compute_composite_score(100, 0.0, 10.0, [], 1.0)
    assert res["composite_score"] == 56
    assert res["speech_rate"] == 0.0
    assert res["keyword_density"] == 0.0


def test_hook_position_hit_and_miss():
    segs = _segs()
    assert check_hook_position_score(10.0, segs) == 100.0
    assert check_hook_position_score(30.0, segs) == 30.0


def test_keyword_density_and_speech_rate():
    segs = _segs()
    kw_score, density = compute_keyword_density_score(10.0, 13.0, segs)
    assert density == 1.0
    assert kw_score == 100.0
    rate_score, rate = compute_speech_rate_score(10.0, 13.0, segs, 1.0)
    assert rate == 1.0
    assert rate_score == 50.0


def test_validate_rescores_and_sorts_by_composite():
    segs = _segs()
    cands = [
        {"title": "Biasa", "start_time_seconds": 30.0, "end_time_seconds": 45.0,
         "hook_score": 90, "virality_reason": "ok"},
        {"title": "Emosional", "start_time_seconds": 9.0, "end_time_seconds": 24.0,
         "hook_score": 80, "virality_reason": "ok"},
    ]
    out = validate_and_filter_candidates(cands, 60.0, 10.0, 60.0, segments=segs)
    assert len(out) == 2
    assert all("composite_score" in c and "speech_rate" in c and "keyword_density" in c for c in out)
    # Klip keyword-dense menyalip walau skor LLM lebih rendah
    assert out[0]["title"] == "Emosional"
    assert out[0]["composite_score"] > out[1]["composite_score"]
    assert out == sorted(out, key=lambda c: c["composite_score"], reverse=True)


def test_validate_without_segments_backward_compat():
    cands = [
        {"title": "A", "start_time_seconds": 0.0, "end_time_seconds": 20.0,
         "hook_score": 70, "virality_reason": "ok"},
    ]
    out = validate_and_filter_candidates(cands, 60.0, 10.0, 60.0)
    assert out[0]["composite_score"] == 70
    assert out[0]["speech_rate"] == 0.0
    assert out[0]["keyword_density"] == 0.0
