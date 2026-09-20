import json
import logging
import os
import asyncio
import tempfile
import wave
from typing import Dict, Any, List, Optional
from app.config import settings

logger = logging.getLogger(__name__)

CHUNK_THRESHOLD_SECONDS = 900.0  # 15 menit: file lebih panjang dari ini otomatis di-chunk
TARGET_CHUNK_SECONDS = 600.0     # 10 menit per chunk


def _find_best_cut_frame(wf: wave.Wave_read, target_frame: int, search_window_frames: int = 240000, sample_rate: int = 16000) -> int:
    """Cari titik potong audio di jeda hening terdekat dalam jendela pencarian (default ±7.5 detik)."""
    import array
    total_frames = wf.getnframes()
    if target_frame >= total_frames:
        return total_frames

    half_window = search_window_frames // 2
    start_search = max(0, target_frame - half_window)
    end_search = min(total_frames, target_frame + half_window)

    try:
        wf.setpos(start_search)
        frames_to_read = end_search - start_search
        raw_data = wf.readframes(frames_to_read)
        samples = array.array("h", raw_data)

        sub_len = int(0.3 * sample_rate)
        step = int(0.1 * sample_rate)
        best_offset = half_window
        min_energy = float("inf")

        for i in range(0, len(samples) - sub_len, step):
            chunk = samples[i:i + sub_len]
            energy = sum(s * s for s in chunk) / sub_len
            if energy < min_energy:
                min_energy = energy
                best_offset = i + sub_len // 2
                if energy < 50:  # Keheningan mutlak
                    break

        return start_search + best_offset
    except Exception:
        return target_frame


def _transcribe_chunked(
    audio_path: str,
    model_name: str,
    device: str,
    compute_type: str,
    language: str = None,
    initial_prompt: str = None,
    progress_callback=None,
) -> Dict[str, Any]:
    """Transkripsi audio panjang secara bertahap (per-chunk ~10m) agar RAM stabil < 150MB."""
    from faster_whisper import WhisperModel
    import gc

    sample_rate = 16000
    target_frames = int(TARGET_CHUNK_SECONDS * sample_rate)

    with wave.open(audio_path, "rb") as wf:
        total_frames = wf.getnframes()
        params = wf.getparams()

        cuts = [0]
        cur = target_frames
        while cur < total_frames:
            cut = _find_best_cut_frame(wf, cur, sample_rate=sample_rate)
            if cut <= cuts[-1] + 60 * sample_rate:
                cut = cuts[-1] + target_frames
            if cut >= total_frames:
                break
            cuts.append(cut)
            cur = cut + target_frames
        cuts.append(total_frames)

    total_chunks = len(cuts) - 1
    total_dur_sec = total_frames / sample_rate
    logger.info("Audio panjang (%.1f detik) dibagi menjadi %d chunk untuk mencegah OOM.", total_dur_sec, total_chunks)

    model = WhisperModel(model_name, device=device, compute_type=compute_type)

    all_parts: List[str] = []
    all_segments: List[Dict[str, Any]] = []
    detected_lang = language
    detected_prob = 1.0
    seg_counter = 0

    for i in range(total_chunks):
        start_frame = cuts[i]
        end_frame = cuts[i + 1]
        offset_sec = start_frame / sample_rate

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_chunk_path = tmp.name

        try:
            with wave.open(audio_path, "rb") as wf:
                wf.setpos(start_frame)
                frames = wf.readframes(end_frame - start_frame)
            with wave.open(tmp_chunk_path, "wb") as out_wf:
                out_wf.setparams(params)
                out_wf.writeframes(frames)
            del frames

            segments_gen, info = model.transcribe(
                tmp_chunk_path,
                word_timestamps=True,
                vad_filter=True,
                language=detected_lang,
                initial_prompt=initial_prompt,
            )

            if detected_lang is None and info.language:
                detected_lang = info.language
                detected_prob = round(info.language_probability, 2)

            for seg in segments_gen:
                seg_text = seg.text.strip()
                if seg_text:
                    all_parts.append(seg_text)
                seg_words = []
                if seg.words:
                    for w in seg.words:
                        seg_words.append({
                            "word": w.word.strip(),
                            "start": round(w.start + offset_sec, 2),
                            "end": round(w.end + offset_sec, 2),
                            "probability": round(w.probability, 2)
                        })
                all_segments.append({
                    "id": seg_counter,
                    "seek": int(offset_sec * 100) + seg.seek,
                    "start": round(seg.start + offset_sec, 2),
                    "end": round(seg.end + offset_sec, 2),
                    "text": seg_text,
                    "words": seg_words
                })
                seg_counter += 1

            pct = int((i + 1) / total_chunks * 100)
            if progress_callback:
                try:
                    progress_callback(pct)
                except Exception:
                    pass

        finally:
            if os.path.exists(tmp_chunk_path):
                try:
                    os.remove(tmp_chunk_path)
                except OSError:
                    pass
            gc.collect()

    return {
        "language": detected_lang or "id",
        "language_probability": detected_prob,
        "duration": round(total_dur_sec, 2),
        "full_text": " ".join(all_parts),
        "segments": all_segments
    }


