import math
import os
import struct
import tempfile
import wave
import pytest
from httpx import AsyncClient, ASGITransport

from app.database import init_db
from app.main import app
from app.services.audio_dynamics_service import (
    analyze_vocal_dynamics,
    compute_audio_rms_for_samples,
)
from app.services.ass_service import generate_karaoke_ass
from app.services.ffmpeg_service import _build_video_filtergraph


def create_synthetic_wav(path: str, duration: float = 2.0, sample_rate: int = 16000):
    """
    Creates a 16-bit mono WAV:
    0.0 - 1.0s: Quiet tone (low amplitude 600)
    1.0 - 2.0s: Loud tone (high amplitude 18000)
    """
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        
        frames = []
        total_samples = int(duration * sample_rate)
        half_samples = total_samples // 2
        
        # Quiet part
        for i in range(half_samples):
            val = int(600 * math.sin(2 * math.pi * 440 * i / sample_rate))
            frames.append(struct.pack("<h", val))
            
        # Loud part
        for i in range(half_samples, total_samples):
            val = int(18000 * math.sin(2 * math.pi * 440 * i / sample_rate))
            frames.append(struct.pack("<h", val))
            
        wf.writeframes(b"".join(frames))


def test_compute_audio_rms_for_samples():
    import array
    
    # Silence
    silence = array.array("h", [0] * 1000)
    assert compute_audio_rms_for_samples(silence) == 0.0
    
    # Empty
    empty = array.array("h")
    assert compute_audio_rms_for_samples(empty) == 0.0
    
    # Loud tone
    loud = array.array("h", [10000, -10000] * 500)
    assert compute_audio_rms_for_samples(loud) == 10000.0


def test_analyze_vocal_dynamics_detection():
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_wav = tmp.name

    try:
        create_synthetic_wav(tmp_wav, duration=2.0)
        
        words = [
            {"word": "pelan", "start": 0.1, "end": 0.8},
            {"word": "KERAS", "start": 1.1, "end": 1.9},
        ]
        
        results = analyze_vocal_dynamics(tmp_wav, words, clip_start=0.0, clip_end=2.0)
        assert len(results) == 2
        
        quiet_word = results[0]
        loud_word = results[1]
        
        # Quiet word should have lower energy than loud word and scale <= 1.0
        assert quiet_word["energy_ratio"] < loud_word["energy_ratio"]
        assert quiet_word["scale_multiplier"] <= 1.0
        assert quiet_word["is_vocal_stressed"] is False
        assert quiet_word["energy_level"] in ("low", "normal")
        
        # Loud word should have high energy and scale >= 1.25
        assert loud_word["scale_multiplier"] >= 1.25
        assert loud_word["is_vocal_stressed"] is True
        assert loud_word["energy_level"] == "high"
    finally:
        if os.path.exists(tmp_wav):
            os.remove(tmp_wav)


def test_ass_generation_with_vocal_dynamics_and_glow():
    words = [
        {"word": "Halo", "start": 0.0, "end": 0.5, "scale_multiplier": 0.9, "is_vocal_stressed": False},
        {"word": "DAHSYAT", "start": 0.5, "end": 1.0, "scale_multiplier": 1.30, "is_vocal_stressed": True},
    ]
    
    with tempfile.NamedTemporaryFile(suffix=".ass", delete=False) as tmp:
        tmp_ass = tmp.name

    try:
        generate_karaoke_ass(
            words=words,
            clip_start=0.0,
            clip_end=1.0,
            output_path=tmp_ass,
            motion_type="karaoke",
            glow_effect=True,
            enable_vocal_dynamics=True,
            active_color="#FFCC00",
        )
        
        with open(tmp_ass, "r", encoding="utf-8") as f:
            content = f.read()
            
        # Verify glow effect sets translucent BackColour while preserving black outline
        assert "&H00000000" in content  # OutlineColour is solid black
        assert "&H60" in content  # BackColour contains alpha channel (e.g. &H6000CCFF&)
        
        # Verify dynamic scaling tag \fscx140\fscy140 is injected for the stressed word
        assert r"\fscx140\fscy140" in content
    finally:
        if os.path.exists(tmp_ass):
            os.remove(tmp_ass)


