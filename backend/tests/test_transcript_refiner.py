import pytest
from unittest.mock import patch, AsyncMock
from app.services.llm_service import _align_refined_words, refine_transcript_with_llm


def test_align_refined_words_same_length():
    old_words = [
        {"word": "AD", "start": 1.0, "end": 1.4, "probability": 0.9},
        {"word": "DHoha", "start": 1.5, "end": 2.0, "probability": 0.85},
    ]
    new_text = "Ad Dhuha"
    aligned = _align_refined_words(old_words, new_text, seg_start=1.0, seg_end=2.0)
    assert len(aligned) == 2
    assert aligned[0]["word"] == "Ad"
    assert aligned[0]["start"] == 1.0
    assert aligned[0]["end"] == 1.4
    assert aligned[1]["word"] == "Dhuha"
    assert aligned[1]["start"] == 1.5
    assert aligned[1]["end"] == 2.0


def test_align_refined_words_merged_tokens():
    # Merging "Sekali" and "-GUS" into "sekaligus"
    old_words = [
        {"word": "Sekali", "start": 10.0, "end": 10.5, "probability": 0.9},
        {"word": "-GUS", "start": 10.6, "end": 11.2, "probability": 0.8},
    ]
    new_text = "sekaligus"
    aligned = _align_refined_words(old_words, new_text, seg_start=10.0, seg_end=11.2)
    assert len(aligned) == 1
    assert aligned[0]["word"] == "sekaligus"
    assert aligned[0]["start"] >= 10.0
    assert aligned[0]["end"] <= 11.2


def test_align_refined_words_expanded_tokens():
    # Expanding 1 glitch word to 2 words
    old_words = [
        {"word": "Al-ALvinsi", "start": 5.0, "end": 6.5, "probability": 0.7},
    ]
    new_text = "Surah Al-Insyirah"
    aligned = _align_refined_words(old_words, new_text, seg_start=5.0, seg_end=6.5)
    assert len(aligned) == 2
    assert aligned[0]["word"] == "Surah"
    assert aligned[1]["word"] == "Al-Insyirah"
    assert aligned[0]["start"] >= 5.0
    assert aligned[-1]["end"] <= 6.5
    assert aligned[0]["end"] <= aligned[1]["start"] + 0.05


def test_align_refined_words_empty_old_words():
    aligned = _align_refined_words([], "bismillahirrahmanirrahim", seg_start=0.0, seg_end=2.5)
    assert len(aligned) == 1
    assert aligned[0]["word"] == "bismillahirrahmanirrahim"
    assert aligned[0]["start"] == 0.0
    assert aligned[0]["end"] == 2.5


@pytest.mark.asyncio
async def test_refine_transcript_with_llm_success():
    segments = [
        {
            "id": 0,
            "start": 1.0,
            "end": 2.5,
            "text": "bacaan surah AD DHoha",
            "words": [
                {"word": "bacaan", "start": 1.0, "end": 1.3},
                {"word": "surah", "start": 1.3, "end": 1.6},
                {"word": "AD", "start": 1.6, "end": 1.9},
                {"word": "DHoha", "start": 1.9, "end": 2.5},
            ]
        },
        {
            "id": 1,
            "start": 3.0,
            "end": 4.5,
            "text": "Sekali -GUS dan Al ALvinsi",
            "words": [
                {"word": "Sekali", "start": 3.0, "end": 3.4},
                {"word": "-GUS", "start": 3.4, "end": 3.8},
                {"word": "dan", "start": 3.8, "end": 4.0},
                {"word": "Al", "start": 4.0, "end": 4.2},
                {"word": "ALvinsi", "start": 4.2, "end": 4.5},
            ]
        }
    ]

    mock_llm_reply = (
        '```json\n'
        '[\n'
        '  {"id": 0, "text": "bacaan surah Ad-Dhuha"},\n'
        '  {"id": 1, "text": "sekaligus dan Al-Insyirah"}\n'
        ']\n'
        '```'
    )

    with patch("app.services.llm_service._post_chat", new=AsyncMock(return_value=mock_llm_reply)):
        refined = await refine_transcript_with_llm(
            segments=segments,
            video_title="Kajian Tafsir Surah Ad-Dhuha dan Al-Insyirah",
            llm_base_url="https://api.deepseek.com",
            llm_api_key="test-key",
            llm_model="deepseek-flash",
        )

        assert len(refined) == 2
        assert refined[0]["text"] == "bacaan surah Ad-Dhuha"
        assert [w["word"] for w in refined[0]["words"]] == ["bacaan", "surah", "Ad-Dhuha"]
        assert refined[1]["text"] == "sekaligus dan Al-Insyirah"
        assert [w["word"] for w in refined[1]["words"]] == ["sekaligus", "dan", "Al-Insyirah"]


@pytest.mark.asyncio
async def test_refine_transcript_noop_when_no_llm():
    segments = [{"id": 0, "start": 1.0, "end": 2.0, "text": "test"}]
    res = await refine_transcript_with_llm(segments=segments, video_title="Test", llm_base_url=None)
    assert res == segments