def _transcribe_worker(audio_path: str, model_name: str, device: str, compute_type: str,
                       language: str = None, initial_prompt: str = None, progress_callback=None) -> Dict[str, Any]:
    # Jika audio berdurasi panjang (> 15 menit), transkripsi bertahap per chunk agar RAM tetap < 150MB
    if estimate_wav_seconds(audio_path) > CHUNK_THRESHOLD_SECONDS:
        try:
            return _transcribe_chunked(
                audio_path, model_name, device, compute_type, language, initial_prompt, progress_callback
            )
        except Exception as exc:
            logger.warning("Chunked transcribe gagal, fallback ke unchunked: %s", exc)

    from faster_whisper import WhisperModel

    model = WhisperModel(
        model_name,
        device=device,
        compute_type=compute_type
    )

    segments_gen, info = model.transcribe(
        audio_path,
        word_timestamps=True,
        vad_filter=True,
        language=language,  # None = auto-detect (satu bahasa dominan per file)
        initial_prompt=initial_prompt,
    )

    full_text_parts: List[str] = []
    formatted_segments: List[Dict[str, Any]] = []

    for seg in segments_gen:
        full_text_parts.append(seg.text.strip())
        seg_words = []
        if seg.words:
            for w in seg.words:
                seg_words.append({
                    "word": w.word.strip(),
                    "start": round(w.start, 2),
                    "end": round(w.end, 2),
                    "probability": round(w.probability, 2)
                })
        formatted_segments.append({
            "id": seg.id,
            "seek": seg.seek,
            "start": round(seg.start, 2),
            "end": round(seg.end, 2),
            "text": seg.text.strip(),
            "words": seg_words
        })

    return {
        "language": info.language,
        "language_probability": round(info.language_probability, 2),
        "duration": round(info.duration, 2),
        "full_text": " ".join(full_text_parts),
        "segments": formatted_segments
    }

async def transcribe_audio(
    audio_path: str,
    output_json_path: str,
    model_name: str = None,
    device: str = None,
    compute_type: str = None,
    timeout_seconds: Optional[float] = None,
    language: str = None,
    initial_prompt: Optional[str] = None,
    progress_callback: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Asynchronously run faster-whisper transcription and save transcript JSON.
    timeout_seconds membatasi total waktu (termasuk load model); TimeoutError
    bila macet — thread yatim dibiarkan selesai sendiri, sesi worker bebas.
    """
    m_name = model_name or settings.WHISPER_MODEL
    m_device = device or settings.WHISPER_DEVICE
    m_compute = compute_type or settings.WHISPER_COMPUTE_TYPE

    loop = asyncio.get_running_loop()

    def sync_cb(pct: int):
        if progress_callback:
            try:
                if asyncio.iscoroutinefunction(progress_callback):
                    asyncio.run_coroutine_threadsafe(progress_callback(pct), loop)
                else:
                    loop.call_soon_threadsafe(progress_callback, pct)
            except Exception:
                pass

    import inspect
    sig = inspect.signature(_transcribe_worker)
    worker_kwargs = {}
    if "initial_prompt" in sig.parameters and initial_prompt:
        worker_kwargs["initial_prompt"] = initial_prompt
    if "progress_callback" in sig.parameters and progress_callback:
        worker_kwargs["progress_callback"] = sync_cb

    # Run CPU/GPU bound whisper in threadpool
    coro = asyncio.to_thread(
        _transcribe_worker,
        audio_path,
        m_name,
        m_device,
        m_compute,
        language,
        **worker_kwargs
    )
    if timeout_seconds and timeout_seconds > 0:
        try:
            result = await asyncio.wait_for(coro, timeout=timeout_seconds)
        except asyncio.TimeoutError:
            raise TimeoutError(
                f"Transkripsi melebihi batas {timeout_seconds:.0f} detik "
                f"({audio_path}). Coba model lebih kecil atau audio lebih pendek."
            )
    else:
        result = await coro

    # Save to JSON file on disk
    os.makedirs(os.path.dirname(output_json_path), exist_ok=True)
    with open(output_json_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    return result


def estimate_wav_seconds(abs_path: str) -> float:
    """Estimasi durasi WAV 16kHz mono 16-bit dari ukuran file. 0.0 bila gagal."""
    try:
        return max(0.0, os.path.getsize(abs_path) / 32000.0)
    except OSError:
        return 0.0


def compute_transcribe_timeout(audio_path: str) -> float:
    """Batas wajar = max(min, estimasi_durasi * faktor). Pure dari config."""
    factor = float(getattr(settings, "WHISPER_TIMEOUT_FACTOR", 6.0) or 6.0)
    minimum = float(getattr(settings, "WHISPER_TIMEOUT_MIN_SECONDS", 1800.0) or 1800.0)
    return max(minimum, estimate_wav_seconds(audio_path) * factor)


async def prewarm_transcription() -> bool:
    """
    Pemanasan sekali saat startup: load model + transkripsi 1 detik hening
    (sekaligus memicu unduhan model VAD bila belum ada). Tak pernah raise.
    """
    try:
        with tempfile.TemporaryDirectory(prefix="whisper_prewarm_") as tmp:
            wav_path = os.path.join(tmp, "silence.wav")
            with wave.open(wav_path, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(16000)
                wf.writeframes(b"\x00" * 32000)
            await transcribe_audio(wav_path, os.path.join(tmp, "out.json"), timeout_seconds=600.0)
        logger.info("Whisper prewarm OK (model %s).", settings.WHISPER_MODEL)
        return True
    except Exception as exc:
        logger.warning("Whisper prewarm gagal (transkripsi nanti mungkin lambat/gagal): %s", exc)
        return False
