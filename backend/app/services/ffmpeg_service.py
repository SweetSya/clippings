import asyncio
import glob
import inspect
import json
import logging
import os
import re
import shutil
import tempfile
from typing import Dict, Any, Optional, Callable, Tuple
from app.utils.subprocess_utils import run_with_timeout

logger = logging.getLogger(__name__)

async def probe_video(file_path: str) -> Dict[str, Any]:
    """
    Run ffprobe to inspect video duration, resolution, and audio tracks.
    """
    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        file_path
    ]
    rc, stdout, stderr = await run_with_timeout(cmd, timeout_seconds=60.0)
    if rc != 0:
        raise RuntimeError(f"ffprobe failed (code {rc}): {stderr[:400]}")

    data = json.loads(stdout)
    format_info = data.get("format", {})
    streams = data.get("streams", [])

    duration = float(format_info.get("duration", 0.0))
    video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)

    width = int(video_stream.get("width", 0)) if video_stream else 0
    height = int(video_stream.get("height", 0)) if video_stream else 0

    return {
        "duration": duration,
        "width": width,
        "height": height,
        "has_audio": audio_stream is not None,
        "audio_codec": audio_stream.get("codec_name") if audio_stream else None,
        "video_codec": video_stream.get("codec_name") if video_stream else None,
        "size_bytes": int(format_info.get("size", 0))
    }

async def extract_audio(video_path: str, audio_path: str) -> bool:
    """
    Extract audio from video to 16kHz mono PCM WAV.
    """
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-vn",
        "-acodec", "pcm_s16le",
        "-ar", "16000",
        "-ac", "1",
        audio_path
    ]
    rc, _, stderr = await run_with_timeout(cmd, timeout_seconds=1800.0)
    if rc != 0:
        raise RuntimeError(f"FFmpeg audio extraction failed: {stderr[-500:]}")
    return os.path.exists(audio_path)

async def generate_thumbnail(video_path: str, thumb_path: str, seek_seconds: float = 1.0, smart: bool = True) -> bool:
    """
    Extract JPEG thumbnail. Mode smart (default): pilih frame terbaik dari
    N kandidat (skor wajah + ketajaman) di sekitar seek_seconds; gagal → fallback detik statik.
    """
    if smart:
        try:
            best = await select_best_thumbnail(video_path, seek_seconds)
            if best and os.path.exists(best):
                os.makedirs(os.path.dirname(os.path.abspath(thumb_path)), exist_ok=True)
                shutil.copyfile(best, thumb_path)
                return os.path.exists(thumb_path)
        except Exception as exc:
            logger.warning("Smart thumbnail gagal, fallback statik: %s", exc)
    cmd = [
        "ffmpeg", "-y",
        "-ss", str(seek_seconds),
        "-i", video_path,
        "-frames:v", "1",
        "-vf", "scale=480:-2",
        thumb_path
    ]
    rc, _, stderr = await run_with_timeout(cmd, timeout_seconds=60.0)
    if rc != 0:
        # Retry seeking to 0 if seek_seconds failed
        cmd[3] = "0.0"
        rc, _, stderr = await run_with_timeout(cmd, timeout_seconds=60.0)
        if rc != 0:
            raise RuntimeError(f"FFmpeg thumbnail generation failed: {stderr[-500:]}")
    return os.path.exists(thumb_path)


THUMB_CANDIDATES = 10
THUMB_WINDOW_BEFORE = 2.0
THUMB_WINDOW_AFTER = 8.0


def score_thumbnail_frame(face_area_frac: float, sharpness: float, sharp_min: float, sharp_max: float) -> float:
    """
    Skor kandidat thumbnail: 0.6 wajah + 0.4 ketajaman ternormalisasi.
    Pure function (tanpa I/O).
    """
    try:
        face = max(0.0, min(1.0, float(face_area_frac)))
    except (TypeError, ValueError):
        face = 0.0
    span = max(1e-6, sharp_max - sharp_min)
    sharp_norm = max(0.0, min(1.0, (sharpness - sharp_min) / span))
    return round(0.6 * face + 0.4 * sharp_norm, 4)


def _frame_sharpness(cv2_mod, img) -> float:
    """Laplacian variance grayscale sebagai proksi ketajaman."""
    gray = cv2_mod.cvtColor(img, cv2_mod.COLOR_BGR2GRAY)
    return float(cv2_mod.Laplacian(gray, cv2_mod.CV_64F).var())


