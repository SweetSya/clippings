import json
import os
import asyncio
from typing import Dict, Any, List
from app.config import settings

def _transcribe_worker(audio_path: str, model_name: str, device: str, compute_type: str) -> Dict[str, Any]:
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
        language=None
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
    compute_type: str = None
) -> Dict[str, Any]:
    """
    Asynchronously run faster-whisper transcription and save transcript JSON.
    """
    m_name = model_name or settings.WHISPER_MODEL
    m_device = device or settings.WHISPER_DEVICE
    m_compute = compute_type or settings.WHISPER_COMPUTE_TYPE

    # Run CPU/GPU bound whisper in threadpool
    result = await asyncio.to_thread(
        _transcribe_worker,
        audio_path,
        m_name,
        m_device,
        m_compute
    )

    # Save to JSON file on disk
    os.makedirs(os.path.dirname(output_json_path), exist_ok=True)
    with open(output_json_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    return result
