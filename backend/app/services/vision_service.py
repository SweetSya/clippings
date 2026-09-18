"""Vision-aware clipping (Phase 4 — 2.1): highlight visual via model multimodal.

Alur: ekstrak 1 frame/2 detik (≤512px) → batch grid 4x4 berlabel timestamp →
Vision LLM → [{timestamp, visual_score, description}] → boost composite kandidat.

Semua failure (tanpa cv2, model tak support gambar, timeout) degrade graceful:
kembalikan [] agar text analysis jalan tanpa boost. Tak pernah raise ke caller
kecuali video tak terbaca untuk ekstraksi (itu pun ditangkap pipeline).
"""

import asyncio
import base64
import glob
import logging
import os
import shutil
import tempfile
from typing import Any, Dict, List, Optional, Tuple

from app.utils.subprocess_utils import run_with_timeout

logger = logging.getLogger(__name__)

VISION_FRAME_FPS = 0.5
VISION_FRAME_MAX_WIDTH = 512
VISION_GRID_SIZE = 4  # 4x4 = 16 frame per request
VISION_MAX_GRIDS = 8
VISION_CELL_WIDTH = 160

VISION_SYSTEM_PROMPT = """Kamu analis visual video pendek. Diberi grid 4x4 frame berlabel timestamp (detik).
Identifikasi frame yang menunjukkan momen visual menonjol:
- Ekspresi emosi intens (kaget, gembira, terkejut, marah)
- Gestur kuat / bahasa tubuh dramatis
- Slide presentasi / teks penting di layar
- Momen visual 'wow' atau dramatis lainnya

Balas HANYA JSON valid, TANPA markdown, TANPA penjelasan:
{"highlights": [{"timestamp": 12.0, "visual_score": 85, "description": "..."}]}
visual_score 0-100. Kosongkan highlights bila tak ada yang menonjol."""


def batch_frames_to_grid(
    frames: List[Tuple[str, float]], grid_size: int = VISION_GRID_SIZE
) -> List[Tuple[Any, List[float]]]:
    """
    Kelompokkan [(path, timestamp)] jadi grid 4x4 (numpy image, [timestamps]).
    Butuh cv2; raise ImportError bila tak tersedia (ditangkap caller).
    Pure-CPU, dipanggil via to_thread.
    """
    import cv2 as cv2_mod
    import numpy as np

    grids: List[Tuple[Any, List[float]]] = []
    for i in range(0, len(frames), grid_size * grid_size):
        batch = frames[i:i + grid_size * grid_size]
        cells, stamps = [], []
        for path, ts in batch:
            img = cv2_mod.imread(path)
            if img is None:
                continue
            h, w = img.shape[:2]
            cell_h = int(VISION_CELL_WIDTH * h / max(1, w))
            cell = cv2_mod.resize(img, (VISION_CELL_WIDTH, cell_h))
            cv2_mod.putText(cell, f"{ts:.0f}s", (4, 14),
                            cv2_mod.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1)
            cells.append(cell)
            stamps.append(ts)
        if not cells:
            continue
        # Samakan tinggi sel per baris lalu susun grid
        rows = []
        for r in range(0, len(cells), grid_size):
            row_cells = cells[r:r + grid_size]
            max_h = max(c.shape[0] for c in row_cells)
            padded = []
            for c in row_cells:
                if c.shape[0] < max_h:
                    pad = 255 * np.ones(
                        (max_h - c.shape[0], c.shape[1], 3), dtype=c.dtype)
                    c = np.vstack([c, pad])
                padded.append(c)
            while len(padded) < grid_size:
                padded.append(255 * np.ones_like(padded[0]))
            rows.append(np.hstack(padded))
        max_w = max(r.shape[1] for r in rows)
        norm_rows = []
        for r in rows:
            if r.shape[1] < max_w:
                pad = 255 * np.ones(
                    (r.shape[0], max_w - r.shape[1], 3), dtype=r.dtype)
                r = np.hstack([r, pad])
            norm_rows.append(r)
        while len(norm_rows) < grid_size:
            norm_rows.append(255 * np.ones_like(norm_rows[0]))
        grids.append((np.vstack(norm_rows), stamps))
    return grids


def _grid_to_data_uri(grid) -> Optional[str]:
    try:
        import cv2 as cv2_mod
        ok, buf = cv2_mod.imencode(".jpg", grid, [int(cv2_mod.IMWRITE_JPEG_QUALITY), 70])
        if not ok:
            return None
        b64 = base64.b64encode(bytes(buf)).decode("ascii")
        return f"data:image/jpeg;base64,{b64}"
    except Exception:
        return None