async def select_best_thumbnail(
    video_path: str,
    seek_seconds: float = 1.0,
    n_candidates: int = THUMB_CANDIDATES,
) -> Optional[str]:
    """
    Pilih frame terbaik (wajah + tajam) di window sekitar seek_seconds.
    Return path JPEG kandidat terbaik, atau None bila cv2/ffmpeg tak mampu.
    Caller hapus file bila sudah disalin; direktori sementara dibersihkan bila gagal.
    """
    try:
        import cv2 as cv2_mod
    except Exception:
        return None
    if cv2_mod is None:
        return None

    from app.services.reframe_service import _create_detector, _detect_faces, detection_available

    start = max(0.0, float(seek_seconds) - THUMB_WINDOW_BEFORE)
    window = THUMB_WINDOW_BEFORE + THUMB_WINDOW_AFTER
    work_dir = tempfile.mkdtemp(prefix="smartthumb_")
    try:
        fps = max(0.5, n_candidates / window)
        cmd = [
            "ffmpeg", "-y", "-nostats", "-loglevel", "error",
            "-ss", f"{start:.3f}",
            "-i", video_path,
            "-t", f"{window:.1f}",
            "-vf", f"fps={fps:.2f},scale=480:-2",
            os.path.join(work_dir, "cand_%03d.jpg"),
        ]
        rc, _, _ = await run_with_timeout(cmd, timeout_seconds=90.0)
        frames = sorted(glob.glob(os.path.join(work_dir, "cand_*.jpg")))
        if rc != 0 or not frames:
            return None

        detector = _create_detector() if detection_available() else None

        def _score_all():
            scored = []
            for path in frames[:n_candidates]:
                img = cv2_mod.imread(path)
                if img is None:
                    continue
                h, w = img.shape[:2]
                try:
                    sharp = _frame_sharpness(cv2_mod, img)
                except Exception:
                    sharp = 0.0
                face_frac = 0.0
                if detector is not None and h > 0 and w > 0:
                    try:
                        boxes = _detect_faces(detector, img)
                        if boxes:
                            _, _, bw, bh = max(boxes, key=lambda b: b[2] * b[3])
                            face_frac = (bw * bh) / float(w * h)
                    except Exception:
                        pass
                scored.append((path, face_frac, sharp))
            return scored

        scored = await asyncio.to_thread(_score_all)
        if not scored:
            return None
        sharp_vals = [s[2] for s in scored]
        s_min, s_max = min(sharp_vals), max(sharp_vals)
        best = max(scored, key=lambda s: score_thumbnail_frame(s[1], s[2], s_min, s_max))
        # Pindahkan pemenang keluar dari work_dir agar tidak ikut terhapus.
        out_path = os.path.join(tempfile.gettempdir(), f"smartthumb_best_{os.getpid()}.jpg")
        shutil.copyfile(best[0], out_path)
        return out_path
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)

async def _resolve_subtitle_filter(ass_path: Optional[str]) -> Optional[str]:
    """
    Detect whether the local FFmpeg build exposes the ass/subtitles filter and return
    the ready-to-use filter fragment, or None when subtitles cannot be burned in.
    """
    if not ass_path or not os.path.exists(ass_path):
        return None

    sub_filter_name = None
    try:
        rc_f, stdout_f, _ = await run_with_timeout(["ffmpeg", "-filters"], timeout_seconds=3.0)
        if rc_f == 0:
            if " ass " in stdout_f or "\n .. ass " in stdout_f:
                sub_filter_name = "ass"
            elif "subtitles" in stdout_f:
                sub_filter_name = "subtitles"
    except Exception:
        pass

    if not sub_filter_name:
        return None

    escaped_ass = ass_path.replace("\\", "/").replace(":", "\\:")
    return f"{sub_filter_name}='{escaped_ass}'"


