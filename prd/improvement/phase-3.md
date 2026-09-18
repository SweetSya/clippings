# Phase 3 — Creative Features (3-5 minggu)

| Field | Value |
| :--- | :--- |
| **Sumber** | `prd/improvement.md` §8 Phase 3 |
| **Status** | Done — 5/5 (Sep 2026) |
| **Urutan** | Ikut PRD: 3.1 → 3.2 → 4.1 → 5.2 → 2.2 |

> Setiap selesai 1 fitur → centang checkbox di bawah + di section detail.
> Verifikasi tiap fitur: `PYTHONPATH=backend python3 -m pytest backend/tests -v` + `npx tsc --noEmit` di `frontend/`
> Aturan DB: TANPA Alembic, via `PRAGMA table_info` + `ALTER TABLE ADD COLUMN` di `database.py:init_db()`.
> `ClipRenderRequest.model_dump()` (`routers/clips.py:171`) mengalir otomatis ke `pick()` di `handle_render` — field render baru cukup ditambah di schema + dibaca via `pick()`.

## Progress Global

- [x] 1. 3.1 Motion Graphics Overlay (L/H)
- [x] 2. 3.2 Sound Effect Library & Auto-Trigger (L/H)
- [x] 3. 4.1 Preset Category + Built-in Pack (L/H)
- [x] 4. 5.2 Streamer Face Layout Baru (L/H)
- [x] 5. 2.2 Smart Thumbnail Selection (M/M)

---

## 1. 3.1 Motion Graphics Overlay [x]

**Problem:** Output 9:16 hanya crop + subtitle + BGM. Tanpa elemen visual premium (title card, CTA, lower third, stiker).

**Files:**
- `backend/app/services/overlay_service.py` — BARU: `build_intro_overlay()`, `build_outro_overlay()`, `build_lower_third()`, `build_sticker_overlay()`, `resolve_overlay_chain()` (pure, mudah di-test)
- `backend/app/services/ffmpeg_service.py` — `_build_video_filtergraph()` + `render_vertical_clip()` terima `overlay_config: dict`
- `backend/app/models/all_models.py` — `TextPreset` tambah kolom overlay
- `backend/app/database.py` — migrasi PRAGMA + seed default kolom
- `backend/app/schemas/all_schemas.py` — `TextPreset*` + `ClipRenderRequest` tambah field overlay
- `backend/app/routers/presets.py` — `_to_response`/create/update/helper
- `backend/app/services/pipeline.py` — `handle_render()` baca via `pick()` + teruskan ke render
- `frontend/src/pages/PresetEditorPage.tsx` — section "Overlay & Animasi" di tab Visual (DEVIASI dari PRD: bukan tab baru, agar tak rombak navigasi tab)
- `frontend/src/pages/ClipStudioPage.tsx` — teruskan state overlay di payload render + preset apply
- `frontend/src/components/SubtitleFrame.tsx` — preview overlay (title/CTA/lower-third sebagai div absolut)

**Steps:**
- [x] Overlay berbasis FFmpeg `drawtext` (intro 0-1.5s fade via `alpha='if(lt(t,D),t/D,0)'`, outro CTA 2 detik terakhir via `gte(t,DUR-2)`, lower-third strip bawah) — tanpa dependensi font eksternal selain font sistem yang dipakai subtitle
- [x] Stiker: overlay image (PNG/GIF/WebP) dari `storage/stickers/` via `-loop 1` input + `overlay=x:y:enable='between(t,a,b)'`, scale proporsional; file hilang → skip diam-diam (jangan gagalkan job)
- [x] Urutan filter: composite → grade (`video_filter`) → subtitle → overlay graphics (selalu di atas)
- [x] Kolom preset: `enable_intro_title BOOL 0`, `intro_title_duration FLOAT 1.5`, `intro_title_style VARCHAR(20) 'fade_slide'`, `enable_outro_cta BOOL 0`, `outro_cta_text VARCHAR(255)`, `outro_cta_duration FLOAT 2.0`, `enable_lower_third BOOL 0`, `lower_third_text VARCHAR(255)`, `sticker_path VARCHAR(500) NULL`, `sticker_position VARCHAR(20) 'top_right'`, `sticker_scale FLOAT 0.15`
- [x] Semua default OFF → output lama identik bila tak dipakai
- [x] Intro overlay hindari tabrakan subtitle: posisikan di 15% atas (`y=h*0.15`), subtitle tetap bawah

**Acceptance:**
- [x] Intro/outro/lower-third muncul di waktu yang benar, hilang setelah durasinya
- [x] Stiker hilang → render tetap sukses tanpa stiker
- [x] Semua OFF = output identik perilaku lama
- [x] Preview SubtitleFrame konsisten posisi
- [x] Test suite hijau (unit: builder hasilkan fragment drawtext valid + escaping `:`/`'`; render graph mengandung overlay chain)

---

## 2. 3.2 Sound Effect Library & Auto-Trigger [x]

**Problem:** Hanya BGM. Tanpa SFX momen (whoosh, ding, applause).

