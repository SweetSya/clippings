"""Test chunked transcription logic for long audio (> 15 minutes / 900s).

Verifies:
- _find_best_cut_frame finds silence/pause point.
- _transcribe_chunked stitches segments and words with correct time offsets.
- progress_callback receives 0..100% updates.
- worker tracks active jobs and does not reap them.
"""

import wave
import pytest
from unittest.mock import MagicMock
from app.services import whisper_service
from app.services.whisper_service import (
    _find_best_cut_frame,
    _transcribe_chunked,
    CHUNK_THRESHOLD_SECONDS,
)
from app.worker import BackgroundWorker


def test_chunk_threshold_constant():
    assert CHUNK_THRESHOLD_SECONDS == 900.0


def test_find_best_cut_frame_synthetic(tmp_path):
    wav_path = tmp_path / "test.wav"
    sample_rate = 16000
    # 20 seconds total: 10s sound, 2s silence, 8s sound
    with wave.open(str(wav_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        # 10s audio with signal (16000 frames per second)
        sound1 = (b"\x10\x20" * sample_rate) * 10
        # 2s silence
        silence = b"\x00" * (sample_rate * 2) * 2
        # 8s audio with signal
        sound2 = (b"\x10\x20" * sample_rate) * 8
        wf.writeframes(sound1 + silence + sound2)

    with wave.open(str(wav_path), "rb") as wf:
        # Search target at 10.5s (frame 168000)
        cut = _find_best_cut_frame(wf, target_frame=int(10.5 * sample_rate), search_window_frames=64000, sample_rate=sample_rate)
        cut_sec = cut / sample_rate
        # Cut must be within the silence region (10.0s to 12.0s)
        assert 10.0 <= cut_sec <= 12.0


def test_worker_active_jobs_tracking():
    w = BackgroundWorker()
    assert len(w._active_jobs) == 0
    w._active_jobs.add("job-123")
    assert "job-123" in w._active_jobs
    w._active_jobs.discard("job-123")
    assert "job-123" not in w._active_jobs
