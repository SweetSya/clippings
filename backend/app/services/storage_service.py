import os
import glob
from app.config import settings

def resolve_path(relative_path: str) -> str:
    """
    Resolve a database-stored relative path (e.g. 'uploads/abc.mp4')
    to an absolute filesystem path inside STORAGE_ROOT.
    """
    root = os.path.abspath(settings.STORAGE_ROOT)
    return os.path.normpath(os.path.join(root, relative_path))

def to_relative_path(absolute_path: str) -> str:
    """
    Convert an absolute path within STORAGE_ROOT to a relative path for DB storage.
    """
    root = os.path.abspath(settings.STORAGE_ROOT)
    return os.path.relpath(absolute_path, root)

def delete_video_artifacts(video_id: str):
    """
    Clean up all physical files associated with a source video:
    - uploads/{video_id}.*
    - audio/{video_id}.wav
    - transcripts/{video_id}.json
    - thumbnails/{video_id}.jpg
    - reframe/{video_id}_*.json
    """
    root = os.path.abspath(settings.STORAGE_ROOT)
    patterns = [
        os.path.join(root, "uploads", f"{video_id}.*"),
        os.path.join(root, "audio", f"{video_id}.wav"),
        os.path.join(root, "transcripts", f"{video_id}.json"),
        os.path.join(root, "thumbnails", f"{video_id}.jpg"),
        os.path.join(root, "reframe", f"{video_id}_*.json"),
    ]
    for pat in patterns:
        for f in glob.glob(pat):
            try:
                os.remove(f)
            except OSError:
                pass

def delete_short_artifacts(short_id: str, clip_id: str = None, local_path: str = None):
    """
    Clean up all physical files associated with a rendered short:
    - local_path or exports/{short_id}_9x16.mp4
    - subtitles/{clip_id}.ass (if provided)
    """
    root = os.path.abspath(settings.STORAGE_ROOT)
    if local_path:
        target = resolve_path(local_path)
        if os.path.exists(target):
            try:
                os.remove(target)
            except OSError:
                pass

    export_file = os.path.join(root, "exports", f"{short_id}_9x16.mp4")
    if os.path.exists(export_file):
        try:
            os.remove(export_file)
        except OSError:
            pass
            
    if clip_id:
        ass_file = os.path.join(root, "subtitles", f"{clip_id}.ass")
        if os.path.exists(ass_file):
            try:
                os.remove(ass_file)
            except OSError:
                pass
