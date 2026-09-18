"""Motion graphics overlay (Phase 3 — 3.1): intro title, outro CTA, lower third, stiker.

Semua builder di sini murni tanpa I/O (mudah di-test). Penerapan ke filtergraph
ada di `ffmpeg_service.render_vertical_clip` dengan urutan:
composite → grade (video_filter) → subtitle → overlay graphics (selalu di atas).
"""

from typing import Dict, List, Optional, Tuple

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


def _clamp(value: float, low: float, high: float, default: float) -> float:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return default
    return max(low, min(high, v))


def build_intro_overlay(title: str, duration: float = 1.5, style: str = "fade_slide") -> Optional[str]:
    """
    Judul muncul di 15% atas selama `duration` detik pertama dengan fade alpha.
    Style fade_slide menambah gerak luncur dari atas; pop/typewriter dipetakan ke fade cepat.
    """
    esc = escape_drawtext(title)
    if not esc or duration <= 0:
        return None
    d = _clamp(duration, 0.5, 5.0, 1.5)
    if style == "fade_slide":
        y_expr = f"h*0.15-60*max(0,({d}-t))/{d}"
    else:
        y_expr = "h*0.15"
    return (
        f"drawtext=text='{esc}':fontsize=64:fontcolor=white:"
        f"borderw=3:bordercolor=black@0.8:"
        f"x=(w-text_w)/2:y='{y_expr}':alpha='if(lt(t,{d}),t/{d},0)'"
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
