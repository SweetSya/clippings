import json
import re
from typing import List, Dict, Any, Optional
import httpx
from app.config import settings

async def test_llm_connection(
    base_url: str,
    api_key: Optional[str] = None,
    model_name: Optional[str] = "gpt-4o-mini"
) -> Dict[str, Any]:
    """
    Ping LLM API to test connection and verify the model works.
    Returns: {"ok": True, "model": model_name, "message": "..."} or {"ok": False, "error": "..."}
    """
    if not base_url or not base_url.strip():
        return {"ok": False, "error": "Base URL AI belum diisi."}

    url = f"{base_url.rstrip('/')}/chat/completions"
    headers = {"Content-Type": "application/json"}
    if api_key and api_key.strip():
        headers["Authorization"] = f"Bearer {api_key.strip()}"

    payload = {
        "model": model_name or "gpt-4o-mini",
        "messages": [
            {"role": "user", "content": "Ping test. Please reply with only 'OK'."}
        ],
        "max_tokens": 10,
        "temperature": 0.1
    }

    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            res = await client.post(url, headers=headers, json=payload)
            if res.status_code == 200:
                return {
                    "ok": True,
                    "model": model_name,
                    "message": f"Koneksi berhasil! Model '{model_name}' merespon dengan baik."
                }
            else:
                err_text = res.text[:250]
                return {
                    "ok": False,
                    "error": f"API mengembalikan status HTTP {res.status_code}: {err_text}"
                }
    except Exception as e:
        return {"ok": False, "error": f"Gagal terhubung ke {url}: {str(e)}"}

DEFAULT_SYSTEM_PROMPT = """Kamu adalah kurator video profesional kelas dunia yang ahli menyaring momen emas berviralitas tinggi untuk format vertikal TikTok, Instagram Reels, dan YouTube Shorts.

PENDEKATAN KURASI DUA LAPIS (TWO-TIER CONTEXT):
1. KONTEKS BESAR (Macro-Context):
   Pelajari Judul Video, Deskripsi Video, dan Gambaran Seluruh Teks Extracted. Pahami pesan sentral dan tujuan pembicara. Pastikan setiap klip yang dipilih memiliki RELEVANSI TEMATIK KUAT dengan topik utama video (eliminasi basa-basi pembuka, sponsor, atau obrolan santai yang tidak relevan).

2. KONTEKS KECIL (Micro-Context):
   Gunakan segmen stempel waktu untuk memotong klip dengan durasi {min_dur} sampai {max_dur} detik secara presisi tanpa memotong kalimat di tengah-tengah.
   - Kalimat pembuka klip HARUS berupa 'Hook' kuat yang langsung memicu rasa penasaran penonton dalam 3 detik pertama.
   - Setiap klip harus menjadi gagasan yang utuh dan memuaskan penonton.

FORMAT JAWABAN:
Balas HANYA dengan array JSON yang valid, TANPA format markdown block (tanpa ```json), TANPA salam pembuka atau penjelasan tambahan.

[
  {
    "title": "Judul klip singkat, padat & memikat (maksimal 80 karakter)",
    "start_time_seconds": 12.5,
    "end_time_seconds": 58.2,
    "hook_score": 92,
    "virality_reason": "Pernyataan kontroversial di awal langsung memicu rasa ingin tahu penonton."
  }
]"""

def format_transcript_for_llm(segments: List[Dict[str, Any]], max_chars: int = 24000) -> str:
    lines = []
    for s in segments:
        start = s.get("start", 0.0)
        end = s.get("end", 0.0)
        text = s.get("text", "").strip()
        lines.append(f"[{start:.1f}s - {end:.1f}s] {text}")
    
    full_str = "\n".join(lines)
    if len(full_str) <= max_chars:
        return full_str
        
    half = max_chars // 2 - 50
    return full_str[:half] + "\n\n...[omitted middle content]...\n\n" + full_str[-half:]

