"""Smart reframe: crop 9:16 yang menggeser jendela secara horizontal mengikuti kepala pembicara.

Alur:
    detect_head_timeline()  ->  smooth_head_track()  ->  plan_crop_track()  ->  crop_keyframes_to_expression()

Deteksi berjalan di Python pada frame sampel, lalu hasilnya dipadatkan menjadi timeline
keyframe. FFmpeg mengeksekusinya dalam satu pass lewat ekspresi `x` yang dievaluasi per frame.

Fungsi perencanaan (smooth/plan/expression) sengaja dibuat murni tanpa I/O agar mudah diuji.
"""

import asyncio
import bisect
import glob
import json
import logging
import os
import shutil
import tempfile
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

from app.config import settings
from app.services.storage_service import resolve_path
from app.utils.subprocess_utils import run_with_timeout

logger = logging.getLogger(__name__)

try:
    import cv2
except Exception:  # pragma: no cover - cv2 bersifat opsional
    cv2 = None

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_PATH = os.path.join(APP_DIR, "assets", settings.REFRAME_MODEL_FILENAME)

ASPECT = 9.0 / 16.0
DEFAULT_DEADZONE = 0.5
DEFAULT_PAN_SECONDS = 0.5
SNAP_MIN_INTERVAL = 0.4
DEFAULT_FRAME_WIDTH = 640
SUBJECT_JUMP_GATE = 0.35
OUTLIER_LIMIT = 0.30
EMA_ALPHA = 0.5

_model_missing_warned = False


def _silence_opencv_noise() -> None:
    """
    OpenCV 5 logs a DNN target warning even when detection runs fine. Raise the threshold
    to ERROR so genuine problems still surface while routine noise stays out of the logs.
    """
    if cv2 is None:
        return
    try:
        cv2.utils.logging.setLogLevel(cv2.utils.logging.LOG_LEVEL_ERROR)
    except Exception:
        pass


_silence_opencv_noise()


@dataclass
class HeadSample:
    """Posisi tengah kepala pada waktu `t` detik relatif terhadap awal klip."""
    t: float
    cx: float


@dataclass
class CropKeyframe:
    """Nilai offset X jendela crop pada waktu `t` detik relatif terhadap awal klip."""
    t: float
    x: int
    head_cx: Optional[float] = None


# --------------------------------------------------------------------------- deteksi


def detection_available() -> bool:
    """True bila OpenCV dan model deteksi wajah siap dipakai."""
    global _model_missing_warned
    if cv2 is None:
        return False
    if not os.path.exists(MODEL_PATH):
        if not _model_missing_warned:
            logger.warning(
                "Model deteksi wajah tidak ditemukan di %s. Smart crop akan memakai center crop.",
                MODEL_PATH,
            )
            _model_missing_warned = True
        return False
    return True


def _create_detector():
    """Buat detector baru. Dipanggil per klip agar aman saat render berjalan paralel."""
    if not detection_available():
        return None
    try:
        return cv2.FaceDetectorYN.create(
            MODEL_PATH, "", (320, 320), 0.6, 0.3, 50,
            cv2.dnn.DNN_BACKEND_OPENCV, cv2.dnn.DNN_TARGET_CPU,
        )
    except Exception as exc:
        logger.warning("Gagal memuat model deteksi wajah: %s", exc)
        return None


def _detect_faces(detector, frame) -> List[Tuple[float, float, float, float]]:
    """Deteksi wajah pada satu frame. Mengembalikan daftar kotak (x, y, w, h)."""
    height, width = frame.shape[:2]
    detector.setInputSize((width, height))
    _, faces = detector.detect(frame)
    if faces is None:
        return []
    return [(float(f[0]), float(f[1]), float(f[2]), float(f[3])) for f in faces]


