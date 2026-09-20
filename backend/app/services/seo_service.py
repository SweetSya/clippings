"""AI SEO metadata generator (Phase 5 — 9.1 + 9.2).

Satu sumber kebenaran aturan per platform (PLATFORM_SEO_RULES) dipakai baik oleh
jalur LLM maupun template heuristik. Semua normalisasi pure (mudah di-test).
"""

from typing import Any, Dict, List, Optional

PLATFORM_SEO_RULES: Dict[str, Dict[str, Any]] = {
    "youtube_shorts": {
        "max_title": 100,
        "title_target": 60,
        "max_description": 5000,
        "description_target": 500,
        "required_hashtags": ["#shorts"],
        "max_hashtags": 6,
        "max_tags": 15,
        "category_ids": {"gaming": "20", "education": "27", "entertainment": "24", "default": "22"},
    },
    "tiktok": {
        "max_title": 150,
        "title_target": 100,
        "max_caption": 2200,
        "required_hashtags": ["#fyp", "#foryou"],
        "max_hashtags": 10,
        "max_tags": 10,
    },
    "instagram_reels": {
        "max_title": 125,
        "title_target": 100,
        "max_caption": 2200,
        "required_hashtags": ["#reels"],
        "max_hashtags": 30,
        "max_tags": 15,
    },
}

SEO_SYSTEM_PROMPT = """Kamu adalah YouTube SEO specialist dan content strategist kelas dunia.
TUGAS: Buat metadata yang dioptimalkan untuk MAXIMUM VIEWS & ENGAGEMENT.

ATURAN JUDUL (YouTube Shorts):
1. Maksimal 60 karakter (agar tidak terpotong di mobile)
2. WAJIB mengandung 1 emoji yang relevan
3. WAJIB memicu rasa penasaran / FOMO / curiosity gap
4. Gunakan angka jika memungkinkan ("5 Cara...", "3 Detik...")
5. Bahasa natural, bukan clickbait murahan

ATURAN DESKRIPSI:
1. 2-3 baris pertama = hook (terlihat sebelum "more")
2. Sisipkan 3-5 hashtag di akhir: #shorts WAJIB ada
3. Tambahkan CTA: "Like & Subscribe untuk konten serupa!"
4. Jangan lebih dari 500 karakter total

ATURAN TAGS:
1. 8-15 tags campuran: spesifik (topik) + broad (kategori)
2. Campur bahasa Indonesia dan Inggris
3. Include trending tags yang relevan

ATURAN HASHTAGS:
1. Selalu awali dengan #shorts
2. 3-5 hashtag tambahan yang niche-specific
3. Jangan lebih dari 6 total

Balas HANYA JSON valid, TANPA markdown:
{"titles": ["...", "...", "..."], "description": "...", "tags": ["..."], "hashtags": ["..."], "category_suggestion": "22", "best_upload_time": "18:00-21:00", "estimated_reach": "medium"}"""

SEO_SYSTEM_PROMPT_EN = """You are a world-class YouTube SEO specialist and content strategist.
TASK: Create metadata optimized for MAXIMUM VIEWS & ENGAGEMENT.

IMPORTANT: ALL generated text (titles, description, tags) MUST be in English.

TITLE RULES (YouTube Shorts):
1. Maximum 60 characters (so it doesn't get cut off on mobile)
2. MUST contain 1 relevant emoji
3. MUST trigger curiosity / FOMO / curiosity gap
4. Use numbers when possible ("5 Ways...", "3 Seconds...")
5. Natural language, not cheap clickbait

DESCRIPTION RULES:
1. First 2-3 lines = hook (visible before "more")
2. Insert 3-5 hashtags at the end: #shorts is MANDATORY
3. Add CTA: "Like & Subscribe for more content!"
4. No more than 500 characters total

TAG RULES:
1. 8-15 mixed tags: specific (topic) + broad (category)
2. Mix of English tags
3. Include relevant trending tags

HASHTAG RULES:
1. Always start with #shorts
2. 3-5 additional niche-specific hashtags
3. No more than 6 total

Reply ONLY with valid JSON, NO markdown:
{"titles": ["...", "...", "..."], "description": "...", "tags": ["..."], "hashtags": ["..."], "category_suggestion": "22", "best_upload_time": "18:00-21:00", "estimated_reach": "medium"}"""


def get_seo_system_prompt(language: str = "id") -> str:
    """Return language-appropriate SEO system prompt."""
    if language and language.lower().startswith("en"):
        return SEO_SYSTEM_PROMPT_EN
    return SEO_SYSTEM_PROMPT


def _clean_tag(tag: str) -> str:
    t = str(tag or "").strip().lower().lstrip("#").strip()
    return t.replace(" ", "")


def _clean_hashtag(tag: str) -> str:
    t = _clean_tag(tag)
    return f"#{t}" if t else ""