# Preset Video Filter Pack (Phase 1 — 3.4). Fragment FFmpeg yang ditempel SETELAH
# composite video jadi, SEBELUM subtitle burn-in (subtitle selalu di atas, tak ikut di-grade).
# Key tak dikenal → fallback 'none' (perilaku lama), job tak boleh gagal.
VIDEO_FILTERS = {
    "none": None,
    "cinematic": "eq=contrast=1.1:saturation=0.85,vignette=PI/4",
    "vivid": "eq=saturation=1.4:brightness=0.05",
    "warm": "colorchannelmixer=rr=1.1:gg=0.95:bb=0.8",
    "cool": "colorchannelmixer=rr=0.9:gg=0.95:bb=1.15",
    "drama": "curves=r='0/0 0.5/0.4 1/1':b='0/0 0.5/0.6 1/1'",
    "vintage": "hue=s=0.7,vignette,curves=all='0/0 0.5/0.45 1/0.9'",
}


def _resolve_video_filter(video_filter: Optional[str]) -> Optional[str]:
    if not video_filter:
        return None
    return VIDEO_FILTERS.get(str(video_filter).strip().lower())


async def _drawtext_available() -> bool:
    """Cek apakah build FFmpeg lokal mendukung filter drawtext (untuk overlay grafis)."""
    try:
        rc, stdout_f, _ = await run_with_timeout(["ffmpeg", "-filters"], timeout_seconds=5.0)
        if rc != 0:
            return False
        return " drawtext " in stdout_f or "\n .. drawtext " in stdout_f or "drawtext" in stdout_f
    except Exception:
        return False


def _stage_drawtext_chain(graph_parts: list, src_label: str, stages) -> str:
    """Rangkai stage drawtext berurutan. Kembalikan label akhir."""
    cur = src_label
    for i, stage in enumerate(stages):
        out = f"[v_ov{i}]"
        graph_parts.append(f"{cur}{stage}{out}")
        cur = out
    return cur


def _apply_grade_step(graph_parts: list, src_label: str, video_filter: Optional[str]) -> str:
    """
    Tempel grading tepat setelah composite, sebelum subtitle burn-in.
    Kembalikan label sumber untuk tahap berikutnya ([v_graded] atau label asal).
    """
    grade = _resolve_video_filter(video_filter)
    if not grade:
        return src_label
    graph_parts.append(f"{src_label}{grade}[v_graded]")
    return "[v_graded]"
    """
    Tempel grading tepat setelah composite, sebelum subtitle burn-in.
    Kembalikan label sumber untuk tahap berikutnya ([v_graded] atau label asal).
    """
    grade = _resolve_video_filter(video_filter)
    if not grade:
        return src_label
    graph_parts.append(f"{src_label}{grade}[v_graded]")
    return "[v_graded]"


def _build_crop_filter(crop_mode: str, crop_offset_x: int, crop_x_expr: Optional[str]) -> str:
    """
    Build the 9:16 crop fragment.

    When crop_x_expr is provided, the single quotes protect the expression's commas from
    the filtergraph parser, so dynamic panning works inside one FFmpeg pass.
    """
    if crop_x_expr:
        return f"crop=w=ih*(9/16):h=ih:x='{crop_x_expr}':y=0"
    if crop_mode == "manual" and crop_offset_x > 0:
        return f"crop=w=ih*(9/16):h=ih:x={crop_offset_x}:y=0"
    return "crop=w=ih*(9/16):h=ih:x='(iw-ow)/2':y=0"


