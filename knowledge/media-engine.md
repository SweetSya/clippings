# 🎥 Media Engine & FFmpeg Pipeline (`knowledge/media-engine.md`)

This document details the video and audio processing logic, FFmpeg command flags, 9:16 vertical crop mathematics, ASS subtitle formatting, and color conversion.

---

## 1. Video Cropping & Framing (9:16 Vertical)

Original videos are typically 16:9 landscape ($1920 \times 1080$). Shorts must be rendered in 9:16 vertical ($1080 \times 1920$).

### Framing Modes
1. **Center Crop**:
   - Calculates target width: `target_width = in_h * (9 / 16)`.
   - Offset: `offset_x = (in_w - target_width) / 2`.
   - Filter: `crop=ih*(9/16):ih:(iw-ow)/2:0,scale=1080:1920`.
2. **Manual Shift X**:
   - Allows moving the crop window horizontally to center on a speaker seated on the side.
   - Offset: `offset_x = clamp(0, in_w - target_width, user_offset_x)`.
   - Filter: `crop=ih*(9/16):ih:offset_x:0,scale=1080:1920`.
3. **Smart Reframe (Ikuti Wajah)**:
   - Detects the speaker's head across the clip and pans the crop window to follow it.
   - Implemented in [`backend/app/services/reframe_service.py`](file:///Users/sultanherrysan/Documents/dev/web-development/clipping/backend/app/services/reframe_service.py).
   - Filter: `crop=w=ih*(9/16):h=ih:x='<expression>':y=0,scale=1080:1920`.

> [!NOTE]
> For any source wider than 9:16 (including every 16:9 video), the crop height equals the
> full frame height, so the crop window has **no vertical room to move**. Smart reframe
> therefore only shifts on the X axis. Panning on Y would require a source narrower than 9:16.

### Smart Reframe (Head Tracking)

#### Pipeline

```text
detect_head_timeline()  →  smooth_head_track()  →  plan_crop_track()  →  crop_keyframes_to_expression()
   (FFmpeg + OpenCV)          (buang outlier)        (aturan deadzone)        (ekspresi filter crop)
```

Detection runs on sampled frames (default 2 fps) extracted as small JPEGs by FFmpeg, then
handed to OpenCV's YuNet face detector (`backend/app/assets/face_detection_yunet_2023mar.onnx`).
The first frame containing a face locks the subject: the **largest** detection becomes the
anchor, and later frames pick the detection nearest to the previous position (with a jump
gate of 35% of the frame width to avoid switching speakers). Detection coordinates are
converted back into **source video pixels** so all downstream math shares one space.

#### The deadzone rule

Let `crop_w = round(src_h * 9/16)`, `max_x = max(0, src_w - crop_w)` and
`band = deadzone * crop_w / 2`. The crop window starts centred on the anchor head.

For every sampled head position `cx`:

- If `cx` lies inside `[x + crop_w/2 - band, x + crop_w/2 + band]` → **nothing happens**.
  With the default `deadzone = 0.5`, that band is the middle half of the visible frame.
- If `cx` leaves the band → the window moves **just enough** to put the head back on the
  nearest edge of the band (`cx - (crop_w/2 ∓ band)`), never re-centring, clamped to `[0, max_x]`.
- Each move is emitted as a linear ramp lasting `pan_seconds` (default 0.5s) and samples are
  ignored until the ramp settles, which is what makes the motion read as a camera operator
  rather than a jump cut.

If no face is found at all, the plan collapses to a single keyframe at the centre (or at
`crop_offset_x` when supplied), so the render still succeeds.

#### Snap mode (potongan langsung)

With `smart_snap = true` the window **cuts instantly** instead of panning. Two things change:

1. Both keyframes of a move are emitted at the **same timestamp**, so
   `crop_keyframes_to_expression()` collapses the segment into a step and the resulting
   expression contains no time term at all — e.g. `if(lt(t,9.000),550,if(lt(t,22.500),674,567))`
   versus `if(lt(t,9.000),550,if(lt(t,9.500),550+(t-9.000)*46.0000,...))` for the smooth mode.
2. The target is the **centre** of the frame (`cx - crop_w/2`), not the band edge. Landing on
   the band edge would leave the head exactly on the boundary, so the very next frame would
   trigger another cut — the result flickers.

`pan_seconds` becomes the minimum gap between cuts (never below `SNAP_MIN_INTERVAL`, 0.4s), and
the keyframe-cap escalation lengthens it rather than the ramp. In practice this yields far
fewer, more deliberate moves: on a 30s clip that produced 6 panning adjustments, snap produced
2 hard cuts.

#### Expression generation

`crop_keyframes_to_expression()` turns the timeline into a nested `if()` expression on `t`,
where `t = 0` is the **start of the clip** (FFmpeg removes the seek offset unless `-copyts`
is passed):

```text
if(lt(t,2.000),656+t*22.0000,if(lt(t,5.000),700+(t-2.000)*33.3333,800))
```

The single quotes in `x='<expr>'` protect the expression's commas from the filtergraph
parser, which is what lets it share one `-vf` chain with `ass=...`. Flat segments collapse to
a constant, and at most `REFRAME_MAX_KEYFRAMES` (default 150) keyframes are emitted — beyond
that the plan is recomputed with a longer `pan_seconds` until the count fits.

#### Caching and preview

Detection costs roughly 1-2 seconds per clip, so results are cached at
`storage/reframe/{video_id}_{clip_id}.json`, keyed by clip range, sample rate and source
mtime. `GET /api/clips/{clip_id}/reframe-preview?deadzone=...` returns the head track plus
the planned keyframes; since only the *plan* depends on `deadzone`, dragging the slider
re-plans instantly without re-running detection.

#### Failure behaviour

| Condition | Result |
| :--- | :--- |
| `cv2` not installed, or model file missing | `smart` degrades to centre crop; the render never fails |
| No face detected in the clip | Single keyframe at centre; preview reports `detected: false` |
| FFmpeg rejects the generated expression | One automatic retry with a static crop |
| More keyframes than the cap | Re-planned with a longer pan until it fits |

---

## 2. Advanced SubStation Alpha (`.ass`) Subtitle Generator

Karaoke word-by-word highlight subtitles are generated in [`backend/app/services/media_service.py`](file:///Users/sultanherrysan/Documents/dev/web-development/clipping/backend/app/services/media_service.py).

### Header Configuration
```ini
[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Poppins,44,&H00FFFFFF,&H0000CCFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,3.5,1.5,2,40,40,280,1
```

### Critical Color Format Rule (`&HAABBGGRR&`)
Standard web colors are in RGB: `#RRGGBB`.
The ASS specification requires hexadecimal in **BGR order** with Alpha:
`&H[AA][BB][GG][RR]&`
- `AA`: Alpha transparency (`00` = opaque, `FF` = fully transparent).
- `BB`: Blue component.
- `GG`: Green component.
- `RR`: Red component.

**Conversion Utility**:
```python
def hex_to_ass_color(hex_str: str, alpha: str = "00") -> str:
    cleaned = hex_str.strip().lstrip("#")
    r, g, b = cleaned[0:2], cleaned[2:4], cleaned[4:6]
    return f"&H{alpha}{b}{g}{r}&"
```

### Karaoke Animation Tags
Each dialogue event contains timestamps and word-level karaoke duration tags (`{\k<centiseconds>}`):
```text
Dialogue: 0,0:00:12.40,0:00:15.80,Default,,0,0,0,,{\k35}Ini {\k45}adalah {\k60}momen {\k70}terbaik
```
When burned using `libass`, the active word animates with the highlight color as the speaker speaks.

### Subtitle Placement
- **Bottom** (`Alignment: 2, MarginV: 280`): Positioned above typical TikTok/Shorts UI buttons.
- **Middle** (`Alignment: 5, MarginV: 0`): Centered on screen.
- **Top** (`Alignment: 8, MarginV: 200`): Positioned below top status bar.

---

## 3. FFmpeg Command Construction

### Complete Render Command:
```bash
ffmpeg -y -ss {start_time} -to {end_time} -i "{input_video}" \
  -vf "crop={target_w}:{target_h}:{offset_x}:0,scale=1080:1920,ass='{ass_file_path}'" \
  -c:v libx264 -preset fast -crf 20 -profile:v high \
  -c:a aac -b:a 192k -ar 48000 \
  -movflags +faststart "{output_short_path}"
```

### Progress Parsing
The FFmpeg command is spawned via `asyncio.create_subprocess_exec` with `-progress pipe:1`.
The stdout stream is parsed line-by-line:
- Reads `out_time_ms` or `out_time_us`.
- Computes `progress_pct = int((current_time / clip_duration) * 100)`.
- Updates `RenderedShort.render_progress` in the database so the frontend progress bar moves smoothly.

---

## 4. YouTube Downloader (`yt-dlp`) Integration

Implemented in [`backend/app/services/yt_service.py`](file:///Users/sultanherrysan/Documents/dev/web-development/clipping/backend/app/services/yt_service.py):
- Extracts metadata without downloading using `yt-dlp --dump-single-json`.
- Downloads high-quality video and audio:
  `bestvideo[height<=1080]+bestaudio/best[height<=1080]/best`
- Merges streams to MP4 container using FFmpeg.
- Preserves YouTube video title and description to feed into the **Konteks Besar** pipeline.