def _detect_sequence(frame_paths: Sequence[str], sample_fps: float, src_width: int) -> List[HeadSample]:
    """Deteksi wajah berurutan pada frame sampel yang sudah diekstrak.

    Subjek dikunci ke deteksi pertama (kotak terluas) lalu dilacak ke deteksi terdekat.
    Koordinat `cx` dikembalikan dalam piksel video sumber.
    """
    detector = _create_detector()
    if detector is None:
        return []

    samples: List[HeadSample] = []
    anchor_cx: Optional[float] = None
    prev_cx_frame: Optional[float] = None

    for index, path in enumerate(frame_paths):
        frame = cv2.imread(path)
        if frame is None:
            continue

        frame_h, frame_w = frame.shape[:2]
        boxes = _detect_faces(detector, frame)
        if not boxes:
            continue

        if anchor_cx is None:
            bx, by, bw, bh = max(boxes, key=lambda b: b[2] * b[3])
        else:
            bx, by, bw, bh = min(boxes, key=lambda b: abs((b[0] + b[2] / 2.0) - prev_cx_frame))

        cx_frame = bx + bw / 2.0

        if anchor_cx is not None and abs(cx_frame - prev_cx_frame) > SUBJECT_JUMP_GATE * frame_w:
            continue

        prev_cx_frame = cx_frame
        scale = (src_width / frame_w) if src_width > 0 and frame_w > 0 else 1.0
        cx_source = cx_frame * scale

        if anchor_cx is None:
            anchor_cx = cx_source

        samples.append(HeadSample(t=index / sample_fps, cx=cx_source))

    return samples


async def _extract_sample_frames(
    video_path: str,
    clip_start: float,
    clip_end: float,
    sample_fps: float,
    out_dir: str,
    src_width: int,
) -> List[str]:
    """Ekstrak frame sampel sebagai JPEG kecil agar deteksi cepat."""
    filters = f"fps={sample_fps}"
    if src_width > DEFAULT_FRAME_WIDTH:
        filters += f",scale={DEFAULT_FRAME_WIDTH}:-2"

    cmd = [
        "ffmpeg", "-y", "-nostats", "-loglevel", "error",
        "-ss", f"{clip_start:.3f}",
        "-to", f"{clip_end:.3f}",
        "-i", video_path,
        "-vf", filters,
        os.path.join(out_dir, "frame_%05d.jpg"),
    ]

    duration = max(0.1, clip_end - clip_start)
    rc, _, stderr = await run_with_timeout(cmd, timeout_seconds=max(120.0, duration * 5.0))
    if rc != 0:
        raise RuntimeError(f"Ekstraksi frame sampel gagal: {stderr[-300:]}")

    return sorted(glob.glob(os.path.join(out_dir, "frame_*.jpg")))


async def detect_head_timeline(
    video_path: str,
    clip_start: float,
    clip_end: float,
    src_width: int = 0,
    sample_fps: Optional[float] = None,
) -> List[HeadSample]:
    """Deteksi posisi kepala sepanjang klip. Mengembalikan [] bila tidak ada yang terdeteksi."""
    if not detection_available():
        return []

    fps = float(sample_fps or settings.REFRAME_SAMPLE_FPS)
    work_dir = tempfile.mkdtemp(prefix="reframe_")
    try:
        frames = await _extract_sample_frames(
            video_path, clip_start, clip_end, fps, work_dir, src_width
        )
        if not frames:
            return []
        return await asyncio.to_thread(_detect_sequence, frames, fps, src_width)
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


# ------------------------------------------------------- face anchor (Phase 2 — 5.1)

FACE_ZONE_TOP_THRESHOLD = 0.35
FACE_ZONE_BOTTOM_THRESHOLD = 0.65
FACE_ANCHOR_SAMPLE_FPS = 0.5
FACE_ANCHOR_LOW_COVERAGE = 0.3

# Zona → framing_layout existing (kategori preset streamer baru di Phase 3).
FACE_ZONE_LAYOUT_MAP = {
    "top": "split_top_bottom",      # wajah atas → person top
    "bottom": "split_bottom_top",   # wajah bawah → person bottom
    "center": "single",
}


@dataclass
class FaceAnchorSample:
    """Posisi tengah wajah relatif 0-1 pada satu frame sampel."""
    cx: float
    cy: float


