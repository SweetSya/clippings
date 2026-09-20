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

from app.services.video_type_service import build_video_types_prompt_guide, get_video_type_by_id
from app.services.ass_service import is_keyword

# Bobot composite hook scoring (Phase 2 — 1.3). Jumlah = 1.0.
COMPOSITE_WEIGHT_LLM = 0.4
COMPOSITE_WEIGHT_SPEECH_RATE = 0.2
COMPOSITE_WEIGHT_KEYWORD = 0.2
COMPOSITE_WEIGHT_HOOK_POSITION = 0.2
# Window detik awal klip untuk penilaian kualitas hook + ambang densitas keyword.
HOOK_WINDOW_SECONDS = 3.0
KEYWORD_DENSITY_SATURATION = 0.15
HOOK_POSITION_HIT_SCORE = 100.0
HOOK_POSITION_MISS_SCORE = 30.0


def _iter_clip_words(
    segments: List[Dict[str, Any]], clip_start: float, clip_end: float
):
    """
    Yield (kata, start_detik) untuk kata dalam window klip.
    Pakai timestamps per-kata bila ada (whisper verbose), else sebar merata per segmen
    (pola yang sama dengan fallback di pipeline.handle_render).
    """
    for seg in segments or []:
        try:
            seg_s = float(seg.get("start", 0.0))
            seg_e = float(seg.get("end", seg_s))
        except (TypeError, ValueError):
            continue
        if seg_e <= clip_start or seg_s >= clip_end:
            continue
        words = seg.get("words") or []
        if words:
            for w in words:
                try:
                    text = str(w.get("word", "")).strip()
                    ws = float(w.get("start", seg_s))
                except (TypeError, ValueError, AttributeError):
                    continue
                if text and clip_start <= ws < clip_end:
                    yield text, ws
        else:
            tokens = str(seg.get("text", "")).strip().split()
            if not tokens:
                continue
            seg_d = max(0.1, seg_e - seg_s)
            w_dur = seg_d / len(tokens)
            for i, tok in enumerate(tokens):
                ws = seg_s + i * w_dur
                if clip_start <= ws < clip_end:
                    yield tok, ws


def compute_speech_rate_score(
    clip_start: float, clip_end: float,
    segments: List[Dict[str, Any]], avg_rate_wps: float,
) -> tuple:
    """
    Return (skor 0-100, rate kata/detik klip).
    Skor dari rasio rate klip vs rata-rata video: rasio 1.0 → 50, ≥1.4 → 100, ≤0.6 → 0.
    Pure function (tanpa I/O).
    """
    dur = max(0.1, clip_end - clip_start)
    words = list(_iter_clip_words(segments, clip_start, clip_end))
    rate = len(words) / dur
    if not words or avg_rate_wps <= 0:
        return 50.0, round(rate, 3)
    ratio = rate / avg_rate_wps
    score = max(0.0, min(1.0, (ratio - 0.6) / 0.8)) * 100.0
    return round(score, 1), round(rate, 3)


def compute_keyword_density_score(
    clip_start: float, clip_end: float, segments: List[Dict[str, Any]],
) -> tuple:
    """
    Return (skor 0-100, densitas 0-1). Jenuh di KEYWORD_DENSITY_SATURATION.
    Pure function (tanpa I/O).
    """
    words = [t for t, _ in _iter_clip_words(segments, clip_start, clip_end)]
    if not words:
        return 0.0, 0.0
    hits = sum(1 for t in words if is_keyword(t))
    density = hits / len(words)
    score = min(1.0, density / KEYWORD_DENSITY_SATURATION) * 100.0
    return round(score, 1), round(density, 4)


def check_hook_position_score(
    clip_start: float, segments: List[Dict[str, Any]],
    window_seconds: float = HOOK_WINDOW_SECONDS,
) -> float:
    """
    100 bila kata kunci muncul dalam `window_seconds` pertama klip, else MISS_SCORE.
    Pure function (tanpa I/O).
    """
    for text, _ in _iter_clip_words(segments, clip_start, clip_start + window_seconds):
        try:
            if is_keyword(text):
                return HOOK_POSITION_HIT_SCORE
        except Exception:
            continue
    return HOOK_POSITION_MISS_SCORE


def compute_composite_score(
    llm_score: float, clip_start: float, clip_end: float,
    segments: List[Dict[str, Any]], avg_rate_wps: float,
) -> Dict[str, float]:
    """
    Gabung skor LLM (40%) + speech rate (20%) + keyword density (20%) + hook position (20%).
    Return {composite_score, speech_rate, keyword_density}. Pure function (tanpa I/O).
    """
    try:
        llm = max(0.0, min(100.0, float(llm_score)))
    except (TypeError, ValueError):
        llm = 50.0
    speech_score, rate = compute_speech_rate_score(clip_start, clip_end, segments, avg_rate_wps)
    kw_score, density = compute_keyword_density_score(clip_start, clip_end, segments)
    hook_score = check_hook_position_score(clip_start, segments)
    composite = (
        llm * COMPOSITE_WEIGHT_LLM
        + speech_score * COMPOSITE_WEIGHT_SPEECH_RATE
        + kw_score * COMPOSITE_WEIGHT_KEYWORD
        + hook_score * COMPOSITE_WEIGHT_HOOK_POSITION
    )
    return {
        "composite_score": int(round(max(0, min(100, composite)))),
        "speech_rate": rate,
        "keyword_density": density,
    }


def _average_speech_rate(segments: List[Dict[str, Any]], video_duration: float) -> float:
    total = sum(len(str(s.get("text", "")).strip().split()) for s in segments or [])
    if total <= 0 or video_duration <= 0:
        return 0.0
    return total / video_duration

