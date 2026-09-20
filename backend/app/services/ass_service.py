import math
import re
from typing import List, Dict, Any, Optional

EMOJI_KEYWORDS: Dict[str, str] = {
    # Finance / Wealth / Profit
    "uang": "💰", "cuan": "💰", "duit": "💰", "kaya": "💰", "modal": "💰",
    "omset": "💰", "profit": "💰", "investasi": "💰", "rupiah": "💰", "dolar": "💰",
    "saham": "💰", "crypto": "💰", "rejeki": "💰", "gaji": "💰", "harga": "💰",
    "money": "💰", "cash": "💰", "rich": "💰", "wealth": "💰",

    # Viral / Energy / Fire
    "api": "🔥", "viral": "🔥", "panas": "🔥", "meledak": "🔥", "trending": "🔥",
    "heboh": "🔥", "gila": "🔥", "parah": "🔥", "keren": "🔥", "mantap": "🔥",
    "fire": "🔥", "hot": "🔥", "epic": "🔥", "insane": "🔥",

    # Rocket / Growth / Speed
    "roket": "🚀", "terbang": "🚀", "melejit": "🚀", "cepat": "🚀", "lompat": "🚀",
    "naik": "🚀", "pesat": "🚀", "growth": "🚀", "rocket": "🚀", "scale": "🚀",
    "fast": "🚀", "launch": "🚀",

    # Idea / Smart / Mindset
    "ide": "💡", "pikir": "💡", "solusi": "💡", "trik": "💡", "tips": "💡",
    "cara": "💡", "rahasia": "💡", "strategi": "💡", "kunci": "💡", "ilmu": "💡",
    "formula": "💡", "mindset": "💡", "tahu": "💡", "idea": "💡", "smart": "💡",
    "brain": "💡", "secret": "💡", "hack": "💡",

    # Target / Goal / Focus
    "target": "🎯", "tujuan": "🎯", "fokus": "🎯", "bidik": "🎯", "goal": "🎯",
    "goals": "🎯", "focus": "🎯", "mission": "🎯",

    # Warning / Danger / Risk
    "bahaya": "⚠️", "waspada": "⚠️", "hati-hati": "⚠️", "rugi": "⚠️", "scam": "⚠️",
    "awas": "⚠️", "jebakan": "⚠️", "salah": "⚠️", "gagal": "⚠️", "danger": "⚠️",
    "warning": "⚠️", "risk": "⚠️", "mistake": "⚠️",

    # Winner / Trophy / Champion
    "juara": "🏆", "menang": "🏆", "sukses": "🏆", "berhasil": "🏆", "terbaik": "🏆",
    "nomor 1": "🏆", "prestasi": "🏆", "win": "🏆", "winner": "🏆", "champion": "🏆",
    "trophy": "🏆", "success": "🏆",

    # Time / Clock
    "waktu": "⏱️", "detik": "⏱️", "menit": "⏱️", "jam": "⏱️", "hari": "⏱️",
    "time": "⏱️", "clock": "⏱️",

    # Shock / Wow
    "kaget": "🤯", "syok": "🤯", "takjub": "🤯", "wow": "🤯", "shock": "🤯",
}

HIGH_EMOTION_KEYWORDS = {
    "rahasia", "kunci", "sukses", "penting", "bahaya", "uang", "cuan", "kaya", "gratis",
    "wajib", "fakta", "gila", "terbaik", "viral", "tips", "trik", "investasi", "profit",
    "omset", "bisnis", "modal", "juara", "target", "fokus", "solusi", "terbukti", "hasil",
    "raup", "jutaan", "miliaran", "strategi", "otomatis", "formula", "mindset", "secret",
    "money", "rich", "win", "growth", "danger", "warning", "free", "best", "million",
    "billion", "hack", "rugi", "awas", "peringatan", "keuntungan", "hebat"
}

def hex_to_ass(hex_color: str, alpha: int = 0x00) -> str:
    """
    Mengonversi format warna heksadesimal RGB (#RRGGBB) ke format ASS (&HAABBGGRR&).
    PENTING: Format ASS membalik urutan Red dan Blue (BGR, bukan RGB).
    
    >>> hex_to_ass("#FFCC00")
    '&H0000CCFF&'
    >>> hex_to_ass("#FFFFFF")
    '&H00FFFFFF&'
    """
    clean_hex = hex_color.lstrip("#").upper()
    if len(clean_hex) == 3:
        clean_hex = "".join([c * 2 for c in clean_hex])
    if len(clean_hex) != 6:
        clean_hex = "FFFFFF"  # fallback white
        
    r = int(clean_hex[0:2], 16)
    g = int(clean_hex[2:4], 16)
    b = int(clean_hex[4:6], 16)
    
    return f"&H{alpha:02X}{b:02X}{g:02X}{r:02X}&"