def classify_face_zone(avg_cy: float) -> str:
    """Klasifikasi zona vertikal wajah. Pure function (tanpa I/O)."""
    try:
        cy = float(avg_cy)
    except (TypeError, ValueError):
        return "center"
    if cy < FACE_ZONE_TOP_THRESHOLD:
        return "top"
    if cy > FACE_ZONE_BOTTOM_THRESHOLD:
        return "bottom"
    return "center"


def recommend_layout_for_zone(zone: str) -> str:
    """Petakan zona ke framing_layout existing. Pure function (tanpa I/O)."""
    return FACE_ZONE_LAYOUT_MAP.get(zone, "single")


def _detect_anchor_samples(frame_paths: Sequence[str]) -> Tuple[List[FaceAnchorSample], int]:
    """
    Deteksi wajah per frame sampel, ambil kotak terluas per frame.
    Return (sampel, jumlah_frame). Pure-CPU, dipanggil via to_thread.
    """
    detector = _create_detector()
    if detector is None:
        return [], 0
    samples: List[FaceAnchorSample] = []
    total = 0
    for path in frame_paths:
        frame = cv2.imread(path)
        if frame is None:
            continue
        total += 1
        frame_h, frame_w = frame.shape[:2]
        if frame_h <= 0 or frame_w <= 0:
            continue
        boxes = _detect_faces(detector, frame)
        if not boxes:
            continue
        bx, by, bw, bh = max(boxes, key=lambda b: b[2] * b[3])
        samples.append(FaceAnchorSample(
            cx=(bx + bw / 2.0) / frame_w,
            cy=(by + bh / 2.0) / frame_h,
        ))
    return samples, total


async def analyze_face_anchor(
    video_path: str,
    clip_start: float,
    clip_end: float,
    sample_fps: float = FACE_ANCHOR_SAMPLE_FPS,
) -> Dict[str, object]:
    """
    Analisis posisi rata-rata wajah dalam rentang klip (Phase 2 — 5.1).
    Tak pernah raise untuk kasus degradasi (model hilang / tanpa wajah):
    kembalikan coverage 0 + zona center agar caller fallback graceful.
    """
    result: Dict[str, object] = {
        "avg_cx": 0.5, "avg_cy": 0.5, "face_coverage": 0.0,
        "dominant_zone": "center",
        "recommended_layout": "single",
        "frames_sampled": 0, "frames_with_face": 0,
    }
    if not detection_available():
        return result
    work_dir = tempfile.mkdtemp(prefix="faceanchor_")
    try:
        try:
            frames = await _extract_sample_frames(
                video_path, clip_start, clip_end, sample_fps, work_dir, 0
            )
        except Exception as exc:
            logger.warning("Face anchor: ekstraksi frame gagal: %s", exc)
            return result
        if not frames:
            return result
        samples, total = await asyncio.to_thread(_detect_anchor_samples, frames)
        result["frames_sampled"] = total
        result["frames_with_face"] = len(samples)
        if total <= 0 or not samples:
            return result
        result["face_coverage"] = round(len(samples) / total, 3)
        result["avg_cx"] = round(sum(s.cx for s in samples) / len(samples), 3)
        result["avg_cy"] = round(sum(s.cy for s in samples) / len(samples), 3)
        zone = classify_face_zone(result["avg_cy"])
        result["dominant_zone"] = zone
        result["recommended_layout"] = recommend_layout_for_zone(zone)
        return result
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


# ------------------------------------------------------------------------ perencanaan


def _clamp(value: float, low: float, high: float) -> float:
    if high < low:
        return low
    return max(low, min(high, value))


