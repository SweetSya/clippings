import os
import wave
import array
import math
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


def compute_audio_rms_for_samples(samples: array.array) -> float:
    """
    Menghitung Root Mean Square (RMS) dari sekumpulan sampel PCM 16-bit.
    Menggunakan array.array murni standar Python (kompatibel penuh Python 3.14+).
    """
    n = len(samples)
    if n == 0:
        return 0.0
    sum_sq = sum(int(s) * int(s) for s in samples)
    return math.sqrt(sum_sq / n)


def analyze_vocal_dynamics(
    audio_path: Optional[str],
    words: List[Dict[str, Any]],
    clip_start: float,
    clip_end: float,
) -> List[Dict[str, Any]]:
    """
    Menganalisis profil energi vokal (loudness / RMS) per kata dalam rentang klip.
    
    Mengembalikan daftar kata yang diperkaya dengan:
    - energy_ratio: rasio energi kata terhadap rata-rata energi klip
    - scale_multiplier: skala ukuran teks dinamis (0.88x untuk suara pelan, 1.25x-1.35x untuk penekanan tegas)
    - energy_level: 'high' (penekanan kuat), 'normal', atau 'low' (berbisik/pelan)
    - is_vocal_stressed: boolean True jika kata diucapkan dengan penekanan kuat
    """
    # Salin list kata agar tidak memodifikasi input secara langsung
    enriched_words = [dict(w) for w in words]

    if not audio_path or not os.path.exists(audio_path) or not enriched_words:
        for w in enriched_words:
            w.setdefault("energy_ratio", 1.0)
            w.setdefault("scale_multiplier", 1.0)
            w.setdefault("energy_level", "normal")
            w.setdefault("is_vocal_stressed", False)
        return enriched_words

    try:
        with wave.open(audio_path, "rb") as wf:
            n_channels = wf.getnchannels()
            sampwidth = wf.getsampwidth()
            framerate = wf.getframerate()
            total_frames = wf.getnframes()

            if sampwidth != 2:
                logger.warning("Format audio bukan 16-bit PCM (sampwidth=%s), fallback ke normal.", sampwidth)
                for w in enriched_words:
                    w["scale_multiplier"] = 1.0
                    w["energy_level"] = "normal"
                    w["is_vocal_stressed"] = False
                return enriched_words

            # Hitung rentang klip dalam frame audio
            clip_start_frame = max(0, int(clip_start * framerate))
            clip_end_frame = min(total_frames, int(clip_end * framerate))
            frames_to_read = max(0, clip_end_frame - clip_start_frame)

            if frames_to_read == 0:
                for w in enriched_words:
                    w["scale_multiplier"] = 1.0
                    w["energy_level"] = "normal"
                    w["is_vocal_stressed"] = False
                return enriched_words

            # Posisikan pointer dan baca seluruh sampel audio klip
            wf.setpos(clip_start_frame)
            raw_data = wf.readframes(frames_to_read)

            # Muat raw bytes ke array 16-bit signed integer
            all_samples = array.array("h")
            all_samples.frombytes(raw_data)

            # Jika audio stereo, gabungkan kanal menjadi mono
            if n_channels == 2:
                mono_samples = array.array("h")
                for i in range(0, len(all_samples) - 1, 2):
                    avg_sample = (int(all_samples[i]) + int(all_samples[i + 1])) // 2
                    mono_samples.append(avg_sample)
                samples_pool = mono_samples
            else:
                samples_pool = all_samples

            pool_len = len(samples_pool)

            # Hitung RMS untuk tiap kata
            word_rms_list = []
            for w in enriched_words:
                w_start = float(w.get("start", 0.0))
                w_end = float(w.get("end", 0.0))

                # Relatif terhadap awal klip
                rel_start = max(0.0, w_start - clip_start)
                rel_end = max(rel_start + 0.05, w_end - clip_start)

                start_idx = max(0, int(rel_start * framerate))
                end_idx = min(pool_len, int(rel_end * framerate))

                if end_idx > start_idx and start_idx < pool_len:
                    word_slice = samples_pool[start_idx:end_idx]
                    rms = compute_audio_rms_for_samples(word_slice)
                else:
                    rms = 0.0

                w["_rms"] = rms
                if rms > 50.0:  # Abaikan keheningan total / background hiss
                    word_rms_list.append(rms)

            # Hitung baseline rata-rata energi vokal klip
            if word_rms_list:
                mean_rms = sum(word_rms_list) / len(word_rms_list)
            else:
                mean_rms = 1000.0

            # Berikan bobot dan skala dinamis berdasarkan energi relatif
            for w in enriched_words:
                rms = w.pop("_rms", 0.0)
                ratio = rms / max(1.0, mean_rms)
                w["energy_ratio"] = round(ratio, 2)

                if ratio >= 1.28:
                    # Penekanan kuat / intonasi emosional tinggi
                    scale_mult = min(1.35, 1.15 + (ratio - 1.28) * 0.35)
                    w["scale_multiplier"] = round(scale_mult, 2)
                    w["energy_level"] = "high"
                    w["is_vocal_stressed"] = True
                elif ratio <= 0.72 and rms > 0.0:
                    # Suara mengecil / bisikan / intonasi rendah
                    scale_mult = max(0.88, 0.95 - (0.72 - ratio) * 0.25)
                    w["scale_multiplier"] = round(scale_mult, 2)
                    w["energy_level"] = "low"
                    w["is_vocal_stressed"] = False
                else:
                    w["scale_multiplier"] = 1.0
                    w["energy_level"] = "normal"
                    w["is_vocal_stressed"] = False

    except Exception as exc:
        logger.warning("Gagal menganalisis energi audio (%s): %s", audio_path, exc)
        for w in enriched_words:
            w.setdefault("energy_ratio", 1.0)
            w.setdefault("scale_multiplier", 1.0)
            w.setdefault("energy_level", "normal")
            w.setdefault("is_vocal_stressed", False)

    return enriched_words