def sanitize_and_parse_json(content: str) -> List[Dict[str, Any]]:
    # 1. Remove markdown backticks
    cleaned = re.sub(r"^```(?:json)?", "", content.strip(), flags=re.IGNORECASE)
    cleaned = re.sub(r"```$", "", cleaned.strip())
    cleaned = cleaned.strip()

    # 2. Find bracket matching array
    start_bracket = cleaned.find("[")
    end_bracket = cleaned.rfind("]")
    if start_bracket != -1 and end_bracket != -1:
        cleaned = cleaned[start_bracket:end_bracket + 1]

    data = json.loads(cleaned)
    if not isinstance(data, list):
        raise ValueError("Response is not a JSON list")
    return data

def validate_and_filter_candidates(
    candidates: List[Dict[str, Any]],
    video_duration: float,
    min_dur: float,
    max_dur: float
) -> List[Dict[str, Any]]:
    valid = []
    for item in candidates:
        try:
            start = float(item.get("start_time_seconds", 0.0))
            end = float(item.get("end_time_seconds", 0.0))
            dur = end - start
            title = str(item.get("title", "")).strip()[:100]
            reason = str(item.get("virality_reason", "")).strip()
            score = int(item.get("hook_score", 50))
            score = max(0, min(100, score))

            if start < 0 or start >= end or end > video_duration + 2.0:
                continue
            if dur < min_dur or dur > max_dur:
                continue
            if not title:
                title = f"Highlight {int(start)}s - {int(end)}s"

            valid.append({
                "title": title,
                "start_time_seconds": round(start, 2),
                "end_time_seconds": round(min(end, video_duration), 2),
                "duration_seconds": round(min(end, video_duration) - start, 2),
                "hook_score": score,
                "virality_reason": reason or "Momen penting dan berpotensi tinggi."
            })
        except Exception:
            continue

    # Sort descending by hook score
    valid.sort(key=lambda x: x["hook_score"], reverse=True)

    # Overlap suppression (>50%)
    non_overlapping = []
    for cand in valid:
        c_start = cand["start_time_seconds"]
        c_end = cand["end_time_seconds"]
        c_len = cand["duration_seconds"]

        overlaps = False
        for selected in non_overlapping:
            s_start = selected["start_time_seconds"]
            s_end = selected["end_time_seconds"]
            s_len = selected["duration_seconds"]

            inter_start = max(c_start, s_start)
            inter_end = min(c_end, s_end)
            intersection = max(0.0, inter_end - inter_start)

            if intersection / min(c_len, s_len) > 0.5:
                overlaps = True
                break
        if not overlaps:
            non_overlapping.append(cand)

    return non_overlapping[:5]

def generate_heuristic_highlights(
    segments: List[Dict[str, Any]],
    video_duration: float,
    min_dur: float = 15.0,
    max_dur: float = 60.0
) -> List[Dict[str, Any]]:
    """
    Intelligent rule-based fallback when LLM is not configured or unavailable.
    Finds natural segments with high speech density and engagement.
    """
    if not segments or video_duration < min_dur:
        # Single clip fallback
        end = min(video_duration, max_dur)
        return [{
            "title": "Momen Utama Video",
            "start_time_seconds": 0.0,
            "end_time_seconds": round(end, 2),
            "duration_seconds": round(end, 2),
            "hook_score": 85,
            "virality_reason": "Ringkasan pembuka video penuh dengan informasi inti."
        }]

    # Slice video into 3-5 windows
    target_clips = 3
    if video_duration > 180:
        target_clips = 4
    if video_duration > 300:
        target_clips = 5

    step = max(30.0, video_duration / (target_clips + 1))
    highlights = []

    for i in range(target_clips):
        window_center = (i + 1) * step
        # Find segment nearest to window_center
        matching_segs = [s for s in segments if abs(s.get("start", 0.0) - window_center) < step * 0.8]
        if not matching_segs:
            continue

        start_seg = matching_segs[0]
        c_start = start_seg.get("start", 0.0)
        c_end = c_start

        clip_words = []
        for s in segments:
            if s.get("start", 0.0) >= c_start:
                c_end = s.get("end", c_end)
                clip_words.append(s.get("text", ""))
                if (c_end - c_start) >= min_dur:
                    break

        dur = c_end - c_start
        if dur > max_dur:
            c_end = c_start + max_dur
            dur = max_dur

        first_sentence = clip_words[0].strip() if clip_words else f"Highlight Bagian {i+1}"
        title = first_sentence[:60] if len(first_sentence) > 10 else f"Momen Menarik #{i+1}"
        if not title.endswith((".", "!", "?")):
            title += "..."

        score = 80 + (i % 3) * 5
        highlights.append({
            "title": title,
            "start_time_seconds": round(c_start, 2),
            "end_time_seconds": round(c_end, 2),
            "duration_seconds": round(dur, 2),
            "hook_score": score,
            "virality_reason": f"Kutipan menarik dan pembahasan fokus pada bagian menit {int(c_start//60)}:{int(c_start%60):02d}."
        })

    return highlights[:5]

