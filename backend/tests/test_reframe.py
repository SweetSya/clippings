"""Unit tests untuk logika smart reframe (fungsi murni, tanpa FFmpeg)."""

import pytest

from app.services.reframe_service import (
    CropKeyframe,
    HeadSample,
    crop_keyframes_to_expression,
    plan_crop_track,
    smooth_head_track,
)

SRC_W = 1920
SRC_H = 1080
CROP_W = 608          # round(1080 * 9/16)
MAX_X = SRC_W - CROP_W  # 1312
CENTER_X = MAX_X // 2   # 656
BAND = CROP_W // 4      # 152, pita tengah 50%
FIRST_CX = 960.0        # kepala tepat di tengah frame sumber


def samples(*pairs):
    return [HeadSample(t=t, cx=cx) for t, cx in pairs]


def test_head_inside_deadzone_does_not_move():
    """Selama kepala berada di pita tengah 50%, jendela crop diam."""
    track = samples(
        (0.0, FIRST_CX),
        (0.5, FIRST_CX - 100),
        (1.0, FIRST_CX + 120),
        (1.5, FIRST_CX),
        (2.0, FIRST_CX - 60),
    )

    keyframes = plan_crop_track(track, SRC_W, SRC_H, deadzone=0.5)

    assert keyframes == [CropKeyframe(t=0.0, x=CENTER_X, head_cx=FIRST_CX)]


def test_head_crossing_band_moves_to_near_edge_not_center():
    """Kepala melewati tepi pita: jendela bergeser seperlunya, bukan di-recenter."""
    track = samples((0.0, FIRST_CX), (1.0, 1200.0))

    keyframes = plan_crop_track(track, SRC_W, SRC_H, deadzone=0.5, pan_seconds=0.5)

    assert len(keyframes) == 3
    assert keyframes[0] == CropKeyframe(t=0.0, x=CENTER_X, head_cx=FIRST_CX)
    assert keyframes[1].t == pytest.approx(1.0)
    assert keyframes[2].t == pytest.approx(1.5)

    # Tepi kanan pita pada jendela awal = 656 + 304 + 152 = 1112.
    # Bergeser seperlunya menempatkan kepala di tepi pita: 1200 - 456 = 744.
    assert keyframes[2].x == 744
    # Recenter penuh akan menghasilkan 1200 - 304 = 896.
    assert keyframes[2].x != 896


def test_offset_is_clamped_to_source_edges():
    """Kepala di ujung kiri/kanan tidak boleh membuat jendela keluar dari frame."""
    left = plan_crop_track(samples((0.0, 50.0), (1.0, 20.0)), SRC_W, SRC_H)
    right = plan_crop_track(samples((0.0, 1900.0), (1.0, 1910.0)), SRC_W, SRC_H)

    assert left[0].x == 0
    assert all(k.x >= 0 for k in left)

    assert right[0].x == MAX_X
    assert all(k.x <= MAX_X for k in right)


def test_no_head_detected_falls_back_to_center():
    """Tanpa deteksi wajah, crop kembali ke tengah (atau offset manual bila diberikan)."""
    centered = plan_crop_track([], SRC_W, SRC_H)
    manual = plan_crop_track([], SRC_W, SRC_H, fallback_offset=200)

    assert centered == [CropKeyframe(t=0.0, x=CENTER_X, head_cx=None)]
    assert manual == [CropKeyframe(t=0.0, x=200, head_cx=None)]


def test_expression_single_keyframe_is_a_constant():
    assert crop_keyframes_to_expression([]) == "0"
    assert crop_keyframes_to_expression([CropKeyframe(t=0.0, x=CENTER_X)]) == str(CENTER_X)


def test_expression_ramps_linearly_between_two_keyframes():
    expression = crop_keyframes_to_expression([
        CropKeyframe(t=0.0, x=656),
        CropKeyframe(t=3.2, x=744),
    ])

    assert expression == "if(lt(t,3.200),656+t*27.5000,744)"


def test_expression_nests_for_three_keyframes():
    expression = crop_keyframes_to_expression([
        CropKeyframe(t=0.0, x=656),
        CropKeyframe(t=2.0, x=700),
        CropKeyframe(t=5.0, x=800),
    ])

    assert expression == (
        "if(lt(t,2.000),656+t*22.0000,"
        "if(lt(t,5.000),700+(t-2.000)*33.3333,800))"
    )