class HighlightsList(list):
    """
    Subclass of list holding clip candidates while carrying video_type and recommended_preset_id metadata.
    """
    def __init__(self, iterable=None, video_type: str = "umum", recommended_preset_id: Optional[str] = None):
        super().__init__(iterable or [])
        self.video_type = video_type
        self.recommended_preset_id = recommended_preset_id

DEFAULT_SYSTEM_PROMPT_ID = """Kamu adalah kurator & editor video profesional kelas dunia yang ahli menyaring momen emas berviralitas tinggi untuk format vertikal TikTok, Instagram Reels, dan YouTube Shorts.

PENDEKATAN DUA LAPIS (TWO-TIER CONTEXT):
1. KONTEKS BESAR (Macro-Context):
   - Pelajari Judul Video, Deskripsi Video (dari metadata yt-dlp/sumber), dan Gambaran Seluruh Transkrip.
   - Pahami tema sentral, topik bahasan, dan klasifikasikan TIPE/GENRE video tersebut.
   - Gunakan panduan kurasi khusus sesuai tipe video untuk menentukan bagian mana yang wajib diambil.

2. KONTEKS KECIL (Micro-Context):
   - Gunakan segmen stempel waktu untuk memotong klip dengan durasi {min_dur} sampai {max_dur} detik secara presisi tanpa memotong kalimat di tengah-tengah.
   - Kalimat pembuka klip HARUS berupa 'Hook' kuat yang langsung memicu rasa penasaran penonton dalam 3 detik pertama.
   - Setiap klip harus menjadi gagasan yang utuh dan memuaskan penonton.
   - Cari dan hasilkan hingga 10 klip terbaik (jika memang ada banyak momen menarik, hasilkan 5-10 klip; maksimal 10 klip).

FORMAT JAWABAN:
Balas HANYA dengan JSON Object yang valid, TANPA format markdown block (tanpa ```json), TANPA salam pembuka atau penjelasan tambahan.

{
  "video_type": "id_tipe_yang_sesuai",
  "recommended_preset_id": "id_preset_sesuai_tipe",
  "summary": "Ringkasan 1-2 kalimat konteks besar video",
  "clips": [
    {
      "title": "Judul klip singkat, padat & memikat (maksimal 80 karakter)",
      "start_time_seconds": 12.5,
      "end_time_seconds": 58.2,
      "hook_score": 92,
      "virality_reason": "Pernyataan kontroversial di awal langsung memicu rasa ingin tahu penonton."
    }
  ]
}"""

DEFAULT_SYSTEM_PROMPT_EN = """You are a world-class professional video curator & editor specializing in extracting high-virality golden moments for vertical formats: TikTok, Instagram Reels, and YouTube Shorts.

TWO-TIER CONTEXT APPROACH:
1. MACRO CONTEXT:
   - Study the Video Title, Video Description (from yt-dlp/source metadata), and the Full Transcript Overview.
   - Understand the central theme, discussion topics, and classify the video TYPE/GENRE.
   - Use genre-specific curation guidelines to determine which sections must be captured.

2. MICRO CONTEXT:
   - Use timestamped segments to cut clips with duration {min_dur} to {max_dur} seconds precisely without cutting sentences mid-way.
   - The opening sentence of each clip MUST be a strong 'Hook' that immediately triggers viewer curiosity within the first 3 seconds.
   - Each clip must be a complete, satisfying idea for the viewer.
   - Find and generate up to 10 best clips (if there are many interesting moments, generate 5-10 clips; maximum 10 clips).

IMPORTANT: ALL generated text (title, virality_reason, summary) MUST be in English.

RESPONSE FORMAT:
Reply ONLY with a valid JSON Object, WITHOUT markdown code blocks (no ```json), WITHOUT greetings or additional explanations.

{
  "video_type": "matching_type_id",
  "recommended_preset_id": "preset_id_for_type",
  "summary": "1-2 sentence summary of the video macro context",
  "clips": [
    {
      "title": "Short, catchy & compelling clip title (max 80 characters)",
      "start_time_seconds": 12.5,
      "end_time_seconds": 58.2,
      "hook_score": 92,
      "virality_reason": "Controversial statement at the start immediately triggers viewer curiosity."
    }
  ]
}"""

# Keep backward compat alias
DEFAULT_SYSTEM_PROMPT = DEFAULT_SYSTEM_PROMPT_ID


def get_system_prompt(language: str = "id") -> str:
    """Return language-appropriate system prompt for LLM clip extraction."""
    if language and language.lower().startswith("en"):
        return DEFAULT_SYSTEM_PROMPT_EN
    return DEFAULT_SYSTEM_PROMPT_ID

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

def sanitize_and_parse_json(content: str) -> Dict[str, Any]:
    # 1. Remove markdown backticks
    cleaned = re.sub(r"^```(?:json)?", "", content.strip(), flags=re.IGNORECASE)
    cleaned = re.sub(r"```$", "", cleaned.strip())
    cleaned = cleaned.strip()

    # 2. Try JSON Object matching {...}
    start_obj = cleaned.find("{")
    end_obj = cleaned.rfind("}")
    if start_obj != -1 and end_obj != -1 and end_obj > start_obj:
        try:
            data = json.loads(cleaned[start_obj:end_obj + 1])
            if isinstance(data, dict):
                return data
        except Exception:
            pass

    # 3. Try JSON Array matching [...]
    start_bracket = cleaned.find("[")
    end_bracket = cleaned.rfind("]")
    if start_bracket != -1 and end_bracket != -1 and end_bracket > start_bracket:
        data = json.loads(cleaned[start_bracket:end_bracket + 1])
        if isinstance(data, list):
            return {"clips": data}

    data = json.loads(cleaned)
    if isinstance(data, list):
        return {"clips": data}
    if isinstance(data, dict):
        return data
    raise ValueError("Response is not a valid JSON list or object")