def apply_platform_rules(platform: str, seo: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalisasi metadata sesuai aturan platform. Pure function.
    Platform tak dikenal → fallback youtube_shorts (jangan error).
    """
    rules = PLATFORM_SEO_RULES.get(str(platform or ""), PLATFORM_SEO_RULES["youtube_shorts"])
    out = dict(seo or {})

    titles = [str(t or "").strip() for t in (out.get("titles") or []) if str(t or "").strip()]
    if not titles and out.get("title"):
        titles = [str(out["title"]).strip()]
    max_title = int(rules.get("max_title", 100))
    out["titles"] = [t[:max_title] for t in titles[:3]]

    desc = str(out.get("description") or "").strip()
    out["description"] = desc[: int(rules.get("max_description", rules.get("description_target", 5000)))]

    tags = []
    for t in (out.get("tags") or []):
        c = _clean_tag(t)
        if c and c not in tags:
            tags.append(c)
    out["tags"] = tags[: int(rules.get("max_tags", 15))]

    tags_needed = list(rules.get("required_hashtags", []))
    tags_have = []
    for h in (out.get("hashtags") or []):
        c = _clean_hashtag(h)
        if c and c not in tags_have:
            tags_have.append(c)
    merged = list(tags_needed)
    for h in tags_have:
        if h.lower() not in [x.lower() for x in merged]:
            merged.append(h)
    out["hashtags"] = merged[: int(rules.get("max_hashtags", 6))]
    return out


def heuristic_seo(clip_title: str, clip_text: str, video_title: str = "",
                  platform: str = "youtube_shorts") -> Dict[str, Any]:
    """
    Template generator bila LLM tak connected. Pure function (tanpa I/O).
    """
    base = (clip_title or video_title or "Momen menarik").strip()
    hook_word = (clip_text or "").strip().split()
    hook = " ".join(hook_word[:8])
    titles = [
        f"{base[:48]} 🤯",
        f"GILA! {base[:50]}...",
        f"{base[:48]} 🔥",
    ]
    description = (
        f"{hook}...\n\n"
        f"Tonton sampai habis! Like & Subscribe untuk konten serupa!\n\n"
        f"#shorts #viral #fyp"
    )
    topic_tags = [w.strip(".,!?").lower() for w in (clip_title + " " + clip_text).split()
                  if len(w.strip(".,!?")) > 4][:6]
    tags = ["shorts", "viral", "indonesia"] + [t for t in topic_tags if t not in ("shorts", "viral")]
    return apply_platform_rules(platform, {
        "titles": titles,
        "description": description,
        "tags": tags,
        "hashtags": ["#shorts", "#viral", "#fyp"],
        "category_suggestion": "22",
        "best_upload_time": "18:00-21:00",
        "estimated_reach": "medium",
    })


async def _llm_seo(clip_title: str, clip_text: str, video_title: str, video_description: str,
                   video_type: str, clip_duration: float, platform: str, language: str,
                   llm_base_url: str, llm_api_key: Optional[str], llm_model: Optional[str]) -> Dict[str, Any]:
    from app.services.llm_service import _post_chat, sanitize_and_parse_json

    user_content = f"""Platform target: {platform} | Bahasa: {language}
Judul klip (internal): {clip_title}
Teks yang diucapkan di klip: {clip_text[:1500]}
Judul video sumber: {video_title}
Deskripsi video sumber: {(video_description or '-')[:800]}
Tipe video: {video_type} | Durasi klip: {clip_duration:.0f} detik

Buatkan metadata SEO sesuai aturan."""
    content = await _post_chat(
        llm_base_url, llm_api_key, llm_model,
        [{"role": "system", "content": SEO_SYSTEM_PROMPT},
         {"role": "user", "content": user_content}],
        temperature=0.7, timeout_seconds=45.0,
    )
    parsed = sanitize_and_parse_json(content)
    if isinstance(parsed, list):
        parsed = {"titles": parsed}
    if not isinstance(parsed, dict) or not parsed.get("titles"):
        raise ValueError("Respons LLM tak berisi judul.")
    return parsed


async def generate_youtube_seo(clip_title: str, clip_text: str, video_title: str = "",
                               video_description: str = "", video_type: str = "umum",
                               clip_duration: float = 30.0, language: str = "id",
                               llm_base_url: str = "", llm_api_key: Optional[str] = None,
                               llm_model: Optional[str] = "gpt-4o-mini") -> Dict[str, Any]:
    """SEO YouTube Shorts via LLM, fallback heuristik bila gagal/tak connected."""
    platform = "youtube_shorts"
    if llm_base_url:
        try:
            raw = await _llm_seo(clip_title, clip_text, video_title, video_description,
                                 video_type, clip_duration, platform, language,
                                 llm_base_url, llm_api_key, llm_model)
            return apply_platform_rules(platform, raw)
        except Exception:
            pass
    return heuristic_seo(clip_title, clip_text, video_title, platform)


async def generate_tiktok_seo(clip_title: str, clip_text: str, video_title: str = "",
                              language: str = "id", llm_base_url: str = "",
                              llm_api_key: Optional[str] = None,
                              llm_model: Optional[str] = "gpt-4o-mini") -> Dict[str, Any]:
    """SEO TikTok: caption = judul + hashtags."""
    platform = "tiktok"
    if llm_base_url:
        try:
            raw = await _llm_seo(clip_title, clip_text, video_title, "", "umum",
                                 30.0, platform, language,
                                 llm_base_url, llm_api_key, llm_model)
            norm = apply_platform_rules(platform, raw)
            caption = (norm["titles"][0] if norm["titles"] else clip_title) + " " + " ".join(norm["hashtags"])
            norm["caption"] = caption[: int(PLATFORM_SEO_RULES[platform].get("max_caption", 2200))]
            return norm
        except Exception:
            pass
    norm = heuristic_seo(clip_title, clip_text, video_title, platform)
    norm["caption"] = (norm["titles"][0] if norm["titles"] else clip_title) + " " + " ".join(norm["hashtags"])
    return norm
