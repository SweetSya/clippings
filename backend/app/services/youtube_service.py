import os
import sys
import json
import asyncio
import re
import shutil
from typing import Dict, Any, Optional, List

# Client fallback sequences for YouTube bot-check bypass
YT_CLIENT_FALLBACKS = [
    "android,ios,mweb,web",
    "android,ios",
    "mweb,android,ios,web",
    "android_embedded,web_embedded,ios,android"
]

def find_ffmpeg_binary() -> str:
    """Find path to ffmpeg binary."""
    which_bin = shutil.which("ffmpeg")
    if which_bin:
        return which_bin
    candidates = [
        "/usr/bin/ffmpeg",
        "/usr/local/bin/ffmpeg",
        "/opt/homebrew/bin/ffmpeg",
        "ffmpeg"
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return "ffmpeg"

def find_ytdlp_cmd() -> List[str]:
    """Find command prefix to execute yt-dlp."""
    which_bin = shutil.which("yt-dlp")
    if which_bin:
        return [which_bin]
    for c in ["/usr/local/bin/yt-dlp", "/usr/bin/yt-dlp", "/opt/homebrew/bin/yt-dlp"]:
        if os.path.exists(c):
            return [c]
    # Fallback to python module execution if binary isn't in PATH
    return [sys.executable, "-m", "yt_dlp"]

def get_youtube_cookies_path() -> Optional[str]:
    """Find local youtube cookies file if provided by user."""
    candidates = [
        "storage/youtube_cookies.txt",
        "/app/storage/youtube_cookies.txt",
        "storage/cookies.txt",
        "/app/storage/cookies.txt",
        "/storage/youtube_cookies.txt",
        "/storage/cookies.txt"
    ]
    for c in candidates:
        if os.path.isfile(c) and os.path.getsize(c) > 0:
            return c
    return None

def build_ytdlp_args(client_type: str = "android,ios,mweb,web") -> List[str]:
    """Build base yt-dlp CLI arguments including anti-bot client spoofing and cookies."""
    args = find_ytdlp_cmd() + [
        "--extractor-args", f"youtube:player_client={client_type}",
        "--no-check-certificates",
        "--user-agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    ]
    cookies_file = get_youtube_cookies_path()
    if cookies_file:
        args += ["--cookies", cookies_file]
    return args

async def get_youtube_info(url: str) -> Dict[str, Any]:
    """
    Probe YouTube video metadata quickly without downloading.
    Uses multi-client fallback to bypass bot check challenges.
    Returns: title, duration, thumbnail, channel, description.
    """
    last_err = ""
    for client in YT_CLIENT_FALLBACKS:
        cmd = build_ytdlp_args(client) + [
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
        if proc.returncode == 0:
            try:
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
            except Exception as e:
                last_err = str(e)
                continue
        else:
            err_msg = stderr.decode('utf-8', errors='replace').strip() or stdout.decode('utf-8', errors='replace').strip()
            last_err = err_msg

    raise ValueError(f"Gagal mengambil info video YouTube: {last_err[:250]}")

async def download_youtube_video(
    url: str,
    output_path: str,
    quality_pref: str = "1080p",
    line_callback = None
) -> str:
    """
    Download a video from YouTube using yt-dlp with anti-bot bypass & client fallback.
    quality_pref: "1080p" (Full HD if available), "720p" (HD), or "best"
    """
    ffmpeg_bin = find_ffmpeg_binary()
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    if quality_pref == "1080p":
        fmt = "bestvideo[height<=1080]+bestaudio/best[height<=1080]/bestvideo+bestaudio/best"
    elif quality_pref == "720p":
        fmt = "bestvideo[height<=720]+bestaudio/best[height<=720]/bestvideo+bestaudio/best"
    else:  # "best" or other
        fmt = "bestvideo+bestaudio/best"

    last_err = ""
    for client in YT_CLIENT_FALLBACKS:
        cmd = build_ytdlp_args(client) + [
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

        if proc.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            return output_path

        last_err = " ".join([l for l in stderr_lines if l]) or " ".join([l for l in stdout_lines if l]) or f"kode {proc.returncode}"

    raise RuntimeError(f"Gagal mengunduh video dari YouTube: {last_err[-300:]}")

async def download_youtube_audio(url: str, output_path: str) -> Dict[str, Any]:
    """
    Download audio track from YouTube video and convert directly to MP3 using yt-dlp + ffmpeg.
    Returns metadata: title, duration_seconds, file_size_bytes.
    """
    ffmpeg_bin = find_ffmpeg_binary()
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    info = await get_youtube_info(url)
    title = info.get("title") or "YouTube Audio"
    duration = float(info.get("duration_seconds") or 0.0)

    last_err = ""
    for client in YT_CLIENT_FALLBACKS:
        cmd = build_ytdlp_args(client) + [
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
        if proc.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            size_bytes = os.path.getsize(output_path)
            return {
                "title": title,
                "duration_seconds": duration,
                "file_size_bytes": size_bytes,
                "output_path": output_path
            }

        last_err = stderr.decode('utf-8', errors='replace').strip() or stdout.decode('utf-8', errors='replace').strip()

    raise RuntimeError(f"Gagal mengunduh audio YouTube: {last_err[-300:]}")
