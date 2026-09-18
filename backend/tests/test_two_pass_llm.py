import json
import pytest
import app.services.llm_service as llm


def _segs():
    return [
        {"start": 0.0, "end": 30.0, "text": "pembuka sponsor yang membosankan sekali"},
        {"start": 30.0, "end": 60.0, "text": "momen gratis rahasia yang sangat penting"},
    ]


BRIEF_JSON = json.dumps({
    "video_type": "umum",
    "theme_summary": "Video tentang tips",
    "must_avoid_topics": ["sponsor"],
    "must_include_topics": ["tips"],
    "tone": "santai",
})

CLIPS_JSON = json.dumps({
    "video_type": "umum",
    "clips": [
        {"title": "Momen Gratis", "start_time_seconds": 30.0, "end_time_seconds": 50.0,
         "hook_score": 90, "virality_reason": "kuat"},
    ],
})


@pytest.mark.asyncio
async def test_two_pass_uses_brief_in_pass2(monkeypatch):
    calls = []

    async def fake_post(base_url, api_key, model, messages, temperature, timeout_seconds=45.0):
        calls.append(messages)
        return BRIEF_JSON if len(calls) == 1 else CLIPS_JSON

    monkeypatch.setattr(llm, "_post_chat", fake_post)
    out = await llm.extract_highlights_two_pass(
        segments=_segs(), video_duration=60.0, video_title="T",
        llm_base_url="http://x/v1",
    )
    assert len(calls) == 2  # 2 panggilan: brief + klip
    assert len(out) == 1 and out[0]["title"] == "Momen Gratis"
    # Brief diteruskan sebagai system context di pass 2
    pass2_system = calls[1][0]["content"]
    assert "EDITORIAL BRIEF" in pass2_system
    assert "tips" in pass2_system


@pytest.mark.asyncio
async def test_two_pass_falls_back_to_single_pass(monkeypatch):
    async def fail_post(*a, **k):
        raise ConnectionError("down")

    single_called = {}

    async def fake_single(**kwargs):
        single_called["yes"] = True
        return llm.HighlightsList([], video_type="umum")

    monkeypatch.setattr(llm, "_post_chat", fail_post)
    monkeypatch.setattr(llm, "extract_highlights_with_llm", fake_single)
    await llm.extract_highlights_two_pass(
        segments=_segs(), video_duration=60.0, llm_base_url="http://x/v1",
    )
    assert single_called.get("yes") is True


@pytest.mark.asyncio
async def test_two_pass_no_base_url_uses_heuristic():
    out = await llm.extract_highlights_two_pass(
        segments=_segs(), video_duration=60.0, llm_base_url=None,
    )
    assert len(out) >= 1
