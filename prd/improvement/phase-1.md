# Phase 1 — Quick Wins (1-2 minggu)

| Field | Value |
| :--- | :--- |
| **Sumber** | `prd/improvement.md` §8 Phase 1 |
| **Status** | Done — 6/6 (17 Sep 2026) |
| **Urutan** | Ikut PRD, mulai 1.4 |

> Setiap selesai 1 fitur → centang checkbox di bawah + di section detail.
> Verifikasi tiap fitur: `PYTHONPATH=backend python3 -m pytest backend/tests -v`
> Aturan DB: TANPA Alembic, via `PRAGMA table_info` + `ALTER TABLE ADD COLUMN` di `database.py:init_db()`.

## Progress Global

- [x] 1. 1.4 Re-Analyze Klip Individual (S/H)
- [x] 2. 4.2 Preset Export/Import (S/H)
- [x] 3. 4.3 Preset Duplicate (XS/M)
- [x] 4. 6.1 Clip Preview Player (M/H) — sudah ada, tambah label segmen
- [x] 5. 3.3 Animated Text Types Baru (M/M)
- [x] 6. 3.4 Video Filter Pack (S/H)

---

## 1. 1.4 Re-Analyze Klip Individual [x]

**Problem:** Setelah analisis selesai, user tak bisa minta ulang analisis tanpa ulang seluruh pipeline.

**Files:**
- `backend/app/routers/videos.py` — endpoint baru `POST /{video_id}/reanalyze`
- `backend/app/services/pipeline.py:201` — `handle_llm_analyze()` support override via `job.payload`
- `backend/app/schemas/all_schemas.py` — schema `ReanalyzeRequest`
- `frontend/src/pages/ClipStudioPage.tsx` — tombol + modal reanalyze
- `frontend/src/services/api.ts` — `videosApi.reanalyze()`

**Steps:**
- [x] Schema `ReanalyzeRequest {min_dur?, max_dur?, custom_prompt_override?}` dengan validasi (min>0, max>min, prompt max 4000 char)
- [x] Endpoint guard 404 video, 409 bila `EXTRACTING_AUDIO/TRANSCRIBING/ANALYZING`, 404 bila transcript JSON belum ada
- [x] Hapus `ClipCandidate` lama (idempoten) sebelum enqueue `LLM_ANALYZE` dengan payload override
- [x] `handle_llm_analyze` baca override dari `job.payload`, fallback ke settings/global bila kosong; pakai helper setara `pick()` (jangan rantai `or` agar nilai 0/False dihormati)
- [x] Frontend modal: input min/max + custom prompt + konfirmasi; reuse polling status 3s existing
- [x] Test suite hijau

**Acceptance:**
- [x] Reanalyze tanpa upload ulang; klip lama terganti, max 10, overlap suppression jalan
- [x] Override durasi dihormati `validate_and_filter_candidates`
- [x] Gagal LLM → fallback heuristik, job tak hang

---

## 2. 4.2 Preset Export/Import [x]

**Problem:** User tak bisa berbagi/backup preset.

**Files:**
- `backend/app/routers/presets.py` — `GET /{id}/export`, `POST /import`
- `frontend/src/pages/PresetPage.tsx` — tombol Export/Import + file picker
- `frontend/src/services/api.ts` — `presetsApi.exportPreset/importPreset`

**Steps:**
- [x] Export kembalikan JSON preset murni (tanpa `is_builtin/created_at`), sertakan `exported_at` + `app_version`
- [x] Import validasi via `TextPresetCreate`, strip `id/is_builtin`, generate `uuid` baru, selalu `is_builtin=False`
- [x] Frontend: tombol Export per card + Import di header dengan `<input type=file accept=.json>`
- [x] Error JSON rusak → 422 jelas

**Acceptance:**
- [x] Builtin bisa export; hasil import selalu custom
- [x] Roundtrip export→import hasilkan preset identik secara fungsional
- [x] Test suite hijau

---

## 3. 4.3 Preset Duplicate [x]

**Problem:** Tak ada cara duplikat preset sebagai starting point.

**Files:**
- `backend/app/routers/presets.py` — `POST /{id}/duplicate`
- `frontend/src/pages/PresetPage.tsx` — tombol duplicate di card
- `frontend/src/services/api.ts`

**Steps:**
- [x] Endpoint salin semua kolom, nama `Salinan dari {nama}`, `id` baru, `is_builtin=False`
- [x] Boleh duplicate builtin (beda dengan update/delete yang tolak builtin)
- [x] Frontend tombol duplicate (icon Copy) + toast sukses