def validate_and_filter_candidates(
    candidates: List[Dict[str, Any]],
    video_duration: float,
    min_dur: float,
    max_dur: float,
    max_count: int = 10,
    segments: Optional[List[Dict[str, Any]]] = None,
    vision_boost: Optional[Dict[float, float]] = None,
    vision_weight: float = 0.3
) -> List[Dict[str, Any]]:
    valid = []
    for item in candidates:
        try:
            start_val = item.get("start_time_seconds") if item.get("start_time_seconds") is not None else item.get("start_time", 0.0)
            end_val = item.get("end_time_seconds") if item.get("end_time_seconds") is not None else item.get("end_time", 0.0)
            start = float(start_val)
            end = float(end_val)
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

    # Re-scoring komposit: sinyal lokal objektif menambal bias skor LLM.
    # Tanpa segments → perilaku lama (hook_score apa adanya) agar caller lama/tes tetap kompatibel.
    avg_rate = _average_speech_rate(segments, video_duration) if segments else 0.0
    for cand in valid:
        if segments:
            try:
                rescored = compute_composite_score(
                    cand["hook_score"],
                    cand["start_time_seconds"],
                    cand["end_time_seconds"],
                    segments,
                    avg_rate,
                )
                cand.update(rescored)
            except Exception:
                cand.update({"composite_score": cand["hook_score"], "speech_rate": 0.0, "keyword_density": 0.0})
        else:
            cand.update({"composite_score": cand["hook_score"], "speech_rate": 0.0, "keyword_density": 0.0})

    # Vision boost (Phase 4 — 2.1): kandidat yang merentang momen visual menonjol
    # naik sebesar visual_score * weight (dibatasi 100). Tanpa boost → tak berubah.
    if vision_boost:
        try:
            weight = max(0.0, min(1.0, float(vision_weight)))
        except (TypeError, ValueError):
            weight = 0.3
        if weight > 0:
            for cand in valid:
                try:
                    c_start = float(cand["start_time_seconds"])
                    c_end = float(cand["end_time_seconds"])
                    peak = max(
                        (score for ts, score in vision_boost.items()
                         if c_start <= float(ts) <= c_end),
                        default=0.0,
                    )
                    if peak > 0:
                        cand["composite_score"] = int(min(
                            100, cand.get("composite_score", cand["hook_score"]) + round(peak * weight)))
                except (TypeError, ValueError, AttributeError):
                    continue

    # Sort descending by composite score (fallback hook_score bila seri/nol)
    valid.sort(key=lambda x: (x.get("composite_score", x["hook_score"]), x["hook_score"]), reverse=True)

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

    return non_overlapping[:max_count]