def test_ffmpeg_build_video_filtergraph_layouts():
    sub_filter = "subtitles='/tmp/sub.ass'"

    # 1. Single layout (standard 9:16)
    graph, is_complex = _build_video_filtergraph(
        framing_layout="single",
        crop_mode="center",
        crop_offset_x=0,
        expr=None,
        person_offset_x=0,
        person_offset_y=0,
        screen_offset_x=0,
        screen_offset_y=0,
        screen_scale=1.0,
        screen_aspect="16:9",
        subtitle_filter=sub_filter,
    )
    assert is_complex is False
    assert "subtitles='/tmp/sub.ass'" in graph
    assert "crop=w=ih*(9/16):h=ih" in graph

    # 2. Split top-bottom layout (Orang top, Layar bottom)
    graph_split, is_complex_split = _build_video_filtergraph(
        framing_layout="split_top_bottom",
        crop_mode="center",
        crop_offset_x=0,
        expr=None,
        person_offset_x=40,
        person_offset_y=-20,
        screen_offset_x=10,
        screen_offset_y=15,
        screen_scale=1.1,
        screen_aspect="16:9",
        subtitle_filter=sub_filter,
    )
    assert is_complex_split is True
    assert "split=2" in graph_split
    assert "vstack" in graph_split
    assert "subtitles='/tmp/sub.ass'" in graph_split

    # 3. Split bottom-top layout (Layar top, Orang bottom)
    graph_split_rev, is_complex_split_rev = _build_video_filtergraph(
        framing_layout="split_bottom_top",
        crop_mode="center",
        crop_offset_x=0,
        expr=None,
        person_offset_x=0,
        person_offset_y=0,
        screen_offset_x=0,
        screen_offset_y=0,
        screen_scale=1.0,
        screen_aspect="16:9",
        subtitle_filter=sub_filter,
    )
    assert is_complex_split_rev is True
    assert "split=2" in graph_split_rev
    assert "[v_screen][v_person]vstack" in graph_split_rev

    # 4. Fit 16:9 center layout (Ambient blur)
    graph_fit, is_complex_fit = _build_video_filtergraph(
        framing_layout="fit_16_9_center",
        crop_mode="center",
        crop_offset_x=0,
        expr=None,
        person_offset_x=0,
        person_offset_y=0,
        screen_offset_x=0,
        screen_offset_y=0,
        screen_scale=1.0,
        screen_aspect="16:9",
        subtitle_filter=sub_filter,
    )
    assert is_complex_fit is True
    assert "boxblur" in graph_fit
    assert "overlay=" in graph_fit
    assert "subtitles='/tmp/sub.ass'" in graph_fit

    # 5. PIP Full 9:16 layout (Circular Facecam overlaid on Full 9:16 Screen)
    graph_pip_full, is_complex_pip_full = _build_video_filtergraph(
        framing_layout="pip_full",
        screen_mode="full",
        person_shape="circle",
        person_scale=0.5,
        person_offset_x=20,
        person_offset_y=400,
        subtitle_filter=sub_filter,
    )
    assert is_complex_pip_full is True
    assert "split=2" in graph_pip_full
    assert "geq=" in graph_pip_full  # Circle alpha mask
    assert "overlay=" in graph_pip_full
    assert "subtitles='/tmp/sub.ass'" in graph_pip_full

    # 6. PIP Center 16:9 layout (Rounded Facecam overlaid on Center 16:9 Ambient Blur)
    graph_pip_center, is_complex_pip_center = _build_video_filtergraph(
        framing_layout="pip_center",
        screen_mode="center",
        person_shape="rounded",
        person_scale=0.7,
        person_offset_x=-30,
        person_offset_y=350,
        subtitle_filter=sub_filter,
    )
    assert is_complex_pip_center is True
    assert "boxblur" in graph_pip_center
    assert "drawbox=" in graph_pip_center
    assert "overlay=" in graph_pip_center


def test_pad_expressions_are_quoted():
    """Regresi: koma di dalam min()/max() pada argumen pad HARUS di-quote,
    else parser mengira filter baru ("No such filter: 'min(1080-iw'")."""
    import re
    for layout in ("split_top_bottom", "split_bottom_top", "streamer_face_top", "streamer_face_bottom"):
        graph, _ = _build_video_filtergraph(
            framing_layout=layout, crop_mode="center", crop_offset_x=0,
            video_filter="none", face_cy_ratio=0.25,
        )
        for m in re.finditer(r"pad=1080:\d+:", graph):
            # setelah 'pad=WxH:' harus langsung quote pembuka
            assert graph[m.end()] == "'", f"{layout}: pad x/y tak di-quote: {graph[m.start:m.start+60]}"