def test_expression_collapses_flat_segment():
    expression = crop_keyframes_to_expression([
        CropKeyframe(t=0.0, x=656),
        CropKeyframe(t=2.0, x=656),
        CropKeyframe(t=4.0, x=800),
    ])

    assert expression == "if(lt(t,2.000),656,if(lt(t,4.000),656+(t-2.000)*72.0000,800))"


def test_keyframe_count_stays_within_limit():
    """Lintasan yang bergerak sangat sering tetap dipadatkan di bawah batas keyframe."""
    track = samples(*[(i * 0.1, 200.0 if i % 2 else 1700.0) for i in range(600)])

    keyframes = plan_crop_track(track, SRC_W, SRC_H)
    times = [k.t for k in keyframes]

    assert len(keyframes) <= 150
    assert times == sorted(times)
    assert len(set(times)) == len(times)


def test_smoothing_interpolates_short_gap_and_holds_long_gap():
    track = samples((0.0, 500.0), (0.6, 700.0), (5.0, 900.0))

    smoothed = smooth_head_track(track, duration=6.0, frame_width=SRC_W, sample_fps=2.0, ema_alpha=1.0)

    by_time = {round(s.t, 3): s.cx for s in smoothed}
    assert by_time[0.0] == pytest.approx(500.0)
    assert by_time[0.5] == pytest.approx(500.0 + 200.0 * (0.5 / 0.6), abs=0.01)  # gap pendek diinterpolasi
    assert by_time[1.0] == pytest.approx(700.0)                                  # gap panjang ditahan
    assert by_time[4.0] == pytest.approx(700.0)
    assert by_time[5.0] == pytest.approx(900.0)


def test_smoothing_drops_outliers():
    track = samples((0.0, 500.0), (0.6, 700.0), (1.0, 5000.0), (1.6, 720.0))

    smoothed = smooth_head_track(track, duration=2.0, frame_width=SRC_W, sample_fps=2.0, ema_alpha=1.0)

    assert all(s.cx < 1000 for s in smoothed)


def test_snap_recenters_subject_instead_of_landing_on_band_edge():
    """Potongan langsung menaruh kepala di tengah; mendarat di tepi pita akan memicu kedipan."""
    track = samples((0.0, FIRST_CX), (1.0, 1200.0))

    smooth = plan_crop_track(track, SRC_W, SRC_H, deadzone=0.5, pan_seconds=0.5)
    snapped = plan_crop_track(track, SRC_W, SRC_H, deadzone=0.5, pan_seconds=0.5, snap=True)

    assert smooth[-1].x == 744      # tepi pita: 1200 - (304 + 152)
    assert snapped[-1].x == 896     # terpusat: 1200 - 304
    assert snapped[-1].x != smooth[-1].x


def test_snap_emits_step_function_without_interpolation():
    """Kedua keyframe satu potongan berada di waktu yang sama, jadi ekspresinya tanpa transisi."""
    track = samples((0.0, FIRST_CX), (1.0, 1200.0))

    keyframes = plan_crop_track(track, SRC_W, SRC_H, deadzone=0.5, snap=True)
    expression = crop_keyframes_to_expression(keyframes)

    assert len(keyframes) == 3
    assert keyframes[1].t == pytest.approx(1.0)
    assert keyframes[2].t == pytest.approx(1.0)          # tanpa durasi ramp
    assert expression == "if(lt(t,1.000),656,896)"       # murni step, tidak ada suku *t


def test_snap_keeps_cuts_apart():
    """Kepala yang bergerak sangat cepat tidak boleh menghasilkan potongan tiap frame."""
    track = samples(*[(i * 0.1, 200.0 if i % 2 else 1700.0) for i in range(100)])

    keyframes = plan_crop_track(track, SRC_W, SRC_H, pan_seconds=0.0, snap=True)

    cuts = [keyframes[i].t for i in range(1, len(keyframes)) if keyframes[i].x != keyframes[i - 1].x]
    assert len(cuts) > 1

    gaps = [round(b - a, 6) for a, b in zip(cuts, cuts[1:])]
    assert all(gap >= 0.4 for gap in gaps)

    # Setiap potongan harus berupa pasangan pada waktu yang identik
    pairs = [
        (keyframes[i - 1].t, keyframes[i].t)
        for i in range(1, len(keyframes))
        if keyframes[i].x != keyframes[i - 1].x
    ]
    assert all(abs(a - b) < 1e-6 for a, b in pairs)
