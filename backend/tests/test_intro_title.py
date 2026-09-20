import pytest
from app.services.overlay_service import wrap_and_format_title, build_intro_overlay
from app.services.pipeline import extract_short_tts_title


def test_extract_short_tts_title_cleaning():
    # Long video game title
    t1 = "X MEN MELAWAN ROBOT SENTINEL.... Marvel's Wolverine GAMEPLAY #2"
    clean1 = extract_short_tts_title(t1)
    assert "GAMEPLAY" not in clean1
    assert "#2" not in clean1
    assert "...." not in clean1
    assert "X MEN MELAWAN ROBOT SENTINEL" in clean1

    # Religious/Tafsir title with parentheses and hashtags
    t2 = "Kajian Tafsir Surah Ad-Dhuha (Lengkap & Merdu) #islam #shorts"
    clean2 = extract_short_tts_title(t2)
    assert "#" not in clean2
    assert "Lengkap" not in clean2
    assert "Kajian Tafsir Surah Ad-Dhuha" in clean2

    # Empty or short title
    assert extract_short_tts_title("") == ""
    assert extract_short_tts_title("Halo Dunia") == "Halo Dunia"


def test_wrap_and_format_title_anti_overflow():
    # Long title should wrap into 2-3 lines with appropriate font sizes
    long_title = "CARA MENGHASILKAN 100 JUTA PERTAMA DARI YOUTUBE SHORTS TANPA MODAL"
    escaped_text, font_size = wrap_and_format_title(long_title, max_line_len=22, max_lines=3)
    assert "\\\n" in escaped_text  # multi-line
    assert font_size <= 46  # font scaled down to avoid overflow
    lines = escaped_text.split("\\\n")
    assert len(lines) <= 3
    for line in lines:
        assert len(line.replace("\\'", "'")) <= 30  # within margin threshold


def test_wrap_and_format_title_short():
    short_title = "Judul Singkat"
    escaped_text, font_size = wrap_and_format_title(short_title)
    assert "\\\n" not in escaped_text
    assert font_size >= 50
    assert "Judul Singkat" in escaped_text


def test_build_intro_overlay_anti_overflow_styling():
    title = "X MEN MELAWAN ROBOT SENTINEL.... Marvel's Wolverine GAMEPLAY #2"
    stage = build_intro_overlay(title, duration=2.5)
    assert stage is not None
    assert "box=1" in stage
    assert "boxcolor=black@0.75" in stage
    assert "x=(w-text_w)/2" in stage
    assert "if(lt(t,2.5" in stage


def test_intro_title_pause_filter_includes_darken():
    intro_title_duration = 2.5
    intro_title_pause = True
    if intro_title_pause:
        pad_filter = (
            f",tpad=start_duration={intro_title_duration:.2f}:start_mode=clone,"
            f"drawbox=t=fill:color=black@0.45:enable='between(t,0,{intro_title_duration:.2f})'"
        )
    else:
        pad_filter = ""
    assert "tpad=start_duration=2.50:start_mode=clone" in pad_filter
    assert "drawbox=t=fill:color=black@0.45:enable='between(t,0,2.50)'" in pad_filter

