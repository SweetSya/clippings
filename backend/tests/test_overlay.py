from app.services.overlay_service import (
    escape_drawtext,
    build_intro_overlay,
    build_outro_overlay,
    build_lower_third,
    build_sticker_stage,
    build_drawtext_stages,
)


def test_escape_drawtext():
    assert escape_drawtext("It's: wow") == "It\\'s\\: wow"
    assert escape_drawtext("a,b") == "a,b"
    assert escape_drawtext("") == ""


def test_intro_overlay_timing_and_position():
    stage = build_intro_overlay("Judul Hebat", duration=1.5)
    assert stage is not None
    assert "drawtext=" in stage
    assert "Judul Hebat" in stage
    assert "y='h*0.15" in stage  # atas, jauh dari subtitle bawah
    assert "if(lt(t,1.5" in stage
    assert "box=1" in stage
    assert build_intro_overlay("", duration=1.5) is None
    assert build_intro_overlay("X", duration=0) is None


def test_intro_overlay_anti_overflow():
    long_title = "X MEN MELAWAN ROBOT SENTINEL.... Marvel's Wolverine GAMEPLAY #2"
    stage = build_intro_overlay(long_title, duration=2.5)
    assert stage is not None
    # Pastikan dibungkus jadi multi-baris dan font diperkecil
    assert "\\\n" in stage
    assert "fontsize=38" in stage or "fontsize=42" in stage
    assert "x=(w-text_w)/2" in stage
    assert "box=1" in stage


def test_outro_overlay_last_seconds():
    stage = build_outro_overlay("Follow ya!", video_duration=30.0, cta_duration=2.0)
    assert stage is not None
    assert "gte(t,28.00)" in stage
    assert build_outro_overlay("", 30.0) is None


def test_lower_third():
    stage = build_lower_third("Nama Pembicara")
    assert stage is not None
    assert "y=h*0.70" in stage
    assert build_lower_third("  ") is None


def test_sticker_stage_positions():
    scale_f, ov = build_sticker_stage("top_right", 0.15)
    assert scale_f == "scale=162:-2"
    assert ov == "overlay=W-w-40:40"
    _, ov2 = build_sticker_stage("ngaco", 0.15)
    assert ov2 == "overlay=W-w-40:40"  # fallback posisi
    scale_f3, _ = build_sticker_stage("center", 99.0)
    assert scale_f3 == "scale=540:-2"  # clamp 0.5


def test_build_drawtext_stages_all_off():
    assert build_drawtext_stages({}, 30.0) == []
    assert build_drawtext_stages({"enable_intro_title": True, "intro_title": "Halo"}, 30.0) != []
    cfg = {
        "enable_intro_title": True, "intro_title": "Halo",
        "enable_outro_cta": True, "outro_cta_text": "Bye",
        "enable_lower_third": True, "lower_third_text": "Nama",
    }
    assert len(build_drawtext_stages(cfg, 30.0)) == 3