**Files:**
- `backend/app/models/all_models.py` — model BARU `SFXTrack {id, title, local_path, duration_seconds, file_size_bytes, is_builtin, created_at}`
- `backend/app/database.py` — `create_all` cover tabel baru (tanpa migrasi kolom)
- `backend/app/routers/sfx.py` — BARU: `GET /sfx`, `POST /sfx/upload`, `DELETE /sfx/{id}` (pola `routers/audio.py`)
- `backend/app/main.py` — daftarkan router sfx
- `backend/app/services/sfx_service.py` — BARU: `resolve_sfx_triggers()` (aturan auto) + `build_sfx_chain()` (pure, mudah di-test)
- `backend/app/services/ffmpeg_service.py` — `render_vertical_clip()` terima `sfx_triggers: List[dict]` → `adelay` + `amix`
- `backend/app/services/pipeline.py` — `handle_render()` resolve trigger (manual dari payload + auto dari preset) + teruskan path
- `backend/app/schemas/all_schemas.py` — `SFXTrackResponse`, `ClipRenderRequest.sfx_triggers`, preset fields `sfx_on_hook BOOL`, `sfx_hook_sfx_id`, `sfx_hook_threshold INT 90`
- `backend/app/models/all_models.py` + `database.py` — 3 kolom preset di atas (PRAGMA + CRUD presets)
- `frontend/src/services/api.ts` — `sfxApi`
- `frontend/src/pages/AudioLibraryPage.tsx` — tab "Musik" | "Sound Effects" (upload + putar + hapus)
- `frontend/src/pages/ClipStudioPage.tsx` — panel SFX di tab Audio (pilih SFX + offset detik + aturan hook otomatis)

**Steps:**
- [x] Upload SFX (mp3/wav/ogg ≤ 5MB) ke `storage/sfx/`; stream endpoint untuk preview; builtin flag untuk paket bawaan
- [x] Trigger manual: `[{sfx_id, start_t, volume}]` dari ClipStudio → resolve ke path absolut, file hilang → skip
- [x] Trigger auto: bila preset `sfx_on_hook` dan `composite_score >= sfx_hook_threshold` → mainkan SFX di 0.5s pertama (volume 0.8)
- [x] FFmpeg: tiap SFX `[i:a]adelay=ms|ms,volume=v[aN]` + `amix` dengan trek existing (voice/BGM/ori); tanpa SFX → jalur audio lama tak berubah
- [x] DEVIASI dari PRD: tanpa 10 file SFX bawaan biner (tak bisa kirim aset audio) — library + upload + aturan yang dibangun; slot `is_builtin` disiapkan untuk paket kelak

**Acceptance:**
- [x] Upload–preview–hapus SFX lewat UI
- [x] Render dengan 2 trigger manual → kedua SFX terdengar di offset benar (verifikasi via durasi/stream, bukan telinga)
- [x] Klip skor ≥ threshold + auto ON → fanfare di awal; di bawah threshold → tidak ada
- [x] SFX hilang/rusak → render tetap sukses tanpa SFX itu
- [x] Test suite hijau (unit: `build_sfx_chain` hasilkan adelay/amix benar; API CRUD SFX)

---

## 3. 4.1 Preset Category + Built-in Pack [x]

**Problem:** Tanpa kategorisasi; user konfigurasi dari nol; tanpa preset streamer/podcast/edukasi/motivasi/gaming.

**Files:**
- `backend/app/models/all_models.py` — `TextPreset` tambah `category VARCHAR(20) 'text'`, `thumbnail_preview VARCHAR(500) NULL` (`description` sudah ada)
- `backend/app/database.py` — migrasi PRAGMA + seed 8 preset baru + UPDATE/INSERT sertakan kolom
- `backend/app/routers/presets.py` — `GET /presets?category=` filter + sertakan di CRUD/helper
- `backend/app/schemas/all_schemas.py` — 2 field di `TextPreset*`
- `frontend/src/types/index.ts` — `TextPreset.category?`
- `frontend/src/pages/PresetPage.tsx` — group by kategori + chips filter
- `frontend/src/pages/PresetEditorPage.tsx` — dropdown kategori di tab Info
- `frontend/src/pages/ClipStudioPage.tsx` — chips kategori di preset picker

**Steps:**
- [x] Kategori: `text` (existing, default) | `full` | `streamer` | `podcast` | `educational` | `motivational` | `gaming`
- [x] 8 seed (isi kolom lengkap guterpakai default sehat): `preset_streamer_face_top`, `preset_streamer_face_bottom`, `preset_streamer_pip_right`, `preset_podcast_clean`, `preset_podcast_cinematic`, `preset_edu_minimal`, `preset_motivasi_fire`, `preset_gaming_impact` (mapping gaya dari PRD §4.1; `framing_layout` pakai nilai existing — `streamer_face_*` diganti `split_*` sampai 5.2 jadi, lalu diupgrade seed-nya di 5.2)
- [x] `reset-builtins` ikut menanam kategori baru (pola existing)
- [x] Filter `GET /api/presets?category=streamer`; tanpa param = semua (kompatibel)
- [x] UI: grup + chip; duplikat/import/export (Phase 1) pertahankan kategori

