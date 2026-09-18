import json
import pytest
import app.services.llm_service as llm


def _segs(n, start=0.0, step=60.0):
    return [{"start": start + i * step, "end": start + (i + 1) * step, "text": f"kalimat nomor {i} tentang hal penting"}
            for i in range(n)]


def test_smart_chunk_short_video_single():
    segs = _segs(20)
    chunks = llm.smart_chunk_transcript(segs, 1500.0)
    assert len(chunks) == 1
    assert chunks[0] == segs


def test_smart_chunk_mid_video_three():
    segs = _segs(90)
    chunks = llm.smart_chunk_transcript(segs, 3600.0)
    assert len(chunks) == 3
    # Batas di batas segmen: gabungan kembali utuh & berurutan
    assert [s for c in chunks for s in c] == segs


def test_smart_chunk_long_video_five():
    segs = _segs(100)
    chunks = llm.smart_chunk_transcript(segs, 7200.0)
    assert len(chunks) == 5
    assert [s for c in chunks for s in c] == segs


def test_smart_chunk_empty():
    assert llm.smart_chunk_transcript([], 3600.0) == []


@pytest.mark.asyncio
async def test_chunked_merges_and_dedupes(monkeypatch):
    segs = _segs(90)  # 90 mnt → 3 chunk

    def clip_json(title, start, end, score):
        return json.dumps({"video_type": "umum", "clips": [
            {"title": title, "start_time_seconds": start, "end_time_seconds": end,
             "hook_score": score, "virality_reason": "ok"}]})

    responses = [
        clip_json("Awal", 0.0, 40.0, 80),
        clip_json("Tengah", 1800.0, 1840.0, 85),
        # Duplikat >50% overlap dengan Tengah → harus tersupresi
        clip_json("Tengah Copy", 1805.0, 1845.0, 70),
    ]
    calls = []

    async def fake_post(base_url, api_key, model, messages, temperature, timeout_seconds=45.0):
        calls.append(messages)
        return responses[min(len(calls) - 1, len(responses) - 1)]

    monkeypatch.setattr(llm, "_post_chat", fake_post)
    out = await llm.extract_highlights_chunked(
        segments=segs, video_duration=5400.0, video_title="T",
        llm_base_url="http://x/v1",
    )
    assert len(calls) == 3
    titles = [c["title"] for c in out]
    assert "Awal" in titles and "Tengah" in titles
    assert "Tengah Copy" not in titles
    assert len(out) <= 10


@pytest.mark.asyncio
async def test_chunked_all_fail_falls_back_to_heuristic(monkeypatch):
    async def fail_post(*a, **k):
        raise ConnectionError("down")

    monkeypatch.setattr(llm, "_post_chat", fail_post)
    out = await llm.extract_highlights_chunked(
        segments=_segs(90), video_duration=5400.0, llm_base_url="http://x/v1",
    )
    assert len(out) >= 1


@pytest.mark.asyncio
async def test_chunked_short_delegates_to_single(monkeypatch):
    called = {}

    async def fake_single(**kwargs):
        called["yes"] = True
        return llm.HighlightsList([], video_type="umum")

    monkeypatch.setattr(llm, "extract_highlights_with_llm", fake_single)
    await llm.extract_highlights_chunked(
        segments=_segs(10), video_duration=600.0, llm_base_url="http://x/v1",
    )
    assert called.get("yes") is True
