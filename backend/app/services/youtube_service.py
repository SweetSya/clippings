import os
import json
import asyncio
import re
from typing import Dict, Any, Optional

def find_ffmpeg_binary() -> str:
    """Find path to ffmpeg binary."""
    candidates = [
        "/opt/homebrew/bin/ffmpeg",
        "/usr/local/bin/ffmpeg",
        "ffmpeg"
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return "ffmpeg"

def find_ytdlp_binary() -> str:
    """Find path to yt-dlp binary."""
    candidates = [
        "/opt/homebrew/bin/yt-dlp",
        "/usr/local/bin/yt-dlp",
        "yt-dlp"
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return "yt-dlp"

async def get_youtube_info(url: str) -> Dict[str, Any]:
    """
    Probe YouTube video metadata quickly without downloading.
    Returns: title, duration, thumbnail, channel, description.
    """
    ytdlp = find_ytdlp_binary()
    cmd = [
        ytdlp,
        "--dump-single-json",
        "--no-warnings",
        "--flat-playlist",
        url
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        err_msg = stderr.decode('utf-8', errors='replace').strip()
        raise ValueError(f"Gagal mengambil info video YouTube: {err_msg[:200]}")

    data = json.loads(stdout.decode('utf-8', errors='replace'))
    return {
        "id": data.get("id"),
        "title": data.get("title") or "YouTube Video",
        "duration_seconds": float(data.get("duration") or 0),
        "thumbnail_url": data.get("thumbnail"),
        "channel": data.get("channel") or data.get("uploader"),
        "webpage_url": data.get("webpage_url") or url,
        "description": data.get("description") or ""
    }

async def download_youtube_video(
    url: str,
    output_path: str,
    quality_pref: str = "1080p",
    line_callback = None
) -> str:
    """
    Download a video from YouTube using yt-dlp.
    quality_pref: "1080p" (Full HD if available), "720p" (HD), or "best"
    """
    ytdlp = find_ytdlp_binary()
    ffmpeg_bin = find_ffmpeg_binary()
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # Format selector based on user preference
    # Do not restrict to [ext=mp4] because YouTube serves modern 1080p/720p in WebM/VP9/AV1
    # which ffmpeg merges and remuxes/transcodes cleanly into mp4
    if quality_pref == "1080p":
        fmt = "bestvideo[height<=1080]+bestaudio/best[height<=1080]/bestvideo+bestaudio/best"
    elif quality_pref == "720p":
        fmt = "bestvideo[height<=720]+bestaudio/best[height<=720]/bestvideo+bestaudio/best"
    else:  # "best" or other
        fmt = "bestvideo+bestaudio/best"

    cmd = [
        ytdlp,
        "--newline",
        "--ffmpeg-location", ffmpeg_bin,
        "-f", fmt,
        "--merge-output-format", "mp4",
        "-o", output_path,
        url
    ]

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )

    stdout_lines = []
    stderr_lines = []

    async def read_stdout(stream):
        while True:
            line = await stream.readline()
            if not line:
                break
            line_str = line.decode('utf-8', errors='replace').strip()
            stdout_lines.append(line_str)
            if line_callback:
                line_callback(line_str)

    async def read_stderr(stream):
        while True:
            line = await stream.readline()
            if not line:
                break
            line_str = line.decode('utf-8', errors='replace').strip()
            stderr_lines.append(line_str)
            if line_callback:
                line_callback(line_str)

    await asyncio.gather(
        read_stdout(proc.stdout),
        read_stderr(proc.stderr)
    )
    await proc.wait()

    if proc.returncode != 0:
        err_detail = " ".join([l for l in stderr_lines if l]) or " ".join([l for l in stdout_lines if l]) or f"kode {proc.returncode}"
        raise RuntimeError(f"Gagal mengunduh video dari YouTube: {err_detail[-300:]}")

    return output_path

async def download_youtube_audio(url: str, output_path: str) -> Dict[str, Any]:
    """
    Download audio track from YouTube video and convert directly to MP3 using yt-dlp + ffmpeg.
    Returns metadata: title, duration_seconds, file_size_bytes.
    """
    ytdlp = find_ytdlp_binary()
    ffmpeg_bin = find_ffmpeg_binary()
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    info = await get_youtube_info(url)
    title = info.get("title") or "YouTube Audio"
    duration = float(info.get("duration_seconds") or 0.0)

    cmd = [
        ytdlp,
        "--newline",
        "--ffmpeg-location", ffmpeg_bin,
        "-x",
        "--audio-format", "mp3",
        "--audio-quality", "0",
        "-o", output_path,
        url
    ]

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        err_detail = stderr.decode('utf-8', errors='replace').strip() or stdout.decode('utf-8', errors='replace').strip()
        raise RuntimeError(f"Gagal mengunduh audio YouTube: {err_detail[-300:]}")

    size_bytes = os.path.getsize(output_path) if os.path.exists(output_path) else 0

    return {
        "title": title,
        "duration_seconds": duration,
        "file_size_bytes": size_bytes,
        "output_path": output_path
    }
