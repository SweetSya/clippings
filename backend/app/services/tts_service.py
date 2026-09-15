import os
import edge_tts
from typing import Dict, Any, List
from app.utils.subprocess_utils import run_with_timeout

POPULAR_VOICES = [
    {"id": "id-ID-ArdiNeural", "name": "Ardi (Indonesian - Male)", "lang": "id-ID", "gender": "Male"},
    {"id": "id-ID-GadisNeural", "name": "Gadis (Indonesian - Female)", "lang": "id-ID", "gender": "Female"},
    {"id": "en-US-ChristopherNeural", "name": "Christopher (English - Male)", "lang": "en-US", "gender": "Male"},
    {"id": "en-US-JennyNeural", "name": "Jenny (English - Female)", "lang": "en-US", "gender": "Female"},
    {"id": "en-US-GuyNeural", "name": "Guy (English - Male)", "lang": "en-US", "gender": "Male"},
    {"id": "en-US-AriaNeural", "name": "Aria (English - Female)", "lang": "en-US", "gender": "Female"},
]

async def generate_speech(
    text: str,
    output_path: str,
    voice: str = "id-ID-ArdiNeural",
    rate: str = "+0%",
    pitch: str = "+0Hz"
) -> float:
    """
    Generate speech audio file from text using edge-tts.
    Returns duration of generated audio in seconds.
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    communicate = edge_tts.Communicate(text=text, voice=voice, rate=rate, pitch=pitch)
    await communicate.save(output_path)

    # Inspect duration with ffprobe
    cmd = [
        "ffprobe", "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        output_path
    ]
    rc, stdout, _ = await run_with_timeout(cmd, timeout_seconds=15.0)
    duration = 0.0
    if rc == 0:
        import json
        data = json.loads(stdout)
        duration = float(data.get("format", {}).get("duration", 0.0))
    return duration

def get_available_voices() -> List[Dict[str, str]]:
    return POPULAR_VOICES