**Acceptance:**
- [x] 8 preset baru muncul setelah `reset-builtins`, tergrup benar
- [x] Filter kategori API + UI berfungsi
- [x] Export→import pertahankan kategori
- [x] Test suite hijau

---

## 4. 5.2 Streamer Face Layout Baru [x]

**Problem:** `split_top_bottom/bottom_top` belah mekanis satu input. Butuh layout sadar zona wajah (butuh 5.1 ✅).

**Files:**
- `backend/app/services/ffmpeg_service.py` — `_build_video_filtergraph()` kasus `streamer_face_top` + `streamer_face_bottom` (param `face_cy_ratio`)
- `backend/app/services/pipeline.py` — `handle_render()` pre-analysis face anchor bila layout streamer (reuse `analyze_face_anchor`, gagal → fallback `split_*` setara, JANGAN gagalkan job)
- `backend/app/services/reframe_service.py` — tak perlu fungsi baru (reuse 5.1)
- `backend/app/schemas/all_schemas.py` — dokumentasikan 2 nilai layout baru di `framing_layout` (tak ada enum ketat)
- `frontend/src/types/index.ts` — `FramingLayout` tambah 2 nilai
- `frontend/src/pages/PresetEditorPage.tsx` — opsi layout + ilustrasi + upgrade 2 seed streamer (4.1) ke layout baru
- `frontend/src/pages/ClipStudioPage.tsx` — opsi layout di picker visual + `SubtitleFrame` render
- `frontend/src/components/SubtitleFrame.tsx` — pratinjau 2 layout (face 40% + konten 60%)

**Steps:**
- [x] `streamer_face_top`: 40% atas = crop zona wajah (face tracking horizontal existing via `expr`), 60% bawah = sisa konten; `bottom` kebalikannya; `face_cy_ratio` dari `avg_cy` analisis (clamp 0.15-0.35)
- [x] Pipeline: bila `framing_layout startswith 'streamer_face'` → `analyze_face_anchor()` → teruskan `face_cy_ratio`; exception → fallback `split_top_bottom`/`split_bottom_top`
- [x] Validasi layout tak dikenal tetap seperti lama (single) — jangan 500
- [x] Seed 4.1 `preset_streamer_face_top/bottom` diupgrade ke layout baru via UPDATE seed

**Acceptance:**
- [x] Graph untuk kedua layout valid (vstack face+konten, dimensi 1080x1920)
- [x] Face analysis gagal → fallback split, render sukses
- [x] Test suite hijau (unit graph + fallback)

---

## 5. 2.2 Smart Thumbnail Selection [x]

**Problem:** Thumbnail detik-1 statik (`ffmpeg_service.py:67`) — sering blur / wajah tertutup.

**Files:**
- `backend/app/services/ffmpeg_service.py` — `select_best_thumbnail()` BARU + param `smart: bool` di `generate_thumbnail()`
- `backend/app/services/reframe_service.py` — reuse `_detect_faces()` untuk skor wajah
- `backend/app/routers/videos.py:84` + `pipeline.py:103,144` — pakai mode smart
- Sharpness: Laplacian variance via OpenCV (`cv2.Laplacian(...).var()`); tanpa cv2 → fallback seek detik-1 (jangan gagalkan upload)

**Steps:**
- [x] Ambil N=10 kandidat merata di window [max(0,seek-2), seek+8]s (JPEG kecil 480px)
- [x] Skor = `0.6 * face_norm + 0.4 * sharp_norm` (face = luas box terbesar / luas frame; sharp = normalisasi min-max antar kandidat); pilih tertinggi, simpan ke `thumb_path`; gagal total → fallback detik-1
- [x] DEVIASI dari PRD: dipakai untuk thumbnail video sumber (upload + pipeline), bukan per klip (tak ada thumbnail per klip saat ini) — fungsi umum siap dipakai per klip kelak
- [x] Bersihkan JPEG kandidat sementara

**Acceptance:**
- [x] Upload tetap hasilkan thumbnail walau semua kandidat gagal (fallback)
- [x] Test suite hijau (unit skor dengan frame sintetis: tajam+berwajah menang; tanpa cv2 → fallback)

---

## Urutan kerja disarankan

Ikut PRD (3.1 → 3.2 → 4.1 → 5.2 → 2.2). 4.1 sebelum 5.2 sudah terpenuhi bila ikut urutan.

## Invariant (wajib jaga tiap fitur)

1. Filter/efek gagal → fallback (tanpa overlay/SFX/filter), TIDAK gagalkan job
2. Semua default OFF/`none` → output identik perilaku lama
3. Preset precedence `pick()`, jangan rantai `or`
4. Kolom preset baru via PRAGMA + ALTER; tabel baru via `create_all`
5. Warna ASS tetap `hex_to_ass()`; `MarginV/ScriptWidth` sync dengan `SubtitleFrame`
6. `pytest` + `tsc --noEmit` tiap fitur