def _build_video_filtergraph(
    framing_layout: str = "single",
    crop_mode: str = "center",
    crop_offset_x: int = 0,
    expr: Optional[str] = None,
    person_offset_x: int = 0,
    person_offset_y: int = 0,
    screen_offset_x: int = 0,
    screen_offset_y: int = 0,
    screen_scale: float = 1.0,
    screen_aspect: str = "16:9",
    subtitle_filter: Optional[str] = None,
    screen_mode: str = "full",
    person_shape: str = "circle",
    person_scale: float = 0.45,
    video_filter: Optional[str] = "none",
    face_cy_ratio: Optional[float] = None,
) -> Tuple[str, bool]:
    """
    Build video filtergraph string and return (graph_string, is_complex).
    Supports:
    - 'single': 9:16 standard crop with smart panning or static crop
    - 'pip_full' / 'pip_center' / 'overlay_pip': Background screen (full 9:16 or center 16:9 blur) with overlaid cropped person (PIP)
    - 'split_top_bottom': Person top (1080x960), Screen bottom (1080x960)
    - 'split_bottom_top': Screen top (1080x960), Person bottom (1080x960)
    - 'fit_16_9_center': Centered 16:9 screen over blurred ambient 1080x1920 background
    - 'streamer_face_top' / 'streamer_face_bottom': Face zone 40% (1080x768, Y-aware via
      face_cy_ratio dari analyze_face_anchor) + konten 60% (1080x1152)
    - 'video_filter': color grading preset dari VIDEO_FILTERS, ditempel setelah composite
      dan sebelum subtitle burn-in. 'none'/invalid = tanpa grading.
    """
    if framing_layout in ("pip_full", "pip_center", "overlay_pip"):
        eff_screen_mode = "center" if framing_layout == "pip_center" else (screen_mode or "full")

        # 1. Background Layer (Layar Konten)
        if eff_screen_mode == "center":
            bg_chain = [
                "[0:v]split=3[v_bg_blur_raw][v_s_fg_raw][v_p_raw]",
                "[v_bg_blur_raw]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=20:5[v_bg_blur]",
                "[v_s_fg_raw]scale=1080:-2[v_s_fg]",
                f"[v_bg_blur][v_s_fg]overlay=(W-w)/2+({screen_offset_x}):(H-h)/2+({screen_offset_y})[v_bg]"
            ]
        else:
            pad_scr_x = f"max(0,min(iw-ow,(iw-ow)/2+({screen_offset_x})))"
            bg_chain = [
                "[0:v]split=2[v_s_raw][v_p_raw]",
                f"[v_s_raw]crop=w=ih*(9/16):h=ih:x='{pad_scr_x}':y=0,scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920[v_bg]"
            ]

        # 2. Foreground Layer (Orang / Facecam Focused Cutout)
        eff_p_scale = max(0.15, min(1.0, person_scale if person_scale is not None else 0.35))
        w_pip = int(1080 * eff_p_scale)
        w_pip -= w_pip % 2
        h_pip = w_pip

        # Focused square crop for facecam:
        # A tight 50% height square (e.g. 540x540 on 1080p source) centered on face/streamer
        crop_sq = "min(iw,trunc(ih*0.5/2)*2)"

        if expr:
            crop_p = f"crop=w='{crop_sq}':h='{crop_sq}':x='max(0,min(iw-ow,({expr})+(ih*9/32)-(ow/2)))':y='max(0,min(ih-oh,(ih-oh)/2))'"
        else:
            if crop_mode == "manual" or crop_offset_x != 0:
                eff_px = max(0, crop_offset_x)
                crop_p = f"crop=w='{crop_sq}':h='{crop_sq}':x='max(0,min(iw-ow,{eff_px}))':y='max(0,ih-oh)'"
            else:
                crop_p = f"crop=w='{crop_sq}':h='{crop_sq}':x='(iw-ow)/2':y='(ih-oh)/2'"

        # Apply shape mask
        if person_shape == "circle":
            p_shape = f"{crop_p},scale={w_pip}:{h_pip},format=yuva420p,geq=lum='p(X,Y)':a='if(lte(pow(X-W/2,2)+pow(Y-H/2,2),pow(W/2,2)),255,0)'"
        else:
            p_shape = f"{crop_p},scale={w_pip}:{h_pip},format=yuva420p,drawbox=t=4:c=white@0.9"

        pip_x = f"(W-w)/2+({person_offset_x})"
        pip_y = f"(H-h)/2+({person_offset_y})"

        graph_parts = bg_chain + [
            f"[v_p_raw]{p_shape}[v_pip]",
            f"[v_bg][v_pip]overlay={pip_x}:{pip_y}[v_comp]"
        ]

        final_src = _apply_grade_step(graph_parts, "[v_comp]", video_filter)
        if subtitle_filter:
            graph_parts.append(f"{final_src}{subtitle_filter}[vout]")
        else:
            graph_parts.append(f"{final_src}null[vout]")

        return (";".join(graph_parts), True)

    elif framing_layout in ("split_top_bottom", "split_bottom_top"):
        # Layer Orang (Person / Speaker)
        if expr:
            crop_p = f"crop=w=ih*(1080/960):h=ih:x='max(0,min(iw-ow,{expr}))':y=0"
        else:
            eff_px = max(0, crop_offset_x + person_offset_x)
            if crop_mode == "manual" or person_offset_x != 0:
                crop_p = f"crop=w=ih*(1080/960):h=ih:x='max(0,min(iw-ow,{eff_px}))':y=0"
            else:
                crop_p = "crop=w=ih*(1080/960):h=ih:x='(iw-ow)/2':y=0"

        p_chain = f"{crop_p},scale=1080:960:force_original_aspect_ratio=increase,crop=1080:960"

        # Layer Layar (Screen Content)
        eff_scale = max(0.5, min(1.5, screen_scale))
        w_target = int(1080 * eff_scale)
        h_target = int(960 * eff_scale)
        w_target -= w_target % 2
        h_target -= h_target % 2

        if screen_aspect == "9:16":
            s_scale = f"crop=w=ih*(9/16):h=ih:x='(iw-ow)/2':y=0,scale={w_target}:{h_target}:force_original_aspect_ratio=decrease"
        else:
            s_scale = f"scale={w_target}:{h_target}:force_original_aspect_ratio=decrease"

        pad_x = f"max(0,min(1080-iw,(1080-iw)/2+({screen_offset_x})))"
        pad_y = f"max(0,min(960-ih,(960-ih)/2+({screen_offset_y})))"
        s_chain = f"{s_scale},pad=1080:960:{pad_x}:{pad_y}:black"

        graph_parts = [
            "[0:v]split=2[v_p_raw][v_s_raw]",
            f"[v_p_raw]{p_chain}[v_person]",
            f"[v_s_raw]{s_chain}[v_screen]"
        ]
        if framing_layout == "split_top_bottom":
            graph_parts.append("[v_person][v_screen]vstack=inputs=2[v_stacked]")
        else:
            graph_parts.append("[v_screen][v_person]vstack=inputs=2[v_stacked]")

        final_src = _apply_grade_step(graph_parts, "[v_stacked]", video_filter)
        if subtitle_filter:
            graph_parts.append(f"{final_src}{subtitle_filter}[vout]")
        else:
            graph_parts.append(f"{final_src}null[vout]")

        return (";".join(graph_parts), True)

    elif framing_layout == "fit_16_9_center":
        eff_scale = max(0.5, min(1.5, screen_scale))
        w_fg = int(1080 * eff_scale)
        w_fg -= w_fg % 2

        if screen_aspect == "9:16":
            fg_chain = f"crop=w=ih*(9/16):h=ih:x='(iw-ow)/2':y=0,scale={w_fg}:-2"
        else:
            fg_chain = f"scale={w_fg}:-2"

        ov_x = f"(W-w)/2+({screen_offset_x})"
        ov_y = f"(H-h)/2+({screen_offset_y})"

        graph_parts = [
            "[0:v]split=2[v_bg_raw][v_fg_raw]",
            "[v_bg_raw]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=20:5[v_bg]",
            f"[v_fg_raw]{fg_chain}[v_fg]",
            f"[v_bg][v_fg]overlay={ov_x}:{ov_y}[v_comp]"
        ]
        final_src = _apply_grade_step(graph_parts, "[v_comp]", video_filter)
        if subtitle_filter:
            graph_parts.append(f"{final_src}{subtitle_filter}[vout]")
        else:
            graph_parts.append(f"{final_src}null[vout]")

        return (";".join(graph_parts), True)

    elif framing_layout in ("streamer_face_top", "streamer_face_bottom"):
        # Layout sadar zona wajah (Phase 3 — 5.2): 40% face (1080x768) + 60% konten (1080x1152).
        # Posisi band wajah mengikuti face_cy_ratio dari analyze_face_anchor (0-1 relatif).
        face_on_top = framing_layout == "streamer_face_top"
        try:
            cy = float(face_cy_ratio) if face_cy_ratio is not None else (0.25 if face_on_top else 0.75)
        except (TypeError, ValueError):
            cy = 0.25 if face_on_top else 0.75
        cy = max(0.1, min(0.9, cy))
        band_y = round(max(0.0, min(0.6, cy - 0.2)), 3)

        # Layer wajah: band 40% tinggi, tracking horizontal smart bila ada expr.
        if expr:
            crop_f = f"crop=w=ih*(1080/768):h=ih*0.4:x='max(0,min(iw-ow,{expr}))':y='ih*{band_y}'"
        else:
            eff_px = max(0, crop_offset_x + person_offset_x)
            if crop_mode == "manual" or person_offset_x != 0:
                crop_f = f"crop=w=ih*(1080/768):h=ih*0.4:x='max(0,min(iw-ow,{eff_px}))':y='ih*{band_y}'"
            else:
                crop_f = f"crop=w=ih*(1080/768):h=ih*0.4:x='(iw-ow)/2':y='ih*{band_y}'"
        f_chain = f"{crop_f},scale=1080:768:force_original_aspect_ratio=increase,crop=1080:768"

        # Layer konten: 60% sisanya (atas bila wajah bawah, bawah bila wajah atas).
        c_y_frac = 0.4 if face_on_top else 0.0
        c_crop = f"crop=w=ih*(1080/1152):h=ih*0.6:x='(iw-ow)/2':y='ih*{c_y_frac}'"
        pad_x = f"max(0,min(1080-iw,(1080-iw)/2+({screen_offset_x})))"
        pad_y = f"max(0,min(1152-ih,(1152-ih)/2+({screen_offset_y})))"
        s_chain = f"{c_crop},scale=1080:1152:force_original_aspect_ratio=increase,crop=1080:1152,pad=1080:1152:{pad_x}:{pad_y}:black"

        graph_parts = [
            "[0:v]split=2[v_f_raw][v_c_raw]",
            f"[v_f_raw]{f_chain}[v_face]",
            f"[v_c_raw]{s_chain}[v_screen]"
        ]
        if face_on_top:
            graph_parts.append("[v_face][v_screen]vstack=inputs=2[v_stacked]")
        else:
            graph_parts.append("[v_screen][v_face]vstack=inputs=2[v_stacked]")

        final_src = _apply_grade_step(graph_parts, "[v_stacked]", video_filter)
        if subtitle_filter:
            graph_parts.append(f"{final_src}{subtitle_filter}[vout]")
        else:
            graph_parts.append(f"{final_src}null[vout]")

        return (";".join(graph_parts), True)

    else:
        # Standard Single 9:16 crop
        v_filters = [
            _build_crop_filter(crop_mode, crop_offset_x, expr),
            "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920"
        ]
        grade = _resolve_video_filter(video_filter)
        if grade:
            v_filters.append(grade)
        if subtitle_filter:
            v_filters.append(subtitle_filter)
        return (",".join(v_filters), False)


