"""Motion graphics overlay (Phase 3 — 3.1): intro title, outro CTA, lower third, stiker.

Semua builder di sini murni tanpa I/O (mudah di-test). Penerapan ke filtergraph
ada di `ffmpeg_service.render_vertical_clip` dengan urutan:
composite → grade (video_filter) → subtitle → overlay graphics (selalu di atas).
"""

from typing import Dict, List, Optional, Tuple

import re

INTRO_STYLES = ("fade_slide", "pop", "typewriter")

STICKER_POSITIONS: Dict[str, Tuple[str, str]] = {
    "top_right": ("W-w-40", "40"),
    "top_left": ("40", "40"),
    "bottom_right": ("W-w-40", "H-h-40"),
    "bottom_left": ("40", "H-h-40"),
    "center": ("(W-w)/2", "(H-h)/2"),
}


def escape_drawtext(text: str) -> str:
    """Escape teks agar aman di dalam drawtext=text='...'. Tanda kutip melindungi koma."""
    return (
        str(text or "")
        .replace("\\", "\\\\")
        .replace("'", "\\'")
        .replace(":", "\\:")
        .replace("\n", " ")
        .strip()
    )


def wrap_and_format_title(title: str, max_line_len: int = 22, max_lines: int = 3) -> Tuple[str, int]:
    """
    Format dan bungkus judul ke dalam baris agar tidak overflow pada video vertikal (1080x1920).
    Mengembalikan (escaped_text_with_newlines, optimal_fontsize).
    """
    raw = str(title or "").strip()
    if not raw:
        return "", 52

    # Bersihkan tanda baca berlebih di akhir
    cleaned = re.sub(r"\s*[.]{2,}\s*", " ", raw)
    cleaned = re.sub(r"\s*#[\w\d_-]+\s*", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    words = cleaned.split()
    lines: List[str] = []
    current_line: List[str] = []
    current_len = 0

    for w in words:
        w_len = len(w)
        if current_line and (current_len + 1 + w_len) > max_line_len:
            lines.append(" ".join(current_line))
            current_line = [w]
            current_len = w_len
            if len(lines) >= max_lines:
                break
        else:
            current_line.append(w)
            current_len += (1 + w_len) if len(current_line) > 1 else w_len

    if current_line and len(lines) < max_lines:
        lines.append(" ".join(current_line))

    # Jika melebihi max_lines, beri ellipsis pada baris terakhir
    if len(lines) == max_lines and len(words) > sum(len(l.split()) for l in lines):
        if not lines[-1].endswith("..."):
            lines[-1] = lines[-1][: max(5, max_line_len - 3)] + "..."

    num_lines = len(lines)
    longest_line = max((len(l) for l in lines), default=0)

    # Skala ukuran font proporsional agar muat di kanvas 1080px
    if num_lines == 1:
        font_size = 56 if longest_line <= 16 else 50
    elif num_lines == 2:
        font_size = 46 if longest_line <= 18 else 42
    else:
        font_size = 38

    # Escape masing-masing baris untuk drawtext
    escaped_lines = [escape_drawtext(l) for l in lines]
    escaped_text = "\\\n".join(escaped_lines)
    return escaped_text, font_size


def _clamp(value: float, low: float, high: float, default: float) -> float:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return default
    return max(low, min(high, v))


def build_intro_overlay(title: str, duration: float = 1.5, style: str = "fade_slide") -> Optional[str]:
    """
    Judul muncul di 15% atas selama `duration` detik pertama dengan fade alpha dan anti-overflow.
    Style fade_slide menambah gerak luncur dari atas; pop/typewriter dipetakan ke fade cepat.
    """
    if not title or duration <= 0:
        return None
    d = _clamp(duration, 0.5, 5.0, 1.5)
    escaped_text, font_size = wrap_and_format_title(title)
    if not escaped_text:
        return None

    if style == "fade_slide":
        y_expr = f"h*0.15-50*max(0,({d}-t))/{d}"
    else:
        y_expr = "h*0.15"

    # Fade in halus (0.2s), tampil stabil, fade out (0.3s) di akhir durasi jeda
    alpha_expr = f"if(lt(t,{d}),min(min(1,t/0.20),max(0,({d}-t)/0.30)),0)"

    return (
        f"drawtext=text='{escaped_text}':fontsize={font_size}:fontcolor=white:"
        f"borderw=3:bordercolor=black@0.9:box=1:boxcolor=black@0.75:boxborderw=16:line_spacing=10:"
        f"x=(w-text_w)/2:y='{y_expr}':alpha='{alpha_expr}'"
    )


def build_outro_overlay(cta_text: str, video_duration: float, cta_duration: float = 2.0) -> Optional[str]:
    """CTA tampil di `cta_duration` detik terakhir, tengah-bawah (di atas zona subtitle)."""
    esc = escape_drawtext(cta_text)
    if not esc or video_duration <= 0:
        return None
    c = _clamp(cta_duration, 0.5, 10.0, 2.0)
    start = max(0.0, video_duration - c)
    return (
        f"drawtext=text='{esc}':fontsize=44:fontcolor=white:"
        f"borderw=2:bordercolor=black@0.8:box=1:boxcolor=black@0.6:boxborderw=20:"
        f"x=(w-text_w)/2:y=h*0.80:alpha='if(gte(t,{start:.2f}),1,0)'"
    )


def build_lower_third(text: str) -> Optional[str]:
    """Strip info nama di kiri-bawah, tampil sepanjang video."""
    esc = escape_drawtext(text)
    if not esc:
        return None
    return (
        f"drawtext=text='{esc}':fontsize=40:fontcolor=white:"
        f"borderw=2:bordercolor=black@0.8:box=1:boxcolor=black@0.55:boxborderw=24:"
        f"x=60:y=h*0.70"
    )


def build_sticker_stage(position: str = "top_right", scale: float = 0.15) -> Tuple[str, str]:
    """
    Return (scale_filter, overlay_filter) untuk input stiker [1:v].
    Lebar stiker = 1080 * scale terhadap frame output.
    """
    pos = STICKER_POSITIONS.get(str(position or "top_right"), STICKER_POSITIONS["top_right"])
    w = int(1080 * _clamp(scale, 0.05, 0.5, 0.15))
    w -= w % 2
    scale_filter = f"scale={w}:-2"
    overlay_filter = f"overlay={pos[0]}:{pos[1]}"
    return scale_filter, overlay_filter


def build_drawtext_stages(cfg: Optional[Dict], duration: float) -> List[str]:
    """
    Susun stage drawtext dari overlay_config preset/payload.
    cfg keys: enable_intro_title, intro_title, intro_title_duration, intro_title_style,
    enable_outro_cta, outro_cta_text, outro_cta_duration,
    enable_lower_third, lower_third_text.
    """
    if not cfg or duration <= 0:
        return []
    stages: List[str] = []
    if cfg.get("enable_intro_title"):
        stage = build_intro_overlay(
            str(cfg.get("intro_title") or ""),
            float(cfg.get("intro_title_duration") or 1.5),
            str(cfg.get("intro_title_style") or "fade_slide"),
        )
        if stage:
            stages.append(stage)
    if cfg.get("enable_outro_cta"):
        stage = build_outro_overlay(
            str(cfg.get("outro_cta_text") or ""),
            duration,
            float(cfg.get("outro_cta_duration") or 2.0),
        )
        if stage:
            stages.append(stage)
    if cfg.get("enable_lower_third"):
        stage = build_lower_third(str(cfg.get("lower_third_text") or ""))
        if stage:
            stages.append(stage)
    return stages