def smooth_head_track(
    samples: Sequence[HeadSample],
    duration: float,
    frame_width: int,
    sample_fps: Optional[float] = None,
    max_gap: float = 1.0,
    ema_alpha: float = EMA_ALPHA,
) -> List[HeadSample]:
    """Buang outlier, isi gap pendek secara linear, tahan posisi pada gap panjang, lalu haluskan."""
    if not samples or frame_width <= 0:
        return []

    fps = float(sample_fps or settings.REFRAME_SAMPLE_FPS)
    ordered = sorted(samples, key=lambda s: s.t)

    cleaned: List[HeadSample] = []
    for sample in ordered:
        if cleaned:
            recent = sorted(c.cx for c in cleaned[-5:])
            median = recent[len(recent) // 2]
            if abs(sample.cx - median) > OUTLIER_LIMIT * frame_width:
                continue
        cleaned.append(sample)
    if not cleaned:
        return []

    times = [c.t for c in cleaned]

    def value_at(t: float) -> float:
        index = bisect.bisect_right(times, t) - 1
        if index < 0:
            return cleaned[0].cx
        before = cleaned[index]
        if index + 1 >= len(cleaned):
            return before.cx
        after = cleaned[index + 1]
        span = after.t - before.t
        if span <= 0 or span > max_gap:
            return before.cx
        return before.cx + (after.cx - before.cx) * ((t - before.t) / span)

    steps = max(1, int(round(duration * fps)))
    step = duration / steps

    smoothed: List[HeadSample] = []
    ema: Optional[float] = None
    for index in range(steps + 1):
        t = index * step
        value = value_at(t)
        ema = value if ema is None else ema + ema_alpha * (value - ema)
        smoothed.append(HeadSample(t=t, cx=ema))

    return smoothed


def _plan_once(
    head_samples: Sequence[HeadSample],
    src_w: int,
    src_h: int,
    deadzone: float,
    pan_seconds: float,
    fallback_offset: Optional[int],
    snap: bool = False,
) -> List[CropKeyframe]:
    crop_w = max(1, int(round(src_h * ASPECT)))
    max_x = max(0, src_w - crop_w)

    if not head_samples:
        start = fallback_offset if fallback_offset is not None else max_x / 2.0
        return [CropKeyframe(t=0.0, x=int(round(_clamp(start, 0, max_x))), head_cx=None)]

    band = max(1.0, deadzone * crop_w / 2.0)
    x = _clamp(head_samples[0].cx - crop_w / 2.0, 0.0, max_x)

    keyframes = [CropKeyframe(t=0.0, x=int(round(x)), head_cx=head_samples[0].cx)]
    busy_until = 0.0

    for sample in head_samples:
        if sample.t < busy_until:
            continue

        low = x + crop_w / 2.0 - band
        high = x + crop_w / 2.0 + band
        if low <= sample.cx <= high:
            continue

        if snap:
            # Potongan langsung mengembalikan subjek ke tengah. Kalau mendarat di tepi pita,
            # posisi kepala persis di batas sehingga satu frame berikutnya langsung memicu
            # potongan lagi — hasilnya berkedip.
            target = sample.cx - crop_w / 2.0
        elif sample.cx < low:
            target = sample.cx - (crop_w / 2.0 - band)
        else:
            target = sample.cx - (crop_w / 2.0 + band)
        target = _clamp(target, 0.0, max_x)

        if abs(target - x) < 1.0:
            continue

        # Saat snap, kedua keyframe berada di waktu yang sama sehingga ekspresi menjadi
        # step function (tanpa interpolasi). pan_seconds jadi jeda minimum antar potongan.
        end_t = sample.t if snap else sample.t + pan_seconds
        keyframes.append(CropKeyframe(t=sample.t, x=int(round(x)), head_cx=sample.cx))
        keyframes.append(CropKeyframe(t=end_t, x=int(round(target)), head_cx=sample.cx))
        x = target
        busy_until = sample.t + max(pan_seconds, SNAP_MIN_INTERVAL) if snap else end_t

    return _dedupe_keyframes(keyframes)


def _dedupe_keyframes(keyframes: Sequence[CropKeyframe]) -> List[CropKeyframe]:
    """Buang keyframe yang identik dan berimpit waktu (akhir satu ramp = awal ramp berikutnya)."""
    deduped: List[CropKeyframe] = []
    for keyframe in keyframes:
        if deduped and abs(deduped[-1].t - keyframe.t) < 1e-6 and deduped[-1].x == keyframe.x:
            continue
        deduped.append(keyframe)
    return deduped


def plan_crop_track(
    head_samples: Sequence[HeadSample],
    src_w: int,
    src_h: int,
    deadzone: float = DEFAULT_DEADZONE,
    pan_seconds: float = DEFAULT_PAN_SECONDS,
    fallback_offset: Optional[int] = None,
    max_keyframes: Optional[int] = None,
    snap: bool = False,
) -> List[CropKeyframe]:
    """Ubah lintasan kepala menjadi timeline offset crop.

    Aturan: selama kepala berada di pita tengah selebar `deadzone` (default 50% dari lebar
    jendela), jendela tidak bergeser. Begitu kepala melewati tepi pita, jendela bergeser
    seperlunya ke tepi terdekat — bukan di-recenter.

    Bila `snap` aktif, pergeseran terjadi seketika (potongan langsung tanpa interpolasi)
    dan subjek dikembalikan ke tengah. `pan_seconds` lalu berperan sebagai jeda minimum
    antar potongan.
    """
    limit = max_keyframes or settings.REFRAME_MAX_KEYFRAMES

    result = _plan_once(head_samples, src_w, src_h, deadzone, pan_seconds, fallback_offset, snap)
    if len(result) <= limit:
        return result

    for factor in (1.5, 2.0, 3.0, 5.0, 8.0):
        result = _plan_once(
            head_samples, src_w, src_h, deadzone, pan_seconds * factor, fallback_offset, snap
        )
        if len(result) <= limit:
            return result

    logger.warning(
        "Smart crop menghasilkan %d keyframe (batas %d); memakai rencana terakhir.",
        len(result), limit,
    )
    return result


def _format_number(value: int) -> str:
    return str(int(value))


def crop_keyframes_to_expression(keyframes: Sequence[CropKeyframe]) -> str:
    """Bangun ekspresi `x` untuk filter crop dari timeline keyframe.

    Contoh: if(lt(t,3.2),440+(t-1.5)*120,560)
    Satu keyframe cukup direpresentasikan sebagai nilai konstan.
    """
    if not keyframes:
        return "0"
    if len(keyframes) == 1:
        return _format_number(keyframes[0].x)

    def build(index: int) -> str:
        current = keyframes[index]
        following = keyframes[index + 1]
        tail = (
            _format_number(following.x)
            if index + 1 == len(keyframes) - 1
            else build(index + 1)
        )

        span = following.t - current.t
        if span <= 1e-6:
            return tail

        slope = (following.x - current.x) / span
        if abs(slope) < 1e-9:
            return f"if(lt(t,{following.t:.3f}),{_format_number(current.x)},{tail})"

        if current.t <= 1e-6:
            move = f"t*{slope:.4f}"
        else:
            move = f"(t-{current.t:.3f})*{slope:.4f}"
        value = move if current.x == 0 else f"{_format_number(current.x)}+{move}"

        return f"if(lt(t,{following.t:.3f}),{value},{tail})"

    return build(0)


# ------------------------------------------------------------------------------- cache


def _cache_path(video_id: str, clip_id: str) -> str:
    return resolve_path(f"reframe/{video_id}_{clip_id}.json")


def _read_cache(
    path: str, clip_start: float, clip_end: float, sample_fps: float, video_mtime: float
) -> Optional[List[HeadSample]]:
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        if (
            abs(float(data.get("clip_start", -1)) - clip_start) > 0.01
            or abs(float(data.get("clip_end", -1)) - clip_end) > 0.01
            or abs(float(data.get("sample_fps", -1)) - sample_fps) > 0.001
            or abs(float(data.get("video_mtime", -1)) - video_mtime) > 0.001
        ):
            return None
        return [HeadSample(t=float(item["t"]), cx=float(item["cx"])) for item in data["samples"]]
    except Exception:
        return None


def _write_cache(
    path: str,
    samples: Sequence[HeadSample],
    clip_start: float,
    clip_end: float,
    sample_fps: float,
    video_mtime: float,
) -> None:
    payload: Dict[str, object] = {
        "clip_start": clip_start,
        "clip_end": clip_end,
        "sample_fps": sample_fps,
        "video_mtime": video_mtime,
        "samples": [{"t": round(s.t, 4), "cx": round(s.cx, 2)} for s in samples],
    }
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle)
    except OSError as exc:
        logger.warning("Gagal menulis cache reframe: %s", exc)