**Acceptance:**
- [x] Duplikat muncul di custom list, nilai identik kecuali id/nama
- [x] Test suite hijau

---

## 4. 6.1 Clip Preview Player [x] — sudah terimplementasi, verifikasi + label segmen

**Problem:** User hanya lihat metadata klip, tak bisa preview segmen tanpa render.

**Files:**
- `frontend/src/pages/ClipStudioPage.tsx` — inline player di detail editor
- `backend/app/routers/videos.py:463` — verifikasi `Range` support (Starlette `FileResponse` sudah handle)

**Steps:**
- [x] Tambah `<video src=getStreamUrl>` di panel detail dengan `ref` terpisah dari `SubtitleFrame` — SUDAH ADA (`SubtitleFrame` + `videoRef` + `getStreamUrl`)
- [x] `onPlay` seek ke `clip.start`; `onTimeUpdate` pause saat `>= clip.end` (loop segmen) — SUDAH ADA (`selectClipItem:585`, `handleTimeUpdate:637`)
- [x] Kontrol: Putar Segmen / Jeda / Mute + label `start–end` + durasi — SUDAH ADA + tambah label segmen mono
- [x] Ganti klip → reset player, bersihkan state play — SUDAH ADA

**Acceptance:**
- [x] Preview segmen tanpa render; seek akurat ±0.3s
- [x] Ganti klip tak bocor interval/listener

---

## 5. 3.3 Animated Text Types Baru [x]

**Problem:** 5 `motion_type` existing per-kata/chunk saja, tanpa scene-entry dramatis.

**Files:**
- `backend/app/services/ass_service.py:110` — tambah 3 motion
- `backend/app/schemas/all_schemas.py` — izinkan nilai baru
- `frontend/src/pages/PresetEditorPage.tsx:983` — 3 cards baru
- `frontend/src/types/index.ts:168` — tambah ke union type
- `frontend/src/components/SubtitleFrame.tsx:391` — preview CSS approx

**Steps:**
- [x] `bounce_in`: `\move(540,-50,540,target,0,200)` + settle
- [x] `zoom_flash`: `\fscx200\fscy200 → 100` + flash `\1c` kuning→putih; warna via `hex_to_ass()`
- [x] `glitch_reveal`: shake horizontal kecil + inversi sesaat
- [x] Jaga sync `MarginV/ScriptWidth` dengan `SubtitleFrame`
- [x] Semua warna ASS via `hex_to_ass()` (aturan BGR)

**Acceptance:**
- [x] 8 motion render ASS valid + preview konsisten
- [x] Motion lama tak berubah

---

## 6. 3.4 Video Filter Pack [x]

**Problem:** Output selalu sama, tanpa color grading/filter sinematik.

**Files:**
- `backend/app/services/ffmpeg_service.py:128,294` — param `video_filter`
- `backend/app/models/all_models.py:165` — kolom `video_filter`
- `backend/app/database.py:58` — migrasi `PRAGMA` + `ALTER`
- `backend/app/schemas/all_schemas.py` — field `video_filter`
- `backend/app/routers/presets.py:14` — `_to_response/create/update`
- `backend/app/services/pipeline.py:312` — `handle_render` baca via `pick()`
- `frontend/src/pages/PresetEditorPage.tsx` — dropdown + preview

**Steps:**
- [x] Migrasi: `video_filter VARCHAR(20) DEFAULT 'none'`
- [x] FFmpeg postfix filter: `none|cinematic|vivid|warm|cool|drama|vintage` (mapping §3.4 PRD)
- [x] Default `none` = perilaku lama; invalid → fallback `none`, job tak gagal
- [x] Editor dropdown di tab Visual + preview CSS approx

**Acceptance:**
- [x] Tiap filter render sukses; `none` identik output lama
- [x] Test suite hijau (57 passed) + `tsc --noEmit` bersih

---

## Invariant (wajib jaga tiap fitur)

1. ASS warna selalu `hex_to_ass()` (BGR)
2. Preset precedence selalu `pick()`, jangan rantai `or`
3. Face/ffmpeg gagal → fallback, bukan gagal job
4. Ubah `MarginV/ScriptWidth` → update `SubtitleFrame.tsx`
5. Cek `is_drive_uploaded` sebelum upload Drive
6. `PYTHONPATH=backend python3 -m pytest backend/tests -v` tiap fitur