def test_video_filter_pack_graph():
    from app.services.ffmpeg_service import VIDEO_FILTERS

    # 1. none = perilaku lama, tanpa grading
    graph_none, _ = _build_video_filtergraph(
        framing_layout="single", crop_mode="center", crop_offset_x=0,
        video_filter="none",
    )
    for fragment in [f for f in VIDEO_FILTERS.values() if f]:
        assert fragment not in graph_none

    # 2. tiap filter valid menempel di graph single
    for name, fragment in VIDEO_FILTERS.items():
        if name == "none":
            continue
        graph, is_complex = _build_video_filtergraph(
            framing_layout="single", crop_mode="center", crop_offset_x=0,
            video_filter=name,
        )
        assert is_complex is False
        assert fragment in graph

    # 3. filter invalid → fallback none
    graph_bad, _ = _build_video_filtergraph(
        framing_layout="single", crop_mode="center", crop_offset_x=0,
        video_filter="tidak_ada",
    )
    assert "eq=" not in graph_bad
    assert "vignette" not in graph_bad

    # 4. layout complex: grading sebelum subtitle burn-in
    sub_filter = "subtitles='/tmp/sub.ass'"
    graph_split, is_complex_split = _build_video_filtergraph(
        framing_layout="split_top_bottom", crop_mode="center", crop_offset_x=0,
        subtitle_filter=sub_filter, video_filter="cinematic",
    )
    assert is_complex_split is True
    assert "[v_graded]" in graph_split
    assert graph_split.index("vignette") < graph_split.index("subtitles=")

    graph_pip, _ = _build_video_filtergraph(
        framing_layout="pip_full", screen_mode="full",
        person_shape="circle", person_scale=0.5,
        subtitle_filter=sub_filter, video_filter="vivid",
    )
    assert "[v_graded]" in graph_pip
    assert graph_pip.index("saturation=1.4") < graph_pip.index("subtitles=")


@pytest.mark.asyncio
async def test_crud_preset_with_multilayout_and_vocal_dynamics():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        await init_db()
        login_res = await ac.post("/api/auth/login", json={"pin": "123456"})
        if login_res.status_code != 200:
            setup_res = await ac.post("/api/auth/setup", json={"pin": "123456"})
            token = setup_res.json()["token"]
        else:
            token = login_res.json()["token"]

        headers = {"Authorization": f"Bearer {token}"}

        payload = {
            "name": "Reaction Pro Multi-Layer",
            "description": "Orang di atas, gameplay di bawah dengan vocal dynamics",
            "crop_mode": "smart",
            "framing_layout": "pip_full",
            "screen_mode": "full",
            "person_shape": "circle",
            "person_scale": 0.65,
            "person_offset_x": 30,
            "person_offset_y": -15,
            "screen_offset_x": 0,
            "screen_offset_y": 10,
            "screen_scale": 1.05,
            "screen_aspect": "16:9",
            "font": "Outfit",
            "font_size": 46,
            "primary_color": "#FFFFFF",
            "active_color": "#FFCC00",
            "subtitle_position": "bottom",
            "margin_v": 320,
            "outline_width": 3,
            "shadow_depth": 2,
            "is_uppercase": True,
            "motion_type": "karaoke",
            "glow_effect": True,
            "enable_vocal_dynamics": True,
        }

        res_create = await ac.post("/api/presets", json=payload, headers=headers)
        assert res_create.status_code == 201
        created = res_create.json()
        preset_id = created["id"]
        assert created["framing_layout"] == "pip_full"
        assert created["screen_mode"] == "full"
        assert created["person_shape"] == "circle"
        assert created["person_scale"] == 0.65
        assert created["person_offset_x"] == 30
        assert created["person_offset_y"] == -15
        assert created["screen_scale"] == 1.05
        assert created["enable_vocal_dynamics"] is True
        assert created["font"] == "Outfit"

        # Verify fetching list contains new preset
        res_get = await ac.get(f"/api/presets/{preset_id}", headers=headers)
        assert res_get.status_code == 200
        fetched = res_get.json()
        assert fetched["name"] == "Reaction Pro Multi-Layer"
        assert fetched["framing_layout"] == "pip_full"
        assert fetched["screen_mode"] == "full"
        assert fetched["person_shape"] == "circle"
        assert fetched["person_scale"] == 0.65
        assert fetched["enable_vocal_dynamics"] is True

        # Clean up
        await ac.delete(f"/api/presets/{preset_id}", headers=headers)