async def get_head_samples(
    video_path: str,
    clip_start: float,
    clip_end: float,
    src_width: int,
    video_id: Optional[str] = None,
    clip_id: Optional[str] = None,
) -> List[HeadSample]:
    """Ambil lintasan kepala, memanfaatkan cache bila rentang dan berkas sumber tidak berubah."""
    fps = float(settings.REFRAME_SAMPLE_FPS)

    cache_file: Optional[str] = None
    if video_id and clip_id:
        cache_file = _cache_path(video_id, clip_id)
        try:
            mtime = os.path.getmtime(video_path)
        except OSError:
            mtime = 0.0
        cached = _read_cache(cache_file, clip_start, clip_end, fps, mtime)
        if cached is not None:
            return cached
    else:
        mtime = 0.0

    samples = await detect_head_timeline(video_path, clip_start, clip_end, src_width, fps)

    if cache_file:
        _write_cache(cache_file, samples, clip_start, clip_end, fps, mtime)

    return samples


async def build_smart_crop_expression(
    video_path: str,
    clip_start: float,
    clip_end: float,
    src_w: int,
    src_h: int,
    deadzone: float = DEFAULT_DEADZONE,
    pan_seconds: float = DEFAULT_PAN_SECONDS,
    fallback_offset: Optional[int] = None,
    video_id: Optional[str] = None,
    clip_id: Optional[str] = None,
    snap: bool = False,
) -> Optional[str]:
    """Ekspresi `x` siap pakai untuk filter crop, atau None bila tidak ada kepala terdeteksi."""
    samples = await get_head_samples(
        video_path, clip_start, clip_end, src_w, video_id=video_id, clip_id=clip_id
    )
    if not samples:
        return None

    duration = max(0.1, clip_end - clip_start)
    smoothed = smooth_head_track(samples, duration, src_w)
    keyframes = plan_crop_track(
        smoothed, src_w, src_h, deadzone=deadzone, pan_seconds=pan_seconds,
        fallback_offset=fallback_offset, snap=snap,
    )
    return crop_keyframes_to_expression(keyframes)


