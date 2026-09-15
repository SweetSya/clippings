import os
import tempfile
import pytest
from app.services.ass_service import (
    generate_karaoke_ass,
    hex_to_ass,
    is_keyword,
    inject_emoji,
)

def test_hex_to_ass_conversion():
    assert hex_to_ass("#FFCC00") == "&H0000CCFF&"
    assert hex_to_ass("#FFFFFF") == "&H00FFFFFF&"
    assert hex_to_ass("#00F0FF") == "&H00FFF000&"
    assert hex_to_ass("#10B981") == "&H0081B910&"

def test_keyword_and_emoji_injection():
    # Numbers should be keywords
    assert is_keyword("100jt") is True
    assert is_keyword("50%") is True
    assert is_keyword("$500") is True

    # High emotion / viral words
    assert is_keyword("rahasia") is True
    assert is_keyword("cuan") is True
    assert is_keyword("viral") is True
    assert is_keyword("bukan_kata_kunci_biasa_123") is True
    assert is_keyword("dan") is False
    assert is_keyword("yang") is False

    # Emoji injection
    assert inject_emoji("cuan") == "💰 cuan"
    assert inject_emoji("viral") == "🔥 viral"
    assert inject_emoji("roket") == "🚀 roket"
    assert inject_emoji("target") == "🎯 target"
    assert inject_emoji("bahaya") == "⚠️ bahaya"
    assert inject_emoji("biasa") == "biasa"

def test_single_word_pop_generation():
    sample_words = [
        {"word": "Ini", "start": 0.0, "end": 0.5},
        {"word": "rahasia", "start": 0.5, "end": 1.0},
        {"word": "cuan", "start": 1.0, "end": 1.5},
    ]
    with tempfile.NamedTemporaryFile(suffix=".ass", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        generate_karaoke_ass(
            words=sample_words,
            clip_start=0.0,
            clip_end=2.0,
            output_path=tmp_path,
            motion_type="single_word_pop",
            enable_keyword_color=True,
            keyword_color="#10B981",
            enable_dynamic_scaling=True,
            enable_emoji_injection=True,
        )
        with open(tmp_path, "r", encoding="utf-8") as f:
            content = f.read()

        assert "[Script Info]" in content
        assert "Style: Caption,Poppins,44" in content
        # Check that single_word_pop creates dialogue lines per word with bouncy pop tag
        assert r"\t(0,70,\fscx" in content
        # Check emoji was injected for cuan
        assert "💰" in content
        # Keyword color should be present (&H0081B910&)
        assert "&H0081B910&" in content
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

def test_karaoke_motion_generation():
    sample_words = [
        {"word": "Halo", "start": 0.0, "end": 0.4},
        {"word": "semuanya", "start": 0.4, "end": 0.8},
        {"word": "selamat", "start": 0.8, "end": 1.2},
        {"word": "datang", "start": 1.2, "end": 1.6},
    ]
    with tempfile.NamedTemporaryFile(suffix=".ass", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        generate_karaoke_ass(
            words=sample_words,
            clip_start=0.0,
            clip_end=2.0,
            output_path=tmp_path,
            motion_type="karaoke",
            active_color="#FFE600",
            primary_color="#00F0FF",
            glow_effect=True,
        )
        with open(tmp_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Glow effect outline styling check
        assert "&H0000E6FF&" in content  # active_color as outline when glow_effect is True
        assert r"\fscx108\fscy108" in content
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

def test_background_box_motion_generation():
    sample_words = [
        {"word": "Strategi", "start": 0.0, "end": 0.5},
        {"word": "bisnis", "start": 0.5, "end": 1.0},
        {"word": "terbaik", "start": 1.0, "end": 1.5},
    ]
    with tempfile.NamedTemporaryFile(suffix=".ass", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        generate_karaoke_ass(
            words=sample_words,
            clip_start=0.0,
            clip_end=2.0,
            output_path=tmp_path,
            motion_type="background_box",
            highlight_bg_color="#F59E0B",
        )
        with open(tmp_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Check background box border tag: \3c with highlight_bg_ass and thick border \bord7
        highlight_ass = hex_to_ass("#F59E0B")
        assert f"\\3c{highlight_ass}\\bord7" in content
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

def test_typewriter_motion_generation():
    sample_words = [
        {"word": "Belajar", "start": 0.0, "end": 0.5},
        {"word": "coding", "start": 0.5, "end": 1.0},
        {"word": "itu", "start": 1.0, "end": 1.5},
        {"word": "mudah", "start": 1.5, "end": 2.0},
    ]
    with tempfile.NamedTemporaryFile(suffix=".ass", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        generate_karaoke_ass(
            words=sample_words,
            clip_start=0.0,
            clip_end=2.5,
            output_path=tmp_path,
            motion_type="typewriter",
        )
        with open(tmp_path, "r", encoding="utf-8") as f:
            content = f.read()

        lines = [line for line in content.splitlines() if line.startswith("Dialogue:")]
        assert len(lines) >= 4
        # First dialogue has only the first word
        assert "Belajar" in lines[0]
        # Last dialogue in chunk has all 4 words
        assert "Belajar" in lines[-1] and "mudah" in lines[-1]
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

def test_slide_up_motion_generation():
    sample_words = [
        {"word": "Kutipan", "start": 0.0, "end": 0.5},
        {"word": "inspiratif", "start": 0.5, "end": 1.0},
    ]
    with tempfile.NamedTemporaryFile(suffix=".ass", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        generate_karaoke_ass(
            words=sample_words,
            clip_start=0.0,
            clip_end=2.0,
            output_path=tmp_path,
            motion_type="slide_up",
            margin_v=300,
        )
        with open(tmp_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Check slide up \move and \fad tags
        assert r"\move(540," in content
        assert r"\fad(140,80)" in content
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