async def render_vertical_clip(
    video_path: str,
    ass_path: Optional[str],
    output_path: str,
    start_time: float,
    end_time: float,
    crop_mode: str = "center",
    crop_offset_x: int = 0,
    progress_callback: Optional[Callable[[int], Any]] = None,
    crop_x_expr: Optional[str] = None,
    voiceover_audio_path: Optional[str] = None,
    bgm_audio_path: Optional[str] = None,
    bgm_volume: float = 0.2,
    audio_mode: str = "mix",
    framing_layout: str = "single",
    person_offset_x: int = 0,
    person_offset_y: int = 0,
    screen_offset_x: int = 0,
    screen_offset_y: int = 0,
    screen_scale: float = 1.0,
    screen_aspect: str = "16:9",
    screen_mode: str = "full",
    person_shape: str = "circle",
    person_scale: float = 0.45,
    video_filter: Optional[str] = "none",
    overlay_config: Optional[dict] = None,
    sfx_triggers: Optional[list] = None,
    face_cy_ratio: Optional[float] = None,
) -> bool:
    """
    Render 9:16 vertical short (1080x1920) with burn-in ASS subtitle and progress tracking.
    Supports audio mixing: original audio ducking, background music (BGM), and AI voiceover.
    Supports multi-layer framing: single, PIP overlay (full/center), split_top_bottom, split_bottom_top, fit_16_9_center.
    Supports color grading via video_filter (VIDEO_FILTERS); 'none'/invalid = tanpa grading.
    Supports motion graphics overlay via overlay_config (intro/outro/lower-third/stiker);
    overlay yang gagal tersedia di-skip agar render tetap sukses.
    """
    duration = max(1.0, end_time - start_time)
    subtitle_filter = await _resolve_subtitle_filter(ass_path)
    timeout = max(300.0, duration * 10.0)

    has_voice = bool(voiceover_audio_path and os.path.exists(voiceover_audio_path))
    has_bgm = bool(bgm_audio_path and os.path.exists(bgm_audio_path))

    if audio_mode == "original":
        # "original" memakai audio video apa adanya; voiceover dan BGM diabaikan sepenuhnya.
        include_voice = False
        include_bgm = False
    elif audio_mode == "replace":
        # "replace" mematikan trek asli video; hanya voiceover dan/atau BGM yang masuk.
        include_voice = has_voice
        include_bgm = has_bgm
    else:  # "mix"
        include_voice = has_voice
        include_bgm = has_bgm

    expr = crop_x_expr if crop_mode == "smart" else None

    # Overlay grafis (Phase 3 — 3.1): drawtext stages + stiker opsional.
    from app.services.overlay_service import build_drawtext_stages, build_sticker_stage
    overlay_cfg = overlay_config or {}
    try:
        draw_stages = build_drawtext_stages(overlay_cfg, duration)
    except Exception as exc:
        logger.warning("Overlay config tak valid, dilewati: %s", exc)
        draw_stages = []
    if draw_stages and not await _drawtext_available():
        logger.warning("Filter drawtext tak tersedia, overlay teks dilewati.")
        draw_stages = []
    sticker_abs = overlay_cfg.get("sticker_abs")
    has_sticker = bool(sticker_abs and os.path.exists(str(sticker_abs)))

    async def attempt(expr: Optional[str]) -> Tuple[int, str]:
        v_graph, is_complex = _build_video_filtergraph(
            framing_layout=framing_layout,
            crop_mode=crop_mode,
            crop_offset_x=crop_offset_x,
            expr=expr,
            person_offset_x=person_offset_x,
            person_offset_y=person_offset_y,
            screen_offset_x=screen_offset_x,
            screen_offset_y=screen_offset_y,
            screen_scale=screen_scale,
            screen_aspect=screen_aspect,
            subtitle_filter=subtitle_filter,
            screen_mode=screen_mode,
            person_shape=person_shape,
            person_scale=person_scale,
            video_filter=video_filter,
            face_cy_ratio=face_cy_ratio,
        )

        if not is_complex and not include_voice and not include_bgm and not has_sticker:
            # Standard single video pass without complex audio
            vf = v_graph + ("," + ",".join(draw_stages) if draw_stages else "")
            cmd = [
                "ffmpeg", "-y",
                "-progress", "pipe:1",
                "-nostats",
                "-ss", str(start_time),
                "-to", str(end_time),
                "-i", video_path,
                "-vf", vf,
                "-c:v", "libx264",
                "-preset", "fast",
                "-crf", "22",
                "-profile:v", "high",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac",
                "-b:a", "128k",
                "-movflags", "+faststart",
                output_path
            ]
        else:
            # Multi-audio input & mixing pass, multi-layer filtergraph pass, atau sticker overlay
            extra_inputs = []
            audio_chains = []
            audio_inputs = []
            curr_input_idx = 1

            if has_sticker:
                # Input 1 = stiker (loop). Index audio digeser +1.
                extra_inputs.extend(["-loop", "1", "-i", str(sticker_abs)])
                curr_input_idx = 2

            include_orig = (audio_mode != "replace")
            if include_orig:
                orig_vol = 0.15 if has_voice else 1.0
                audio_chains.append(f"[0:a]volume={orig_vol}[a_orig]")
                audio_inputs.append("[a_orig]")

            if has_bgm:
                extra_inputs.extend(["-stream_loop", "-1", "-i", bgm_audio_path])
                bgm_vol = max(0.01, min(1.0, bgm_volume))
                audio_chains.append(f"[{curr_input_idx}:a]volume={bgm_vol}[a_bgm]")
                audio_inputs.append("[a_bgm]")
                curr_input_idx += 1

            if has_voice:
                extra_inputs.extend(["-i", voiceover_audio_path])
                audio_chains.append(f"[{curr_input_idx}:a]volume=1.0[a_voice]")
                audio_inputs.append("[a_voice]")
                curr_input_idx += 1

            if sfx_triggers:
                # Sound effects (Phase 3 — 3.2): tiap trigger di-delay ke offsetnya lalu di-mix.
                from app.services.sfx_service import build_sfx_chain
                sfx_inputs, sfx_chains, sfx_labels, curr_input_idx = build_sfx_chain(
                    sfx_triggers, curr_input_idx
                )
                extra_inputs.extend(sfx_inputs)
                audio_chains.extend(sfx_chains)
                audio_inputs.extend(sfx_labels)

            if len(audio_inputs) > 1:
                mix_in = "".join(audio_inputs)
                audio_chains.append(f"{mix_in}amix=inputs={len(audio_inputs)}:duration=first:dropout_transition=2[aout]")
                final_a = "[aout]"
            elif len(audio_inputs) == 1:
                final_a = audio_inputs[0]
            else:
                final_a = "0:a"

            if is_complex:
                # Kupas [vout] bawaan agar stage overlay bisa ditempel setelahnya.
                v_head, _, _ = v_graph.rpartition("[vout]")
                v_parts = [v_head + "[v_base]"]
                cur_label = _stage_drawtext_chain(v_parts, "[v_base]", draw_stages)
                if has_sticker:
                    stk_scale, stk_overlay = build_sticker_stage(
                        str(overlay_cfg.get("sticker_position") or "top_right"),
                        overlay_cfg.get("sticker_scale", 0.15),
                    )
                    v_parts.append(f"[1:v]{stk_scale}[stk]")
                    v_parts.append(f"{cur_label}{stk_overlay}[vout]")
                else:
                    v_parts.append(f"{cur_label}null[vout]")
                v_graph_staged = ";".join(v_parts)
                if audio_chains:
                    full_filter_complex = f"{v_graph_staged};{';'.join(audio_chains)}"
                else:
                    full_filter_complex = v_graph_staged
            else:
                v_chain = f"[0:v]{v_graph}[v_base]"
                v_parts = [v_chain]
                cur_label = _stage_drawtext_chain(v_parts, "[v_base]", draw_stages)
                if has_sticker:
                    # Cabang ini hanya tercapai bila has_sticker (tanpa audio & single layout).
                    stk_scale, stk_overlay = build_sticker_stage(
                        str(overlay_cfg.get("sticker_position") or "top_right"),
                        overlay_cfg.get("sticker_scale", 0.15),
                    )
                    v_parts.append(f"[1:v]{stk_scale}[stk]")
                    v_parts.append(f"{cur_label}{stk_overlay}[vout]")
                else:
                    v_parts.append(f"{cur_label}null[vout]")
                if audio_chains:
                    full_filter_complex = f"{';'.join(v_parts)};{';'.join(audio_chains)}"
                else:
                    full_filter_complex = ";".join(v_parts)

            cmd = [
                "ffmpeg", "-y",
                "-progress", "pipe:1",
                "-nostats",
                "-ss", str(start_time),
                "-to", str(end_time),
                "-i", video_path,
                *extra_inputs,
                "-filter_complex", full_filter_complex,
                "-map", "[vout]",
                "-map", final_a,
                "-t", str(duration),
                "-c:v", "libx264",
                "-preset", "fast",
                "-crf", "22",
                "-profile:v", "high",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac",
                "-b:a", "128k",
                "-movflags", "+faststart",
                output_path
            ]

        last_pct = [0]

        async def on_line(line: str):
            if line.startswith("out_time_us="):
                try:
                    us_val = int(line.split("=")[1].strip())
                    elapsed_sec = us_val / 1_000_000.0
                    pct = int(min(98, max(5, (elapsed_sec / duration) * 100)))
                    # Throttle progress reporting to 3% increments
                    if pct >= last_pct[0] + 3 and progress_callback:
                        last_pct[0] = pct
                        if inspect.iscoroutinefunction(progress_callback):
                            await progress_callback(pct)
                        else:
                            res = progress_callback(pct)
                            if inspect.iscoroutine(res):
                                await res
                except Exception:
                    pass

        rc, _, stderr = await run_with_timeout(cmd, timeout_seconds=timeout, line_callback=on_line)
        return rc, stderr

    rc, stderr = await attempt(crop_x_expr)

    if rc != 0 and crop_x_expr:
        logger.warning("Render dengan ekspresi smart crop gagal, mengulang dengan crop statis: %s", stderr[-300:])
        rc, stderr = await attempt(None)

    if rc != 0:
        raise RuntimeError(f"FFmpeg render failed (code {rc}): {stderr[-500:]}")

    if progress_callback:
        if inspect.iscoroutinefunction(progress_callback):
            await progress_callback(100)
        else:
            res = progress_callback(100)
            if inspect.iscoroutine(res):
                await res

    return os.path.exists(output_path)
