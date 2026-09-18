"""Sound effect library & trigger resolution (Phase 3 — 3.2).

Trigger manual dari ClipStudio + aturan otomatis (skor hook) di-resolve jadi
daftar path absolut. Builder rantai FFmpeg murni tanpa I/O (mudah di-test).
"""

import os
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import SFXTrack
from app.services.storage_service import resolve_path

MAX_TRIGGERS = 8
AUTO_HOOK_START_T = 0.5
AUTO_HOOK_VOLUME = 0.8


def build_sfx_chain(
    triggers: List[Dict[str, object]], start_idx: int
) -> Tuple[List[str], List[str], List[str], int]:
    """
    Bangun input + filter chain FFmpeg untuk daftar trigger yang sudah ter-resolve.
    trigger: {abs_path, start_t, volume}. Return (extra_inputs, chains, labels, next_idx).
    Pure function (tanpa I/O).
    """
    extra_inputs: List[str] = []
    chains: List[str] = []
    labels: List[str] = []
    idx = int(start_idx)
    for i, trig in enumerate(triggers[:MAX_TRIGGERS]):
        try:
            path = str(trig.get("abs_path") or "")
            start_t = max(0.0, float(trig.get("start_t") or 0.0))
            volume = max(0.0, min(2.0, float(trig.get("volume", 0.8))))
        except (TypeError, ValueError, AttributeError):
            continue
        if not path:
            continue
        delay_ms = int(start_t * 1000)
        extra_inputs.extend(["-i", path])
        chains.append(f"[{idx}:a]adelay={delay_ms}|{delay_ms},volume={volume}[asfx{i}]")
        labels.append(f"[asfx{i}]")
        idx += 1
    return extra_inputs, chains, labels, idx


async def resolve_sfx_triggers(
    db: AsyncSession,
    manual: Optional[List[object]],
    auto_sfx_id: Optional[str] = None,
    auto_enabled: bool = False,
    auto_score: float = 0.0,
    auto_threshold: float = 90.0,
) -> List[Dict[str, object]]:
    """
    Resolve trigger manual [{sfx_id, start_t, volume}] + aturan hook otomatis
    jadi [{abs_path, start_t, volume}]. Entri tak valid / berkas hilang di-skip.
    """
    resolved: List[Dict[str, object]] = []

    for item in manual or []:
        try:
            sfx_id = item.get("sfx_id") if isinstance(item, dict) else getattr(item, "sfx_id", None)
            start_t = item.get("start_t", 0.0) if isinstance(item, dict) else getattr(item, "start_t", 0.0)
            volume = item.get("volume", 0.8) if isinstance(item, dict) else getattr(item, "volume", 0.8)
        except AttributeError:
            continue
        if not sfx_id:
            continue
        track = await db.get(SFXTrack, str(sfx_id))
        if not track:
            continue
        abs_path = resolve_path(track.local_path)
        if not os.path.exists(abs_path):
            continue
        resolved.append({"abs_path": abs_path, "start_t": start_t, "volume": volume})

    if auto_enabled and auto_sfx_id and auto_score >= auto_threshold:
        track = await db.get(SFXTrack, str(auto_sfx_id))
        if track:
            abs_path = resolve_path(track.local_path)
            if os.path.exists(abs_path):
                resolved.append({
                    "abs_path": abs_path,
                    "start_t": AUTO_HOOK_START_T,
                    "volume": AUTO_HOOK_VOLUME,
                })

    return resolved[:MAX_TRIGGERS]