async def analyze_frames_with_vision(
    grid_uri: str,
    grid_start: float,
    grid_end: float,
    llm_base_url: str,
    llm_api_key: Optional[str],
    llm_model: Optional[str],
) -> List[Dict[str, object]]:
    """Satu request vision per grid. Return highlights tervalidasi atau [] bila gagal."""
    from app.services.llm_service import _post_chat, sanitize_and_parse_json

    messages = [
        {"role": "system", "content": VISION_SYSTEM_PROMPT},
        {"role": "user", "content": [
            {"type": "text", "text": f"Grid mencakup detik {grid_start:.0f} sampai {grid_end:.0f}."},
            {"type": "image_url", "image_url": {"url": grid_uri}},
        ]},
    ]
    try:
        content = await _post_chat(
            llm_base_url, llm_api_key, llm_model, messages,
            temperature=0.2, timeout_seconds=60.0,
        )
        parsed = sanitize_and_parse_json(content)
        items = parsed.get("highlights", []) if isinstance(parsed, dict) else (parsed or [])
        out = []
        for it in items:
            if not isinstance(it, dict):
                continue
            try:
                ts = float(it.get("timestamp", grid_start))
                score = max(0, min(100, int(it.get("visual_score", 50))))
            except (TypeError, ValueError):
                continue
            if not (grid_start - 5 <= ts <= grid_end + 5):
                continue
            out.append({
                "timestamp": round(ts, 1),
                "visual_score": score,
                "description": str(it.get("description", ""))[:200],
            })
        return out
    except Exception as exc:
        logger.warning("Vision grid %.0f-%.0fs gagal: %s", grid_start, grid_end, exc)
        return []


async def extract_visual_highlights(
    video_path: str,
    video_duration: float,
    llm_base_url: Optional[str],
    llm_api_key: Optional[str] = None,
    llm_model: Optional[str] = None,
    max_grids: int = VISION_MAX_GRIDS,
) -> List[Dict[str, object]]:
    """
    Pass visual opsional: frame → grid → Vision LLM → highlights.
    Selalu kembalikan list (kosong bila dinonaktifkan/gagal) — tak pernah raise.
    """
    if not llm_base_url or not video_path or not os.path.exists(video_path):
        return []
    try:
        import cv2  # noqa: F401
    except Exception:
        logger.warning("cv2 tak tersedia, vision pass dilewati.")
        return []

    work_dir = tempfile.mkdtemp(prefix="vision_")
    try:
        cmd = [
            "ffmpeg", "-y", "-nostats", "-loglevel", "error",
            "-i", video_path,
            "-vf", f"fps={VISION_FRAME_FPS},scale={VISION_FRAME_MAX_WIDTH}:-2",
            os.path.join(work_dir, "vframe_%05d.jpg"),
        ]
        rc, _, stderr = await run_with_timeout(
            cmd, timeout_seconds=max(120.0, float(video_duration or 0) * 2.0))
        if rc != 0:
            logger.warning("Ekstraksi frame vision gagal: %s", stderr[-300:])
            return []
        paths = sorted(glob.glob(os.path.join(work_dir, "vframe_*.jpg")))
        if not paths:
            return []
        frames = [(p, round(i / VISION_FRAME_FPS, 1)) for i, p in enumerate(paths)]
        # Batasi grid: stride merata agar cakup seluruh durasi
        per_grid = VISION_GRID_SIZE * VISION_GRID_SIZE
        max_frames = max_grids * per_grid
        if len(frames) > max_frames:
            step = len(frames) / max_frames
            frames = [frames[int(i * step)] for i in range(max_frames)]

        try:
            grids = await asyncio.to_thread(batch_frames_to_grid, frames)
        except Exception as exc:
            logger.warning("Grid batching gagal: %s", exc)
            return []

        highlights: List[Dict[str, object]] = []
        for grid, stamps in grids:
            uri = _grid_to_data_uri(grid)
            if not uri or not stamps:
                continue
            res = await analyze_frames_with_vision(
                uri, min(stamps), max(stamps),
                llm_base_url, llm_api_key, llm_model,
            )
            highlights.extend(res)
        highlights.sort(key=lambda h: h["visual_score"], reverse=True)
        return highlights
    except Exception as exc:
        logger.warning("Vision pass gagal: %s", exc)
        return []
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


def build_vision_boost(
    highlights: List[Dict[str, object]],
) -> Dict[float, float]:
    """timestamp → skor visual maks. Pure function (tanpa I/O)."""
    boost: Dict[float, float] = {}
    for h in highlights or []:
        try:
            ts = float(h.get("timestamp", -1))
            score = max(0, min(100, float(h.get("visual_score", 0))))
        except (TypeError, ValueError, AttributeError):
            continue
        if ts >= 0 and score > boost.get(ts, 0):
            boost[ts] = score
    return boost
