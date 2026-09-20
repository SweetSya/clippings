import os
import edge_tts
from typing import Dict, Any, List
from app.utils.subprocess_utils import run_with_timeout

POPULAR_VOICES = [
    {"id": "id-ID-ArdiNeural", "name": "Ardi (Indonesia - Pria)", "lang": "id-ID", "gender": "Male", "description": "Berwibawa & Alami"},
    {"id": "id-ID-GadisNeural", "name": "Gadis (Indonesia - Wanita)", "lang": "id-ID", "gender": "Female", "description": "Jelas, Ramah & Ceria"},
    {"id": "jv-ID-DimasNeural", "name": "Dimas (Jawa/ID - Pria)", "lang": "jv-ID", "gender": "Male", "description": "Lokal Jawa Hangat"},
    {"id": "jv-ID-SitiNeural", "name": "Siti (Jawa/ID - Wanita)", "lang": "jv-ID", "gender": "Female", "description": "Lokal Jawa Lembut"},
    {"id": "su-ID-JajangNeural", "name": "Jajang (Sunda/ID - Pria)", "lang": "su-ID", "gender": "Male", "description": "Lokal Sunda Luwes"},
    {"id": "su-ID-TutiNeural", "name": "Tuti (Sunda/ID - Wanita)", "lang": "su-ID", "gender": "Female", "description": "Lokal Sunda Manis"},
    {"id": "ms-MY-OsmanNeural", "name": "Osman (Melayu - Pria)", "lang": "ms-MY", "gender": "Male", "description": "Melayu Berwibawa"},
    {"id": "ms-MY-YasminNeural", "name": "Yasmin (Melayu - Wanita)", "lang": "ms-MY", "gender": "Female", "description": "Melayu Lembut"},
    {"id": "en-US-ChristopherNeural", "name": "Christopher (English - Male)", "lang": "en-US", "gender": "Male", "description": "Deep Voice & Narator"},
    {"id": "en-US-JennyNeural", "name": "Jenny (English - Female)", "lang": "en-US", "gender": "Female", "description": "Warm & Conversational"},
    {"id": "en-US-GuyNeural", "name": "Guy (English - Male)", "lang": "en-US", "gender": "Male", "description": "Energetic & Casual"},
    {"id": "en-US-AriaNeural", "name": "Aria (English - Female)", "lang": "en-US", "gender": "Female", "description": "Professional & Confident"},
    {"id": "en-US-AndrewMultilingualNeural", "name": "Andrew (Multilingual - Male)", "lang": "en-US", "gender": "Male", "description": "Modern & Authentic"},
    {"id": "en-US-AvaMultilingualNeural", "name": "Ava (Multilingual - Female)", "lang": "en-US", "gender": "Female", "description": "Expressive & Pleasant"},
    {"id": "en-US-BrianMultilingualNeural", "name": "Brian (Multilingual - Male)", "lang": "en-US", "gender": "Male", "description": "Deep & Approachable"},
    {"id": "en-US-EmmaMultilingualNeural", "name": "Emma (Multilingual - Female)", "lang": "en-US", "gender": "Female", "description": "Clear & Cheerful"},
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