def generate_heuristic_highlights(
    segments: List[Dict[str, Any]],
    video_duration: float,
    min_dur: float = 15.0,
    max_dur: float = 60.0,
    max_count: int = 10,
    language: str = "id",
) -> HighlightsList:
    """
    Intelligent rule-based fallback when LLM is not configured or unavailable.
    Finds natural segments with high speech density and engagement (up to 10 clips).
    """
    is_en = language and language.lower().startswith("en")
    if not segments or video_duration < min_dur:
        end = min(video_duration, max_dur)
        return HighlightsList([{
            "title": "Main Video Moment" if is_en else "Momen Utama Video",
            "start_time_seconds": 0.0,
            "end_time_seconds": round(end, 2),
            "duration_seconds": round(end, 2),
            "hook_score": 85,
            "virality_reason": "Opening summary packed with core information." if is_en else "Ringkasan pembuka video penuh dengan informasi inti."
        }], video_type="umum", recommended_preset_id="preset_tiktok_bold")

    # Slice video into 3-10 windows depending on duration
    target_clips = min(max_count, max(3, int(video_duration // 60)))
    step = max(20.0, video_duration / (target_clips + 1))
    highlights = []

    for i in range(target_clips):
        window_center = (i + 1) * step
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

        first_sentence = clip_words[0].strip() if clip_words else (f"Highlight Part {i+1}" if is_en else f"Highlight Bagian {i+1}")
        title = first_sentence[:60] if len(first_sentence) > 10 else (f"Interesting Moment #{i+1}" if is_en else f"Momen Menarik #{i+1}")
        if not title.endswith((".", "!", "?")):
            title += "..."

        score = 80 + (i % 3) * 5
        reason_prefix = "Interesting quote and focused discussion at" if is_en else "Kutipan menarik dan pembahasan fokus pada bagian"
        highlights.append({
            "title": title,
            "start_time_seconds": round(c_start, 2),
            "end_time_seconds": round(c_end, 2),
            "duration_seconds": round(dur, 2),
            "hook_score": score,
            "virality_reason": f"{reason_prefix} {int(c_start//60)}:{int(c_start%60):02d}."
        })

    return HighlightsList(highlights[:max_count], video_type="umum", recommended_preset_id="preset_tiktok_bold")

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
    max_dur: Optional[float] = None,
    vision_boost: Optional[Dict[float, float]] = None,
    vision_weight: float = 0.3,
    language: str = "id",
) -> HighlightsList:
    """
    Call LLM API with exponential retry (3 attempts).
    Leverages two-tier context:
    - Konteks Besar (Macro): video_title, video_description, full_text, and Video Types Taxonomy.
    - Konteks Kecil (Micro): timestamped segments to accurately pinpoint viral hooks (up to 10 clips).
    Falls back to intelligent heuristic extractor if LLM is not provided or fails.
    """
    effective_min = float(min_dur) if min_dur is not None else float(settings.MIN_CLIP_SECONDS)
    effective_max = float(max_dur) if max_dur is not None else float(settings.MAX_CLIP_SECONDS)

    if not llm_base_url:
        return generate_heuristic_highlights(segments, video_duration, effective_min, effective_max, language=language)

    is_en = language and language.lower().startswith("en")

    # 1. Format Konteks Besar (Macro overview)
    macro_text = full_text or " ".join(s.get("text", "").strip() for s in segments)
    if len(macro_text) > 8000:
        mid_label = "...[middle summary omitted]..." if is_en else "\n...[ringkasan alur tengah]...\n"
        macro_text = macro_text[:4000] + mid_label + macro_text[-4000:]

    # 2. Format Konteks Kecil (Micro timestamped segments)
    micro_transcript = format_transcript_for_llm(segments)

    # 3. Video Types Taxonomy Guide
    types_guide = build_video_types_prompt_guide()

    system_instruction = custom_prompt or get_system_prompt(language)
    system_instruction = system_instruction.replace("{min_dur}", str(int(effective_min)))\
                                           .replace("{max_dur}", str(int(effective_max)))

    if is_en:
        no_desc = "(No additional description)"
        user_content = f"""=== [VIDEO TYPE/GENRE TAXONOMY & CURATION GUIDE] ===
{types_guide}

=== [MACRO CONTEXT] ===
Video Title: {video_title}
Video Description (Metadata): {video_description or no_desc}

Full Extracted Text (Theme & Overall Flow):
{macro_text}

=== [MICRO SEGMENTS & TIMESTAMPS] ===
Analyze the timestamped segments below.
1. Determine the most fitting VIDEO TYPE/GENRE from the taxonomy above.
2. Select 3 to 10 best clips RELEVANT to the Macro Context and the genre curation guide, with duration {int(effective_min)} to {int(effective_max)} seconds:
{micro_transcript}
"""
    else:
        user_content = f"""=== [TAKSONOMI TIPE/GENRE VIDEO & PANDUAN KURASI] ===
{types_guide}

=== [KONTEKS BESAR / MACRO CONTEXT] ===
Judul Video: {video_title}
Deskripsi Video (Metadata): {video_description or '(Tidak ada deskripsi tambahan)'}

Seluruh Teks Extracted (Tema & Alur Keseluruhan):
{macro_text}

=== [KONTEKS KECIL / MICRO SEGMENTS & TIMESTAMPS] ===
Analisis segmen berstempel waktu di bawah ini.
1. Tentukan TIPE/GENRE video yang paling cocok dari taksonomi di atas.
2. Pilih 3 sampai 10 klip terbaik yang RELEVAN dengan Konteks Besar dan panduan kurasi tipe tersebut, dengan durasi {int(effective_min)} sampai {int(effective_max)} detik:
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
                    raw_clips = (parsed.get("clips") or parsed.get("highlights") or parsed.get("candidates") or []) if isinstance(parsed, dict) else (parsed if isinstance(parsed, list) else [])
                    detected_type = parsed.get("video_type", "umum") if isinstance(parsed, dict) else "umum"
                    rec_preset = parsed.get("recommended_preset_id") if isinstance(parsed, dict) else None
                    if not rec_preset:
                        vt = get_video_type_by_id(detected_type)
                        rec_preset = vt.get("recommended_preset_id") if vt else "preset_tiktok_bold"

                    valid_candidates = validate_and_filter_candidates(raw_clips, video_duration, effective_min, effective_max, max_count=10, segments=segments, vision_boost=vision_boost, vision_weight=vision_weight)
                    if valid_candidates:
                        return HighlightsList(valid_candidates, video_type=detected_type, recommended_preset_id=rec_preset)
        except Exception:
            pass
        if attempt < 2:
            import asyncio
            await asyncio.sleep(delays[attempt])

    # Fallback if LLM failed
    return generate_heuristic_highlights(segments, video_duration, effective_min, effective_max, language=language)

EDITORIAL_BRIEF_SYSTEM = """Kamu adalah editor-in-chief video pendek (TikTok, Reels, YouTube Shorts).
Tugasmu: baca metadata + seluruh isi video, lalu susun EDITORIAL BRIEF untuk editor klip.

Balas HANYA dengan JSON Object yang valid, TANPA markdown block, TANPA penjelasan tambahan:
{
  "video_type": "id_tipe_yang_sesuai",
  "theme_summary": "Ringkasan 1-2 kalimat tema sentral video",
  "must_avoid_topics": ["sponsor", "intro basa-basi", "topik tidak relevan", "..."],
  "must_include_topics": ["topik wajib diambil", "..."],
  "tone": "gaya bahasa video (mis. santai, formal, meledak-ledak)"
}"""

EDITORIAL_BRIEF_SYSTEM_EN = """You are the editor-in-chief for short-form video (TikTok, Reels, YouTube Shorts).
Your task: read the metadata + full video content, then compose an EDITORIAL BRIEF for the clip editor.

IMPORTANT: Write ALL text in English since the video content is in English.

Reply ONLY with a valid JSON Object, WITHOUT markdown blocks, WITHOUT additional explanations:
{
  "video_type": "matching_type_id",
  "theme_summary": "1-2 sentence summary of the central video theme",
  "must_avoid_topics": ["sponsor", "filler intro", "irrelevant topics", "..."],
  "must_include_topics": ["must-capture topics", "..."],
  "tone": "video tone (e.g. casual, formal, energetic)"
}"""


def get_editorial_brief_system(language: str = "id") -> str:
    """Return language-appropriate editorial brief system prompt."""
    if language and language.lower().startswith("en"):
        return EDITORIAL_BRIEF_SYSTEM_EN
    return EDITORIAL_BRIEF_SYSTEM



async def _post_chat(
    llm_base_url: str,
    llm_api_key: Optional[str],
    llm_model: Optional[str],
    messages: List[Dict[str, str]],
    temperature: float,
    timeout_seconds: float = 45.0,
) -> str:
    """Satu panggilan chat/completions. Kembalikan isi pesan atau raise."""
    headers = {"Content-Type": "application/json"}
    if llm_api_key:
        headers["Authorization"] = f"Bearer {llm_api_key}"
    payload = {
        "model": llm_model or "gpt-4o-mini",
        "messages": messages,
        "temperature": temperature,
    }
    url = f"{llm_base_url.rstrip('/')}/chat/completions"
    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        res = await client.post(url, headers=headers, json=payload)
        if res.status_code != 200:
            raise ValueError(f"LLM HTTP {res.status_code}: {res.text[:200]}")
        return res.json()["choices"][0]["message"]["content"]


async def _request_editorial_brief(
    llm_base_url: str,
    llm_api_key: Optional[str],
    llm_model: Optional[str],
    video_title: str,
    video_description: Optional[str],
    macro_text: str,
    types_guide: str,
    language: str = "id",
) -> Optional[Dict[str, Any]]:
    """Pass 1 Macro Analysis → brief dict atau None bila gagal (2x retry, 45s per call)."""
    is_en = language and language.lower().startswith("en")
    if is_en:
        pass1_user = f"""=== [VIDEO TYPE/GENRE TAXONOMY] ===
{types_guide}

=== [VIDEO METADATA] ===
Title: {video_title}
Description: {video_description or '(No additional description)'}

=== [FULL VIDEO CONTENT] ===
{macro_text}

Compose an EDITORIAL BRIEF according to the requested JSON format."""
    else:
        pass1_user = f"""=== [TAKSONOMI TIPE/GENRE VIDEO] ===
{types_guide}

=== [METADATA VIDEO] ===
Judul: {video_title}
Deskripsi: {video_description or '(Tidak ada deskripsi tambahan)'}

=== [SELURUH ISI VIDEO] ===
{macro_text}

Susun EDITORIAL BRIEF sesuai format JSON yang diminta."""
    brief_system = get_editorial_brief_system(language)
    for attempt in range(2):
        try:
            content = await _post_chat(
                llm_base_url, llm_api_key, llm_model,
                [{"role": "system", "content": brief_system},
                 {"role": "user", "content": pass1_user}],
                temperature=0.3,
            )
            parsed = sanitize_and_parse_json(content)
            if isinstance(parsed, dict) and parsed.get("theme_summary"):
                brief = {
                    "video_type": str(parsed.get("video_type") or "umum"),
                    "theme_summary": str(parsed.get("theme_summary", ""))[:500],
                    "must_avoid_topics": list(parsed.get("must_avoid_topics") or [])[:10],
                    "must_include_topics": list(parsed.get("must_include_topics") or [])[:10],
                    "tone": str(parsed.get("tone") or "-"),
                }
                if not get_video_type_by_id(brief["video_type"]):
                    brief["video_type"] = "umum"
                return brief
        except Exception:
            pass
        if attempt < 1:
            import asyncio
            await asyncio.sleep(2.0)
    return None


def _build_micro_system(
    custom_prompt: Optional[str],
    effective_min: float,
    effective_max: float,
    brief: Optional[Dict[str, Any]] = None,
    language: str = "id",
) -> str:
    """Susun system prompt micro-selection; brief Pass 1 ditempel bila ada."""
    import json as _json
    base_system = custom_prompt or get_system_prompt(language)
    base_system = base_system.replace("{min_dur}", str(int(effective_min)))\
                             .replace("{max_dur}", str(int(effective_max)))
    is_en = language and language.lower().startswith("en")
    if brief:
        if is_en:
            base_system += (
                "\n\n=== [EDITORIAL BRIEF — PASS 1 ANALYSIS RESULT, MUST BE FOLLOWED] ===\n"
                + _json.dumps(brief, ensure_ascii=False)
                + "\nAvoid topics in must_avoid_topics even if they seem interesting. "
                  "Prioritize topics in must_include_topics."
            )
        else:
            base_system += (
                "\n\n=== [EDITORIAL BRIEF — HASIL ANALISIS PASS 1, WAJIB DIPATUHI] ===\n"
                + _json.dumps(brief, ensure_ascii=False)
                + "\nHindari topik di must_avoid_topics meskipun terlihat menarik. "
                  "Utamakan topik di must_include_topics."
            )
    return base_system


async def _request_micro_clips(
    llm_base_url: str,
    llm_api_key: Optional[str],
    llm_model: Optional[str],
    temperature: float,
    system_instruction: str,
    micro_user_content: str,
    fallback_video_type: str = "umum",
    max_attempts: int = 2,
) -> tuple:
    """
    Satu request Micro Clip Selection. Return (raw_clips, video_type, rec_preset_id).
    raw_clips kosong bila gagal — caller yang tentukan fallback.
    """
    delays = [2.0, 4.0]
    for attempt in range(max_attempts):
        try:
            content = await _post_chat(
                llm_base_url, llm_api_key, llm_model,
                [{"role": "system", "content": system_instruction},
                 {"role": "user", "content": micro_user_content}],
                temperature=temperature,
            )
            parsed = sanitize_and_parse_json(content)
            raw_clips = (parsed.get("clips") or parsed.get("highlights") or parsed.get("candidates") or []) if isinstance(parsed, dict) else (parsed if isinstance(parsed, list) else [])
            if raw_clips:
                detected = parsed.get("video_type", fallback_video_type) if isinstance(parsed, dict) else fallback_video_type
                if not get_video_type_by_id(detected):
                    detected = fallback_video_type
                rec_preset = parsed.get("recommended_preset_id") if isinstance(parsed, dict) else None
                if not rec_preset:
                    vt = get_video_type_by_id(detected)
                    rec_preset = vt.get("recommended_preset_id") if vt else "preset_tiktok_bold"
                return list(raw_clips), detected, rec_preset
        except Exception:
            pass
        if attempt < max_attempts - 1:
            import asyncio
            await asyncio.sleep(delays[min(attempt, len(delays) - 1)])
    return [], fallback_video_type, "preset_tiktok_bold"


def smart_chunk_transcript(
    segments: List[Dict[str, Any]], video_duration: float,
) -> List[List[Dict[str, Any]]]:
    """
    Bagi segmen temporal jadi N chunk (batas di batas segmen, kalimat tak terpotong):
    < 30 mnt → 1 chunk (single-pass); 30-90 mnt → 3 chunk; > 90 mnt → 5 chunk.
    Pure function (tanpa I/O).
    """
    if not segments:
        return []
    if video_duration < 1800:
        return [list(segments)]
    num_chunks = 3 if video_duration <= 5400 else 5
    num_chunks = min(num_chunks, len(segments))
    base, extra = divmod(len(segments), num_chunks)
    chunks, idx = [], 0
    for i in range(num_chunks):
        size = base + (1 if i < extra else 0)
        chunks.append(segments[idx:idx + size])
        idx += size
    return [c for c in chunks if c]


def _truncate_macro(full_text: Optional[str], segments: List[Dict[str, Any]]) -> str:
    macro_text = full_text or " ".join(s.get("text", "").strip() for s in segments)
    if len(macro_text) > 8000:
        macro_text = macro_text[:4000] + "\n...[ringkasan alur tengah]...\n" + macro_text[-4000:]
    return macro_text


async def extract_highlights_chunked(
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
    max_dur: Optional[float] = None,
    two_pass: bool = False,
    vision_boost: Optional[Dict[float, float]] = None,
    vision_weight: float = 0.3,
    language: str = "id",
) -> HighlightsList:
    """
    Smart Chunk Strategy (Phase 2 — 1.2): 1 request LLM per chunk temporal (2x retry),
    lalu meta-ranking global (overlap suppression + max 10).
    Bila two_pass=True, Pass 1 macro jalan sekali dan brief dipakai semua chunk.
    Timestamp segmen dipertahankan absolut agar klip antar-chunk bisa digabung.
    """
    effective_min = float(min_dur) if min_dur is not None else float(settings.MIN_CLIP_SECONDS)
    effective_max = float(max_dur) if max_dur is not None else float(settings.MAX_CLIP_SECONDS)

    if not llm_base_url:
        return generate_heuristic_highlights(segments, video_duration, effective_min, effective_max, language=language)

    is_en = language and language.lower().startswith("en")

    chunks = smart_chunk_transcript(segments, video_duration)
    if len(chunks) <= 1:
        if two_pass:
            return await extract_highlights_two_pass(
                segments=segments, video_duration=video_duration, video_title=video_title,
                video_description=video_description, full_text=full_text,
                llm_base_url=llm_base_url, llm_api_key=llm_api_key, llm_model=llm_model,
                temperature=temperature, custom_prompt=custom_prompt,
                min_dur=effective_min, max_dur=effective_max,
                vision_boost=vision_boost, vision_weight=vision_weight,
                language=language,
            )
        return await extract_highlights_with_llm(
            segments=segments, video_duration=video_duration, video_title=video_title,
            video_description=video_description, full_text=full_text,
            llm_base_url=llm_base_url, llm_api_key=llm_api_key, llm_model=llm_model,
            temperature=temperature, custom_prompt=custom_prompt,
            min_dur=effective_min, max_dur=effective_max,
            vision_boost=vision_boost, vision_weight=vision_weight,
            language=language,
        )

    macro_text = _truncate_macro(full_text, segments)
    types_guide = build_video_types_prompt_guide()

    brief = None
    if two_pass:
        brief = await _request_editorial_brief(
            llm_base_url, llm_api_key, llm_model,
            video_title, video_description, macro_text, types_guide,
            language=language,
        )

    system_instruction = _build_micro_system(custom_prompt, effective_min, effective_max, brief, language=language)

    all_raw, type_votes = [], {}
    total = len(chunks)
    for i, chunk in enumerate(chunks, start=1):
        micro = format_transcript_for_llm(chunk)
        if is_en:
            user_content = f"""=== [VIDEO TYPE/GENRE TAXONOMY & CURATION GUIDE] ===
{types_guide}

NOTE: This is PART {i} OF {total} of the video. Timestamps below are ABSOLUTE
(actual time in the video) — return timestamps as-is, do not shift them.
Select 2 to 5 best clips from this part with duration {int(effective_min)} to {int(effective_max)} seconds:
{micro}
"""
        else:
            user_content = f"""=== [TAKSONOMI TIPE/GENRE VIDEO & PANDUAN KURASI] ===
{types_guide}

PERHATIAN: Ini BAGIAN {i} DARI {total} video. Timestamp di bawah adalah ABSOLUT
(waktu sebenarnya dalam video) — kembalikan timestamp apa adanya, jangan digeser.
Pilih 2 sampai 5 klip terbaik dari bagian ini yang berdurasi {int(effective_min)} sampai {int(effective_max)} detik:
{micro}
"""
        raw, detected, _ = await _request_micro_clips(
            llm_base_url, llm_api_key, llm_model, temperature,
            system_instruction, user_content,
            fallback_video_type=(brief or {}).get("video_type", "umum"),
        )
        all_raw.extend(raw)
        if detected and detected != "umum":
            type_votes[detected] = type_votes.get(detected, 0) + 1

    if not all_raw:
        return generate_heuristic_highlights(segments, video_duration, effective_min, effective_max, language=language)

    video_type = max(type_votes, key=type_votes.get) if type_votes else (brief or {}).get("video_type", "umum")
    vt = get_video_type_by_id(video_type)
    rec_preset = vt.get("recommended_preset_id") if vt else "preset_tiktok_bold"
    valid = validate_and_filter_candidates(all_raw, video_duration, effective_min, effective_max, max_count=10, segments=segments, vision_boost=vision_boost, vision_weight=vision_weight)
    if not valid:
        return generate_heuristic_highlights(segments, video_duration, effective_min, effective_max, language=language)
    return HighlightsList(valid, video_type=video_type, recommended_preset_id=rec_preset)


async def extract_highlights_two_pass(
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
    max_dur: Optional[float] = None,
    vision_boost: Optional[Dict[float, float]] = None,
    vision_weight: float = 0.3,
    language: str = "id",
) -> HighlightsList:
    """
    Sequential Two-Pass LLM Strategy (Phase 2 — 1.1):
    - Pass 1 (Macro, 45s, 2x retry): pahami video secara holistik → editorial_brief.
    - Pass 2 (Micro, 45s, 2x retry): pilih klip dari micro-segments dengan brief sebagai
      system context tambahan (noise konteks besar sudah disaring).
    Pass 1 gagal → fallback ke single-pass existing (lalu heuristik bila itu pun gagal).
    """
    effective_min = float(min_dur) if min_dur is not None else float(settings.MIN_CLIP_SECONDS)
    effective_max = float(max_dur) if max_dur is not None else float(settings.MAX_CLIP_SECONDS)

    if not llm_base_url:
        return generate_heuristic_highlights(segments, video_duration, effective_min, effective_max, language=language)

    is_en = language and language.lower().startswith("en")

    macro_text = _truncate_macro(full_text, segments)
    micro_transcript = format_transcript_for_llm(segments)
    types_guide = build_video_types_prompt_guide()

    # ---- Pass 1: Macro Analysis → editorial_brief ----
    brief = await _request_editorial_brief(
        llm_base_url, llm_api_key, llm_model,
        video_title, video_description, macro_text, types_guide,
        language=language,
    )

    if brief is None:
        # Fallback ke single-pass existing (sudah termasuk fallback heuristik)
        return await extract_highlights_with_llm(
            segments=segments, video_duration=video_duration, video_title=video_title,
            video_description=video_description, full_text=full_text,
            llm_base_url=llm_base_url, llm_api_key=llm_api_key, llm_model=llm_model,
            temperature=temperature, custom_prompt=custom_prompt,
            min_dur=effective_min, max_dur=effective_max,
            vision_boost=vision_boost, vision_weight=vision_weight,
            language=language,
        )

    # ---- Pass 2: Micro Clip Selection dengan brief sebagai system context ----
    system_instruction = _build_micro_system(custom_prompt, effective_min, effective_max, brief, language=language)
    if is_en:
        pass2_user = f"""=== [VIDEO TYPE/GENRE TAXONOMY & CURATION GUIDE] ===
{types_guide}

=== [EDITORIAL BRIEF] ===
Theme: {brief['theme_summary']}
Must avoid: {', '.join(brief['must_avoid_topics']) or '-'}
Must prioritize: {', '.join(brief['must_include_topics']) or '-'}

=== [MICRO SEGMENTS & TIMESTAMPS] ===
Select 3 to 10 best clips RELEVANT to the brief above, with duration {int(effective_min)} to {int(effective_max)} seconds:
{micro_transcript}
"""
    else:
        pass2_user = f"""=== [TAKSONOMI TIPE/GENRE VIDEO & PANDUAN KURASI] ===
{types_guide}

=== [BRIEF EDITORIAL] ===
Tema: {brief['theme_summary']}
Wajib dihindari: {', '.join(brief['must_avoid_topics']) or '-'}
Wajib diutamakan: {', '.join(brief['must_include_topics']) or '-'}

=== [KONTEKS KECIL / MICRO SEGMENTS & TIMESTAMPS] ===
Pilih 3 sampai 10 klip terbaik yang RELEVAN dengan brief di atas, dengan durasi {int(effective_min)} sampai {int(effective_max)} detik:
{micro_transcript}
"""
    raw_clips, _, rec_preset = await _request_micro_clips(
        llm_base_url, llm_api_key, llm_model, temperature,
        system_instruction, pass2_user, fallback_video_type=brief["video_type"],
    )
    if raw_clips:
        valid_candidates = validate_and_filter_candidates(raw_clips, video_duration, effective_min, effective_max, max_count=10, segments=segments, vision_boost=vision_boost, vision_weight=vision_weight)
        if valid_candidates:
            return HighlightsList(valid_candidates, video_type=brief["video_type"], recommended_preset_id=rec_preset)

    return generate_heuristic_highlights(segments, video_duration, effective_min, effective_max, language=language)

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


def _align_refined_words(
    old_words: List[Dict[str, Any]],
    new_text: str,
    seg_start: float,
    seg_end: float,
) -> List[Dict[str, Any]]:
    """Selaraskan word timestamps ketika teks segmen diperbaiki oleh LLM."""
    new_tokens = new_text.strip().split()
    if not new_tokens:
        return []
    if not old_words:
        dur = max(0.1, seg_end - seg_start)
        step = dur / len(new_tokens)
        return [
            {
                "word": w,
                "start": round(seg_start + i * step, 2),
                "end": round(seg_start + (i + 1) * step, 2),
                "probability": 0.95,
            }
            for i, w in enumerate(new_tokens)
        ]
    if len(new_tokens) == len(old_words):
        return [
            {
                "word": nw,
                "start": old_words[i]["start"],
                "end": old_words[i]["end"],
                "probability": old_words[i].get("probability", 0.95),
            }
            for i, nw in enumerate(new_tokens)
        ]
    total_chars = sum(len(w) for w in new_tokens) or 1
    total_dur = max(0.1, seg_end - seg_start)
    cur_t = seg_start
    res = []
    for w in new_tokens:
        w_dur = max(0.08, (len(w) / total_chars) * total_dur)
        w_end = min(seg_end, cur_t + w_dur)
        res.append({
            "word": w,
            "start": round(cur_t, 2),
            "end": round(w_end, 2),
            "probability": 0.95,
        })
        cur_t = w_end
    return res


async def refine_transcript_with_llm(
    segments: List[Dict[str, Any]],
    video_title: str,
    video_desc: Optional[str] = None,
    llm_base_url: Optional[str] = None,
    llm_api_key: Optional[str] = None,
    llm_model: Optional[str] = None,
    batch_size: int = 40,
) -> List[Dict[str, Any]]:
    """
    Kirim segmen teks transkrip ke AI untuk analisis konteks besar + perbaikan ejaan fonetik
    (misal 'AD DHoha' -> 'Ad-Dhuha', 'Sekali -GUS' -> 'sekaligus', 'Al ALvinsi' -> 'Al-Insyirah').
    Memperbarui teks segmen sekaligus menyelaraskan ulang word timestamps.
    """
    if not segments:
        return segments
    if not llm_base_url:
        return segments

    system_prompt = (
        "Kamu adalah editor transkrip audio profesional untuk subtitle video. "
        "Tugasmu adalah memperbaiki kesalahan ejaan fonetik speech-to-text (ASR), typo, "
        "pemenggalan kata yang salah/glitch (seperti 'Sekali -GUS' menjadi 'sekaligus'), "
        "dan istilah khusus (nama surah Al-Qur'an, istilah Islam, nama tokoh, istilah gaming) "
        "berdasarkan konteks judul dan isi video.\n\n"
        "ATURAN MUTLAK:\n"
        "1. JANGAN mengubah arti kalimat dan JANGAN meringkas/menghilangkan kata-kata inti agar tetap sinkron dengan audio pembicara.\n"
        "2. Perbaiki istilah yang salah dengar/salah eja (misal: 'AD DHoha' -> 'Ad-Dhuha', 'Al ALvinsi' -> 'Al-Insyirah', 'bismillah hirrohman nirrohim' -> 'bismillahirrahmanirrahim').\n"
        "3. Rapikan kapitalisasi dan tanda hubung/strip yang tidak wajar.\n"
        "4. Kembalikan HANYA format JSON valid berupa list objek: [{\"id\": <id_asli>, \"text\": \"<teks_perbaikan>\"}]. Tidak boleh ada teks obrolan pembuka/penutup."
    )

    refined_segments = [dict(s) for s in segments]
    id_to_seg = {s["id"]: s for s in refined_segments}

    for i in range(0, len(refined_segments), batch_size):
        batch = refined_segments[i : i + batch_size]
        items_payload = [{"id": s["id"], "text": s["text"]} for s in batch]

        user_prompt = (
            f"[KONTEKS VIDEO]\n"
            f"Judul: {video_title}\n"
            f"Deskripsi: {video_desc or '-'}\n\n"
            f"[DAFTAR SEGMEN TEKS YANG PERLU DIPERBAIKI]\n"
            f"{json.dumps(items_payload, ensure_ascii=False, indent=2)}\n\n"
            f"Koreksi teks segmen di atas dan kembalikan JSON list objek [{{\"id\": ..., \"text\": ...}}]:"
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        try:
            content = await _post_chat(
                llm_base_url=llm_base_url,
                llm_api_key=llm_api_key,
                llm_model=llm_model,
                messages=messages,
                temperature=0.2,
                timeout_seconds=45.0,
            )
            clean_json = re.sub(r"```(?:json)?\s*([\s\S]*?)\s*```", r"\1", content.strip())
            fixes = json.loads(clean_json)
            if isinstance(fixes, list):
                for item in fixes:
                    if isinstance(item, dict) and "id" in item and "text" in item:
                        seg = id_to_seg.get(item["id"])
                        if seg:
                            old_text = seg["text"]
                            new_text = str(item["text"]).strip()
                            if new_text and new_text != old_text:
                                seg["text"] = new_text
                                if "words" in seg and seg["words"]:
                                    seg["words"] = _align_refined_words(
                                        seg["words"],
                                        new_text,
                                        seg["start"],
                                        seg["end"],
                                    )
        except Exception as exc:
            logger.warning("Gagal memperbaiki batch transkrip dengan LLM (%s): %s", i, exc)
            continue

    return refined_segments