async def extract_highlights_with_llm(
    segments: List[Dict[str, Any]],
    video_duration: float,
    video_title: str = "Video Tanpa Judul",
    video_description: Optional[str] = None,
    full_text: Optional[str] = None,
    llm_base_url: Optional[str] = None,
    llm_api_key: Optional[str] = None,
    llm_model: Optional[str] = "gpt-4o-mini",
    temperature: float = 0.4,
    custom_prompt: Optional[str] = None,
    min_dur: Optional[float] = None,
    max_dur: Optional[float] = None
) -> List[Dict[str, Any]]:
    """
    Call LLM API with exponential retry (3 attempts).
    Leverages two-tier context:
    - Konteks Besar (Macro): video_title, video_description, and full_text to understand the overarching theme.
    - Konteks Kecil (Micro): timestamped segments to accurately pinpoint viral hooks.
    Falls back to intelligent heuristic extractor if LLM is not provided or fails.
    """
    effective_min = float(min_dur) if min_dur is not None else float(settings.MIN_CLIP_SECONDS)
    effective_max = float(max_dur) if max_dur is not None else float(settings.MAX_CLIP_SECONDS)

    if not llm_base_url:
        return generate_heuristic_highlights(segments, video_duration, effective_min, effective_max)

    # 1. Format Konteks Besar (Macro overview)
    macro_text = full_text or " ".join(s.get("text", "").strip() for s in segments)
    if len(macro_text) > 8000:
        macro_text = macro_text[:4000] + "\n...[ringkasan alur tengah]...\n" + macro_text[-4000:]

    # 2. Format Konteks Kecil (Micro timestamped segments)
    micro_transcript = format_transcript_for_llm(segments)

    system_instruction = custom_prompt or DEFAULT_SYSTEM_PROMPT
    system_instruction = system_instruction.replace("{min_dur}", str(int(effective_min)))\
                                           .replace("{max_dur}", str(int(effective_max)))

    user_content = f"""=== [KONTEKS BESAR / MACRO CONTEXT] ===
Judul Video: {video_title}
Deskripsi Video: {video_description or '(Tidak ada deskripsi tambahan)'}

Seluruh Teks Extracted (Tema & Alur Keseluruhan):
{macro_text}

=== [KONTEKS KECIL / MICRO SEGMENTS & TIMESTAMPS] ===
Analisis segmen berstempel waktu di bawah ini. Pilih 3 sampai 5 klip terbaik yang RELEVAN dengan Konteks Besar di atas dan memiliki durasi {int(effective_min)} sampai {int(effective_max)} detik:
{micro_transcript}
"""

    headers = {"Content-Type": "application/json"}
    if llm_api_key:
        headers["Authorization"] = f"Bearer {llm_api_key}"

    payload = {
        "model": llm_model or "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": user_content}
        ],
        "temperature": temperature
    }

    url = f"{llm_base_url.rstrip('/')}/chat/completions"
    delays = [2.0, 4.0, 8.0]

    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=45.0) as client:
                res = await client.post(url, headers=headers, json=payload)
                if res.status_code == 200:
                    data = res.json()
                    content = data["choices"][0]["message"]["content"]
                    parsed = sanitize_and_parse_json(content)
                    valid_candidates = validate_and_filter_candidates(parsed, video_duration, min_dur, max_dur)
                    if valid_candidates:
                        return valid_candidates
        except Exception:
            pass
        if attempt < 2:
            import asyncio
            await asyncio.sleep(delays[attempt])

    # Fallback if LLM failed
    return generate_heuristic_highlights(segments, video_duration, min_dur, max_dur)