def format_ass_time(seconds: float) -> str:
    """Convert seconds (float) to ASS timestamp format H:MM:SS.cs (centiseconds)."""
    seconds = max(0.0, seconds)
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    cs = int(round((seconds - int(seconds)) * 100))
    if cs >= 100:
        cs = 99
    return f"{hrs}:{mins:02d}:{secs:02d}.{cs:02d}"

def is_keyword(word_text: str) -> bool:
    """Memeriksa apakah kata termasuk kata kunci penting / angka / emosi tinggi."""
    clean = re.sub(r"[^\w\s]", "", word_text).lower().strip()
    if not clean:
        return False
    # Angka, persentase, atau nilai uang
    if re.search(r"\d", clean):
        return True
    return clean in HIGH_EMOTION_KEYWORDS or clean in EMOJI_KEYWORDS

def inject_emoji(word_text: str) -> str:
    """Menyematkan emoji visual pintar di depan kata kunci jika cocok."""
    clean = re.sub(r"[^\w\s]", "", word_text).lower().strip()
    emoji = EMOJI_KEYWORDS.get(clean)
    if emoji and not word_text.startswith(emoji):
        return f"{emoji} {word_text}"
    return word_text

def generate_karaoke_ass(
    words: List[Dict[str, Any]],
    clip_start: float,
    clip_end: float,
    output_path: str,
    font: str = "Poppins",
    font_size: int = 44,
    active_color: str = "#FFCC00",
    primary_color: str = "#FFFFFF",
    position: str = "bottom",
    margin_v: int = None,
    fallback_title: str = None,
    outline_width: int = 3,
    shadow_depth: int = 1,
    is_uppercase: bool = False,
    motion_type: str = "karaoke",
    highlight_bg_color: str = "#FFCC00",
    enable_keyword_color: bool = True,
    keyword_color: str = "#10B981",
    enable_dynamic_scaling: bool = False,
    enable_emoji_injection: bool = False,
    glow_effect: bool = False,
    enable_vocal_dynamics: bool = False,
    time_offset: float = 0.0,
):
    """
    Generate an Advanced SubStation Alpha (.ass) subtitle file formatted for 9:16 vertical video.
    Mendukung 8 motion types (single_word_pop, karaoke, background_box, typewriter, slide_up,
    bounce_in, zoom_flash, glitch_reveal)
    serta 4 efek visual (color shift, dynamic scaling, glow border, smart emoji injection)
    dan deteksi penekanan vokal dinamis (vocal dynamics scaling).
    `time_offset` menggeser seluruh timestamp subtitle (misal saat jeda intro freeze frame aktif).
    """
    active_ass = hex_to_ass(active_color)
    primary_ass = hex_to_ass(primary_color)
    keyword_ass = hex_to_ass(keyword_color)
    highlight_bg_ass = hex_to_ass(highlight_bg_color)

    # Hitung margin vertikal Y
    if margin_v is None:
        if position == "top":
            v_margin = 1540
        elif position == "middle":
            v_margin = 920
        else:  # bottom
            v_margin = 340
    else:
        v_margin = int(margin_v)

    # Filter kata dalam rentang klip
    clip_words = []
    for w in words:
        w_start = float(w.get("start", 0.0))
        w_end = float(w.get("end", 0.0))
        raw_text = str(w.get("word", "")).strip()
        if not raw_text:
            continue

        if enable_emoji_injection:
            raw_text = inject_emoji(raw_text)

        if is_uppercase:
            raw_text = raw_text.upper()

        scale_mult = float(w.get("scale_multiplier", 1.0))
        is_stressed = bool(w.get("is_vocal_stressed", False))

        if w_end > clip_start and w_start < clip_end:
            clip_words.append({
                "word": raw_text,
                "start": max(0.0, (w_start - clip_start) + time_offset),
                "end": max(0.0, min(w_end - clip_start, clip_end - clip_start) + time_offset),
                "is_kw": is_keyword(raw_text),
                "scale_multiplier": scale_mult,
                "is_vocal_stressed": is_stressed
            })

    events = []

    # Jika tidak ada kata transkrip namun ada fallback title
    if not clip_words and fallback_title:
        duration = max(1.0, clip_end - clip_start)
        title_text = fallback_title.upper() if is_uppercase else fallback_title
        if enable_emoji_injection:
            title_text = inject_emoji(title_text)
        events.append(
            f"Dialogue: 0,0:00:00.00,{format_ass_time(duration)},Caption,,0,0,0,,{{\\c{active_ass}\\b1}}{title_text}{{\\c{primary_ass}\\b0}}"
        )
    elif motion_type == "single_word_pop":
        # 1. Single Word Pop / Bouncy (Hormozi Style)
        # Menampilkan 1 kata per waktu dengan efek zoom pop singkat (scale 125% -> 100%)
        for item in clip_words:
            w_start = item["start"]
            w_end = item["end"]
            if w_end <= w_start:
                w_end = w_start + 0.28
            word_txt = item["word"]
            is_kw = item["is_kw"]
            scale_mult = item["scale_multiplier"] if enable_vocal_dynamics else 1.0

            # Pilih warna kata: keyword_color jika aktif keyword shift / stressed, selain itu active_color
            word_col = keyword_ass if ((is_kw or item["is_vocal_stressed"]) and enable_keyword_color) else active_ass
            
            # Dynamic scaling: kata kunci atau penekanan suara mendapat ukuran lebih besar
            if is_kw and enable_dynamic_scaling:
                start_scale, end_scale = int(round(140 * scale_mult)), int(round(120 * scale_mult))
            else:
                start_scale, end_scale = int(round(125 * scale_mult)), int(round(100 * scale_mult))

            # Tag override zoom pop transisi 70ms
            pop_tag = f"{{\\c{word_col}\\b1\\fscx{start_scale}\\fscy{start_scale}\\t(0,70,\\fscx{end_scale}\\fscy{end_scale})}}"
            events.append(
                f"Dialogue: 0,{format_ass_time(w_start)},{format_ass_time(w_end)},Caption,,0,0,0,,{pop_tag}{word_txt}"
            )
    else:
        # Group words into subtitle lines / chunks (3-4 kata per baris)
        chunks = []
        current_chunk = []
        chunk_max_words = 4

        for w in clip_words:
            current_chunk.append(w)
            if len(current_chunk) >= chunk_max_words or (len(current_chunk) >= 2 and any(p in w["word"] for p in [".", "!", "?", ","])):
                chunks.append(current_chunk)
                current_chunk = []
        if current_chunk:
            chunks.append(current_chunk)

        # Render berdasarkan gaya animasi yang dipilih
        if motion_type == "typewriter":
            # 4. Typewriter / Word-by-Word Reveal
            # Kata-kata muncul berurutan satu per satu dan menetap sampai akhir kalimat
            for chunk in chunks:
                if not chunk:
                    continue
                chunk_end = chunk[-1]["end"]
                for step_idx in range(len(chunk)):
                    step_start = chunk[step_idx]["start"]
                    step_end = chunk[step_idx + 1]["start"] if step_idx + 1 < len(chunk) else chunk_end
                    if step_end <= step_start:
                        step_end = step_start + 0.3

                    revealed_parts = []
                    for idx in range(step_idx + 1):
                        item = chunk[idx]
                        txt = item["word"]
                        is_kw = item["is_kw"]
                        if idx == step_idx:
                            # Kata yang baru saja diketik: disorot dengan active_color atau keyword_color
                            col = keyword_ass if (is_kw and enable_keyword_color) else active_ass
                            revealed_parts.append(f"{{\\c{col}\\b1}}{txt}{{\\c{primary_ass}\\b0}}")
                        else:
                            if is_kw and enable_keyword_color:
                                revealed_parts.append(f"{{\\c{keyword_ass}\\b1}}{txt}{{\\c{primary_ass}\\b0}}")
                            else:
                                revealed_parts.append(txt)

                    rendered_line = " ".join(revealed_parts)
                    events.append(
                        f"Dialogue: 0,{format_ass_time(step_start)},{format_ass_time(step_end)},Caption,,0,0,0,,{rendered_line}"
                    )

        elif motion_type == "background_box":
            # 3. Background Box / Highlighter Sticker (CapCut Style)
            # Kata yang aktif dibungkus badge stiker tebal (kontras tinggi)
            for chunk in chunks:
                if not chunk:
                    continue
                for active_idx, target_word in enumerate(chunk):
                    w_start = target_word["start"]
                    w_end = target_word["end"]
                    if w_end <= w_start:
                        w_end = w_start + 0.3

                    line_parts = []
                    for idx, w in enumerate(chunk):
                        word_txt = w["word"]
                        is_kw = w["is_kw"]

                        w_scale_mult = w.get("scale_multiplier", 1.0) if enable_vocal_dynamics else 1.0
                        w_is_stressed = w.get("is_vocal_stressed", False) if enable_vocal_dynamics else False

                        if idx == active_idx:
                            base_scale = 115 if (is_kw and enable_dynamic_scaling) else 108
                            final_scale = int(round(base_scale * w_scale_mult))
                            scale_tag = f"\\fscx{final_scale}\\fscy{final_scale}"
                            # Active highlighter sticker: border tebal warna highlight_bg_ass dengan teks kontras gelap
                            sticker_tag = f"{{\\3c{highlight_bg_ass}\\bord7\\c&H0017191C&\\b1{scale_tag}}}"
                            reset_tag = f"{{\\3c&H00000000&\\bord{outline_width}\\c{primary_ass}\\b0\\fscx100\\fscy100}}"
                            line_parts.append(f"{sticker_tag}{word_txt}{reset_tag}")
                        else:
                            if (is_kw or w_is_stressed) and enable_keyword_color:
                                line_parts.append(f"{{\\c{keyword_ass}\\b1}}{word_txt}{{\\c{primary_ass}\\b0}}")
                            else:
                                line_parts.append(word_txt)

                    rendered_line = " ".join(line_parts)
                    events.append(
                        f"Dialogue: 0,{format_ass_time(w_start)},{format_ass_time(w_end)},Caption,,0,0,0,,{rendered_line}"
                    )

        elif motion_type == "slide_up":
            # 5. Slide Up / Fade In
            # Kalimat meluncur lembut dari bawah (offset Y) sambil fade-in, disinkronkan dengan karaoke
            target_y = 1920 - v_margin
            slide_from_y = target_y + 35
            for chunk in chunks:
                if not chunk:
                    continue
                for active_idx, target_word in enumerate(chunk):
                    w_start = target_word["start"]
                    w_end = target_word["end"]
                    if w_end <= w_start:
                        w_end = w_start + 0.3

                    line_parts = []
                    for idx, w in enumerate(chunk):
                        word_txt = w["word"]
                        is_kw = w["is_kw"]
                        w_scale_mult = w.get("scale_multiplier", 1.0) if enable_vocal_dynamics else 1.0
                        w_is_stressed = w.get("is_vocal_stressed", False) if enable_vocal_dynamics else False

                        if idx == active_idx:
                            col = keyword_ass if ((is_kw or w_is_stressed) and enable_keyword_color) else active_ass
                            base_scale = 115 if (is_kw and enable_dynamic_scaling) else 108
                            final_scale = int(round(base_scale * w_scale_mult))
                            scale_tag = f"\\fscx{final_scale}\\fscy{final_scale}"
                            line_parts.append(f"{{\\c{col}\\b1{scale_tag}}}{word_txt}{{\\c{primary_ass}\\b0\\fscx100\\fscy100}}")
                        else:
                            if (is_kw or w_is_stressed) and enable_keyword_color:
                                line_parts.append(f"{{\\c{keyword_ass}\\b1}}{word_txt}{{\\c{primary_ass}\\b0}}")
                            else:
                                line_parts.append(word_txt)

                    # Jika kata pertama dalam chunk, sematkan animasi slide-up + fade
                    if active_idx == 0:
                        anim_prefix = f"{{\\an2\\move(540,{slide_from_y},540,{target_y},0,140)\\fad(140,80)}}"
                    else:
                        anim_prefix = f"{{\\an2\\pos(540,{target_y})}}"

                    rendered_line = anim_prefix + " ".join(line_parts)
                    events.append(
                        f"Dialogue: 0,{format_ass_time(w_start)},{format_ass_time(w_end)},Caption,,0,0,0,,{rendered_line}"
                    )

        elif motion_type == "bounce_in":
            # 6. Bounce In / Scene Entry dari atas (CapCut style)
            # Tiap baris jatuh memantul dari atas layar ke posisi target + fade cepat
            target_y = 1920 - v_margin
            for chunk in chunks:
                if not chunk:
                    continue
                for active_idx, target_word in enumerate(chunk):
                    w_start = target_word["start"]
                    w_end = target_word["end"]
                    if w_end <= w_start:
                        w_end = w_start + 0.3

                    line_parts = []
                    for idx, w in enumerate(chunk):
                        word_txt = w["word"]
                        is_kw = w["is_kw"]
                        w_scale_mult = w.get("scale_multiplier", 1.0) if enable_vocal_dynamics else 1.0
                        w_is_stressed = w.get("is_vocal_stressed", False) if enable_vocal_dynamics else False

                        if idx == active_idx:
                            col = keyword_ass if ((is_kw or w_is_stressed) and enable_keyword_color) else active_ass
                            base_scale = 115 if (is_kw and enable_dynamic_scaling) else 108
                            final_scale = int(round(base_scale * w_scale_mult))
                            scale_tag = f"\\fscx{final_scale}\\fscy{final_scale}"
                            line_parts.append(f"{{\\c{col}\\b1{scale_tag}}}{word_txt}{{\\c{primary_ass}\\b0\\fscx100\\fscy100}}")
                        else:
                            if (is_kw or w_is_stressed) and enable_keyword_color:
                                line_parts.append(f"{{\\c{keyword_ass}\\b1}}{word_txt}{{\\c{primary_ass}\\b0}}")
                            else:
                                line_parts.append(word_txt)

                    if active_idx == 0:
                        anim_prefix = f"{{\\an2\\move(540,-50,540,{target_y},0,200)\\fad(120,80)}}"
                    else:
                        anim_prefix = f"{{\\an2\\pos(540,{target_y})}}"

                    rendered_line = anim_prefix + " ".join(line_parts)
                    events.append(
                        f"Dialogue: 0,{format_ass_time(w_start)},{format_ass_time(w_end)},Caption,,0,0,0,,{rendered_line}"
                    )

        elif motion_type == "zoom_flash":
            # 7. Zoom Flash / Kata kunci meledak 200% -> 100% + flash warna (CapCut zoom)
            # Kata aktif discale besar lalu menyusut + flash active_color -> putih
            for chunk in chunks:
                if not chunk:
                    continue
                for active_idx, target_word in enumerate(chunk):
                    w_start = target_word["start"]
                    w_end = target_word["end"]
                    if w_end <= w_start:
                        w_end = w_start + 0.3

                    line_parts = []
                    for idx, w in enumerate(chunk):
                        word_txt = w["word"]
                        is_kw = w["is_kw"]
                        w_scale_mult = w.get("scale_multiplier", 1.0) if enable_vocal_dynamics else 1.0
                        w_is_stressed = w.get("is_vocal_stressed", False) if enable_vocal_dynamics else False

                        if idx == active_idx:
                            col = keyword_ass if ((is_kw or w_is_stressed) and enable_keyword_color) else active_ass
                            zoom_tag = (
                                f"{{\\c{col}\\b1\\fscx{int(round(200 * w_scale_mult))}"
                                f"\\fscy{int(round(200 * w_scale_mult))}"
                                f"\\t(0,150,\\fscx100\\fscy100)"
                                f"\\t(0,150,\\1c{primary_ass})}}"
                            )
                            line_parts.append(f"{zoom_tag}{word_txt}{{\\c{primary_ass}\\b0\\fscx100\\fscy100\\1c{primary_ass}}}")
                        else:
                            if (is_kw or w_is_stressed) and enable_keyword_color:
                                line_parts.append(f"{{\\c{keyword_ass}\\b1}}{word_txt}{{\\c{primary_ass}\\b0}}")
                            else:
                                line_parts.append(word_txt)

                    rendered_line = " ".join(line_parts)
                    events.append(
                        f"Dialogue: 0,{format_ass_time(w_start)},{format_ass_time(w_end)},Caption,,0,0,0,,{rendered_line}"
                    )

        elif motion_type == "glitch_reveal":
            # 8. Glitch Reveal / Efek glitch digital (shake horizontal + inversi sesaat)
            # Offset bergantian deterministik per chunk agar mudah di-test (tanpa random)
            target_y = 1920 - v_margin
            for chunk_idx, chunk in enumerate(chunks):
                if not chunk:
                    continue
                shake_x = 546 if chunk_idx % 2 == 0 else 534
                for active_idx, target_word in enumerate(chunk):
                    w_start = target_word["start"]
                    w_end = target_word["end"]
                    if w_end <= w_start:
                        w_end = w_start + 0.3

                    line_parts = []
                    for idx, w in enumerate(chunk):
                        word_txt = w["word"]
                        is_kw = w["is_kw"]
                        w_is_stressed = w.get("is_vocal_stressed", False) if enable_vocal_dynamics else False

                        if idx == active_idx:
                            col = keyword_ass if ((is_kw or w_is_stressed) and enable_keyword_color) else active_ass
                            line_parts.append(f"{{\\c{col}\\b1}}{word_txt}{{\\c{primary_ass}\\b0}}")
                        else:
                            if (is_kw or w_is_stressed) and enable_keyword_color:
                                line_parts.append(f"{{\\c{keyword_ass}\\b1}}{word_txt}{{\\c{primary_ass}\\b0}}")
                            else:
                                line_parts.append(word_txt)

                    if active_idx == 0:
                        anim_prefix = (
                            f"{{\\an2\\pos({shake_x},{target_y})"
                            f"\\1c&H0000FF00&\\t(0,80,\\1c{primary_ass}\\pos(540,{target_y}))}}"
                        )
                    else:
                        anim_prefix = f"{{\\an2\\pos(540,{target_y})}}"

                    rendered_line = anim_prefix + " ".join(line_parts)
                    events.append(
                        f"Dialogue: 0,{format_ass_time(w_start)},{format_ass_time(w_end)},Caption,,0,0,0,,{rendered_line}"
                    )

        else:
            # 2. Karaoke / Active Word Highlight (Default Opus Clip)
            # Kalimat 3-4 kata sekaligus, kata aktif bersinar terang dengan perubahan warna real-time
            for chunk in chunks:
                if not chunk:
                    continue
                for active_idx, target_word in enumerate(chunk):
                    w_start = target_word["start"]
                    w_end = target_word["end"]
                    if w_end <= w_start:
                        w_end = w_start + 0.3

                    line_parts = []
                    for idx, w in enumerate(chunk):
                        word_txt = w["word"]
                        is_kw = w["is_kw"]
                        w_scale_mult = w.get("scale_multiplier", 1.0) if enable_vocal_dynamics else 1.0
                        w_is_stressed = w.get("is_vocal_stressed", False) if enable_vocal_dynamics else False

                        if idx == active_idx:
                            col = keyword_ass if ((is_kw or w_is_stressed) and enable_keyword_color) else active_ass
                            base_scale = 115 if (is_kw and enable_dynamic_scaling) else 108
                            final_scale = int(round(base_scale * w_scale_mult))
                            scale_tag = f"\\fscx{final_scale}\\fscy{final_scale}"
                            line_parts.append(f"{{\\c{col}\\b1{scale_tag}}}{word_txt}{{\\c{primary_ass}\\b0\\fscx100\\fscy100}}")
                        else:
                            if (is_kw or w_is_stressed) and enable_keyword_color:
                                line_parts.append(f"{{\\c{keyword_ass}\\b1}}{word_txt}{{\\c{primary_ass}\\b0}}")
                            else:
                                line_parts.append(word_txt)

                    rendered_line = " ".join(line_parts)
                    events.append(
                        f"Dialogue: 0,{format_ass_time(w_start)},{format_ass_time(w_end)},Caption,,0,0,0,,{rendered_line}"
                    )

    # Softened diffuse glow neon styling: pertahankan outline hitam pekat agar huruf tetap tajam
    if glow_effect:
        outline_col = "&H00000000"
        back_col = hex_to_ass(active_color, alpha=0x60)
        effective_outline = max(2, outline_width)
        effective_shadow = max(3, shadow_depth + 2)
    else:
        outline_col = "&H00000000"
        back_col = "&H80000000"
        effective_outline = outline_width
        effective_shadow = shadow_depth

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Caption,{font},{font_size},{primary_ass},&H000000FF,{outline_col},{back_col},-1,0,0,0,100,100,0,0,1,{effective_outline},{effective_shadow},2,60,60,{v_margin},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    ass_content = header + "\n".join(events) + "\n"

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(ass_content)

