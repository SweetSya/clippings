import json
import logging
import os
import re
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

async def generate_thumbnail(video_path: str, thumb_path: str, seek_seconds: float = 1.0) -> bool:
    """
    Extract a single frame JPEG thumbnail.
    """
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


def _build_crop_filter(crop_mode: str, crop_offset_x: int, crop_x_expr: Optional[str]) -> str:
    """
    Build the 9:16 crop fragment.

    When crop_x_expr is provided, the single quotes protect the expression's commas from
    the filtergraph parser, so dynamic panning works inside one FFmpeg pass.
    """
    if crop_x_expr:
        return f"crop=w=ih*(9/16):h=ih:x='{crop_x_expr}':y=0"
    if crop_mode == "manual" and crop_offset_x > 0:
        return f"crop=ih*(9/16):ih:{crop_offset_x}:0"
    return "crop=ih*(9/16):ih:(iw-ow)/2:0"


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
    audio_mode: str = "mix"
) -> bool:
    """
    Render 9:16 vertical short (1080x1920) with burn-in ASS subtitle and progress tracking.
    Supports audio mixing: original audio ducking, background music (BGM), and AI voiceover.
    """
    duration = max(1.0, end_time - start_time)
    subtitle_filter = await _resolve_subtitle_filter(ass_path)
    timeout = max(300.0, duration * 10.0)

    has_voice = bool(voiceover_audio_path and os.path.exists(voiceover_audio_path))
    has_bgm = bool(bgm_audio_path and os.path.exists(bgm_audio_path))

    if audio_mode == "original":
        # "original" memakai audio video apa adanya; voiceover dan BGM diabaikan sepenuhnya.
        has_voice = False
        has_bgm = False

    async def attempt(expr: Optional[str]) -> Tuple[int, str]:
        v_filters = [
            _build_crop_filter(crop_mode, crop_offset_x, expr),
            "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920",
        ]
        if subtitle_filter:
            v_filters.append(subtitle_filter)

        if not has_voice and not has_bgm:
            # Standard single video pass
            cmd = [
                "ffmpeg", "-y",
                "-progress", "pipe:1",
                "-nostats",
                "-ss", str(start_time),
                "-to", str(end_time),
                "-i", video_path,
                "-vf", ",".join(v_filters),
                "-c:v", "libx264",
                "-preset", "fast",
                "-crf", "22",
                "-profile:v", "high",
                "-c:a", "aac",
                "-b:a", "128k",
                "-movflags", "+faststart",
                output_path
            ]
        else:
            # Multi-audio input & mixing pass
            extra_inputs = []
            audio_chains = []
            audio_inputs = []
            curr_input_idx = 1

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

            if len(audio_inputs) > 1:
                mix_in = "".join(audio_inputs)
                audio_chains.append(f"{mix_in}amix=inputs={len(audio_inputs)}:duration=first:dropout_transition=2[aout]")
                final_a = "[aout]"
            elif len(audio_inputs) == 1:
                final_a = audio_inputs[0]
            else:
                final_a = "0:a"

            v_graph = f"[0:v]{','.join(v_filters)}[vout]"
            a_graph = ";".join(audio_chains)
            full_filter_complex = f"{v_graph};{a_graph}"

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
                "-c:a", "aac",
                "-b:a", "128k",
                "-movflags", "+faststart",
                output_path
            ]

        last_pct = [0]

        def on_line(line: str):
            if line.startswith("out_time_us="):
                try:
                    us_val = int(line.split("=")[1].strip())
                    elapsed_sec = us_val / 1_000_000.0
                    pct = int(min(99, max(0, (elapsed_sec / duration) * 100)))
                    # Throttle progress reporting to 3% increments
                    if pct >= last_pct[0] + 3 and progress_callback:
                        last_pct[0] = pct
                        progress_callback(pct)
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
        progress_callback(100)

    return os.path.exists(output_path)