async def generate_clip_narration(
    macro_title: str,
    macro_description: Optional[str],
    macro_full_text: str,
    clip_text: str,
    clip_duration_seconds: float,
    llm_base_url: Optional[str] = None,
    llm_api_key: Optional[str] = None,
    llm_model: Optional[str] = "gpt-4o-mini",
    style: str = "hook_story"
) -> str:
    """
    Compare macro context (video title, description, full transcript) with micro context
    (clip transcript text at specific minutes) to generate a concise, hook-driven voiceover narration script.
    """
    word_budget = max(20, min(120, int(clip_duration_seconds * 2.5)))

    style_instruction = "Gunakan gaya storytelling yang menggugah emosi dan rasa penasaran penonton."
    if style == "summary":
        style_instruction = "Gunakan gaya rangkuman cepat, padat, dan to-the-point."
    elif style == "educational":
        style_instruction = "Gunakan gaya edukatif, lugas, dan mudah dimengerti khalayak umum."

    system_prompt = f"""Kamu adalah copywriter & voiceover master video pendek (TikTok, Reels, YouTube Shorts).
TUGAS UTAMA:
Bandingkan KONTEKS BESAR video (Judul, deskripsi, tema sentral) dengan TEKS SPESIFIK klip pada menit tersebut.
Ciptakan 1 narasi suara (voiceover script) dalam Bahasa Indonesia alami yang:
1. Mengandung 'Hook' kuat di kalimat pembuka (3 detik pertama) yang langsung memancing rasa ingin tahu.
2. Membantu penonton memahami konteks dan intisari yang sedang dibahas pembicara tanpa bertele-tele.
3. Menyesuaikan panjang teks dengan target sekitar {word_budget} kata.
4. {style_instruction}

PENTING:
Keluarkan HANYA teks narasi yang siap dibaca oleh voice generator. DILARANG menyertakan timestamp, tanda kurung panggung, atau salam pembuka."""

    user_prompt = f"""[KONTEKS BESAR VIDEO]
Judul: {macro_title}
Deskripsi: {macro_description or '-'}
Gambaran Isi Video: {macro_full_text[:4000]}

[KONTEKS KECIL / TEKS DI MENIT KLIP INI ({clip_duration_seconds:.1f} detik)]
{clip_text}

Buatkan narasi voiceover yang selaras dengan kedua konteks di atas (maksimal ~{word_budget} kata):"""

    if not llm_base_url:
        sentences = [s.strip() for s in clip_text.split(".") if len(s.strip()) > 10]
        if sentences:
            return f"Di momen ini: {sentences[0]}. Simak bagaimana pembahasannya berlanjut!"
        return f"Momen menarik dari {macro_title}. Dengarkan pembahasan penting berikut!"

    headers = {"Content-Type": "application/json"}
    if llm_api_key:
        headers["Authorization"] = f"Bearer {llm_api_key}"

    payload = {
        "model": llm_model or "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.7
    }

    url = f"{llm_base_url.rstrip('/')}/chat/completions"
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            res = await client.post(url, headers=headers, json=payload)
            if res.status_code == 200:
                data = res.json()
                text = data["choices"][0]["message"]["content"].strip()
                text = re.sub(r'^["\']|["\']$', '', text).strip()
                return text
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Failed to generate narration with LLM: {e}")

    return f"Di momen menarik ini: {clip_text[:140]}..."