def build_preview(
    samples: Sequence[HeadSample],
    clip_start: float,
    clip_end: float,
    src_w: int,
    src_h: int,
    deadzone: float = DEFAULT_DEADZONE,
    pan_seconds: float = DEFAULT_PAN_SECONDS,
    fallback_offset: Optional[int] = None,
    snap: bool = False,
) -> Dict[str, object]:
    """Ringkasan timeline untuk pratinjau di Clip Studio."""
    duration = max(0.1, clip_end - clip_start)
    crop_w = max(1, int(round(src_h * ASPECT)))
    max_x = max(0, src_w - crop_w)

    expected = max(1, int(round(duration * float(settings.REFRAME_SAMPLE_FPS))))
    coverage = min(1.0, len(samples) / expected)

    if samples:
        smoothed = smooth_head_track(samples, duration, src_w)
        keyframes = plan_crop_track(
            smoothed, src_w, src_h, deadzone=deadzone, pan_seconds=pan_seconds,
            fallback_offset=fallback_offset, snap=snap,
        )
        head_series = smoothed
    else:
        keyframes = plan_crop_track(
            [], src_w, src_h, deadzone=deadzone, pan_seconds=pan_seconds,
            fallback_offset=fallback_offset, snap=snap,
        )
        head_series = []

    return {
        "clip_start": clip_start,
        "clip_end": clip_end,
        "duration": duration,
        "src_width": src_w,
        "src_height": src_h,
        "crop_width": crop_w,
        "max_offset_x": max_x,
        "deadzone": deadzone,
        "snap": snap,
        "detected": bool(samples),
        "coverage": round(coverage, 3),
        "head_samples": [{"t": round(s.t, 3), "cx": round(s.cx, 1)} for s in head_series],
        "keyframes": [
            {"t": round(k.t, 3), "x": k.x, "head_cx": (round(k.head_cx, 1) if k.head_cx is not None else None)}
            for k in keyframes
        ],
    }
