import os
import json
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

ASSETS_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "video_types.json")

_CACHED_VIDEO_TYPES: Optional[List[Dict[str, Any]]] = None

def get_all_video_types() -> List[Dict[str, Any]]:
    """
    Get the full list of video genre taxonomy profiles.
    """
    global _CACHED_VIDEO_TYPES
    if _CACHED_VIDEO_TYPES is not None:
        return _CACHED_VIDEO_TYPES

    if os.path.exists(ASSETS_PATH):
        try:
            with open(ASSETS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                _CACHED_VIDEO_TYPES = data.get("video_types", [])
                return _CACHED_VIDEO_TYPES
        except Exception as e:
            logger.error("Failed to load video_types.json: %s", e)

    # Fallback minimal
    return [
        {
            "id": "umum",
            "name": "Umum / General Viral",
            "description": "Fokus pada momen paling menarik, berenergi tinggi, dan penuh informasi inti.",
            "hook_guidelines": "Awali dengan hook kuat 3 detik pertama.",
            "recommended_preset_id": "preset_tiktok_bold"
        }
    ]

def get_video_type_by_id(type_id: str) -> Optional[Dict[str, Any]]:
    for vt in get_all_video_types():
        if vt.get("id") == type_id:
            return vt
    return None

def build_video_types_prompt_guide() -> str:
    """
    Build a concise prompt guide formatted for the LLM to categorize video and pick relevant highlights.
    """
    types = get_all_video_types()
    lines = []
    for t in types:
        lines.append(f"- TIPE '{t.get('id')}': {t.get('name')}")
        lines.append(f"  Panduan Kurasi: {t.get('description')}")
        lines.append(f"  Panduan Hook: {t.get('hook_guidelines')}")
        lines.append(f"  Preset Default: {t.get('recommended_preset_id')}")
    return "\n".join(lines)
