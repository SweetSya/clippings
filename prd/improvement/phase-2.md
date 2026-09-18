# Phase 2 — Core AI Improvements (2-4 minggu)

| Field | Value |
| :--- | :--- |
| **Sumber** | `prd/improvement.md` §8 Phase 2 |
| **Status** | Done — 5/5 (17 Sep 2026) |
| **Urutan** | 1.1 → 1.2 → 1.3 → 5.1 → 5.3 (1.3 butuh kolom skor dulu sebelum 5.3 badge; 5.1 mandiri, bisa paralel dengan 1.x) |

> Setiap selesai 1 fitur → centang checkbox di bawah + di section detail.
> Verifikasi tiap fitur: `PYTHONPATH=backend python3 -m pytest backend/tests -v` + `npx tsc --noEmit` di `frontend/`
> Aturan DB: TANPA Alembic, via `PRAGMA table_info` + `ALTER TABLE ADD COLUMN` di `database.py:init_db()`.
> Setting baru (`llm_two_pass_enabled`, `llm_chunk_strategy`) pakai tabel generik `app_settings` via `_get_val`/`_set_val` di `routers/settings.py:52` — tanpa migrasi schema.

## Progress Global

- [x] 1. 1.1 Sequential Two-Pass LLM (M/H)
- [x] 2. 1.2 Smart Chunk Strategy (M/H)
- [x] 3. 1.3 Composite Hook Scoring (M/M)
- [x] 4. 5.1 Face Anchor Analysis (M/H)
- [x] 5. 5.3 Face Coverage Badge (S/M)

---

## 1. 1.1 Sequential Two-Pass LLM [x]

**Problem:** `extract_highlights_with_llm()` (`services/llm_service.py:274`) kirim macro + micro context dalam 1 request. Model kecil (gpt-4o-mini, Ollama lokal) gagal rekonsiliasi → klip tak sesuai tema / kalimat terpotong.

**Files:**
- `backend/app/services/llm_service.py` — fungsi baru `extract_highlights_two_pass()`
- `backend/app/services/pipeline.py:201` — `handle_llm_analyze()` pilih two-pass bila setting aktif
- `backend/app/routers/settings.py` — `_get_val`/`_set_val` key `llm_two_pass_enabled` + response schema
- `backend/app/schemas/all_schemas.py` — `SettingsResponse` + update payload tambah field
- `frontend/src/pages/SettingsPage.tsx` — toggle di tab AI (Koneksi AI)

**Steps:**
- [x] Pass 1 (Macro): input `video_title + video_description + full_text` → output `{video_type, theme_summary, must_avoid_topics, must_include_topics, tone}` (`editorial_brief`)
- [x] Pass 2 (Micro): `editorial_brief` sebagai system context tambahan + timestamped micro-segments → `{clips: [...]}`, reuse `sanitize_and_parse_json:109` + `validate_and_filter_candidates:141`
- [x] Timeout masing-masing 45 detik (total ≤ 90 detik); retry 3x pattern existing boleh disederhanakan per-pass (mis. 2x)
- [x] Pass 1 gagal → fallback single-pass existing (jangan gagalkan job; heuristik `generate_heuristic_highlights:207` tetap lapis terakhir)
- [x] Setting `llm_two_pass_enabled` default `false` (perilaku lama tetap default)
- [x] Frontend toggle + label penjelasan singkat; `videosApi.reanalyze` (Phase 1) otomatis ikut two-pass karena lewat `handle_llm_analyze` yang sama

**Acceptance:**
- [x] Pass 1 hasilkan `editorial_brief` JSON valid
- [x] Pass 2 pakai `editorial_brief` sebagai system context tambahan
- [x] Total timeout dua pass ≤ 90 detik
- [x] Pass 1 gagal → fallback single-pass, job tetap COMPLETED
- [x] Test suite hijau (tambah tes: mock httpx 2 response berurutan → brief diteruskan ke pass 2; mock pass-1 gagal → fallback terpanggil)

---

## 2. 1.2 Smart Chunk Strategy [x]

**Problem:** `format_transcript_for_llm()` (`services/llm_service.py:94`) potong buta (setengah awal + setengah akhir, tengah dibuang). Video 90+ menit kehilangan diskusi terdalam di tengah.

**Files:**
- `backend/app/services/llm_service.py` — `smart_chunk_transcript()` + `extract_highlights_chunked()`
- `backend/app/services/pipeline.py:201` — `handle_llm_analyze()` pilih strategy dari `video.duration_seconds`
- `backend/app/routers/settings.py` — setting `llm_chunk_strategy` (`auto`/`single_pass`/`chunked`)
- `frontend/src/pages/SettingsPage.tsx` — dropdown strategy di tab AI

**Steps:**
- [x] `smart_chunk_transcript(segments, video_duration)`: `num_chunks = max(3, min(6, duration // 1200))` (±1 chunk per 20 menit); chunk berisi segmen temporal berurutan (tanpa potong kalimat — batas chunk di batas segmen)
- [x] LLM sekali per chunk (reuse prompt single-pass existing per chunk + info "bagian X dari N" di user content), kumpulkan kandidat semua chunk
- [x] Meta-ranking: gabung + `validate_and_filter_candidates` global (overlap suppression antar-chunk sudah ada di sana) + max 10
- [x] Routing: `< 30 mnt` single-pass; `30-90 mnt` 3 chunk; `> 90 mnt` 5 chunk (bila `auto`); `single_pass`/`chunked` paksa mode
- [x] Kombinasi dengan 1.1: bila two-pass aktif, Pass 1 macro tetap sekali (full_text), Pass 2 micro per chunk dengan brief yang sama
- [x] Setting default `auto`

**Acceptance:**
- [x] Video < 30 menit: tetap single-pass (1 request)
- [x] Video 30-90 menit: 3-chunk; > 90 menit: 5-chunk
- [x] Overlap suppression antar chunk berjalan
- [x] Klip akhir max 10 (deduplicated)
- [x] Test suite hijau (tambah tes: chunking 60 mnt → 3 chunk batas segmen utuh; mock multi-chunk → gabung max 10)

---

## 3. 1.3 Composite Hook Scoring [x]

**Problem:** `hook_score` murni kualitatif dari LLM (`llm_service.py:141-205`) — bias skor tinggi semua, tanpa validasi independen.

**Files:**
- `backend/app/services/llm_service.py` — `compute_composite_score()` + perkaya `validate_and_filter_candidates()`
- `backend/app/models/all_models.py:62` — `ClipCandidate` tambah `composite_score`, `speech_rate`, `keyword_density`
- `backend/app/database.py:48` — migrasi `PRAGMA clip_candidates` + 3x `ALTER ADD COLUMN`
- `backend/app/schemas/all_schemas.py` — `ClipCandidateResponse` tambah 3 field
- `backend/app/routers/videos.py:491` — `get_video_clips` kembalikan + urut `composite_score` (fallback `hook_score`)
- `backend/app/routers/clips.py:57` — `update_clip` tak perlu ubah (kolom read-only hasil analisis)
- `backend/app/services/pipeline.py:201` — simpan 3 kolom saat insert `ClipCandidate`
- `frontend/src/types/index.ts` — `ClipItem` tambah 3 field opsional
- `frontend/src/pages/ClipStudioPage.tsx` — tampilkan composite di card (ganti/ dampingi Hook Score)

**Steps:**
- [x] Sinyal lokal (pure function, mudah di-test):
  - `speech_rate`: kata/detik segmen klip vs rata-rata video → persentil 0-100
  - `keyword_density`: kepadatan kata `HIGH_EMOTION_KEYWORDS` (`ass_service.py:50`, reuse `is_keyword:92`)
  - `hook_position`: 3 detik pertama klip (kata dari segmen dalam window) mengandung keyword?
- [x] Bobot: LLM 40% + speech 20% + keyword 20% + hook-pos 20% (konstanta bernama, bukan magic number tersebar)
- [x] `validate_and_filter_candidates` hitung ulang per kandidat (butuh `segments` + `full_text` words → tambah param opsional agar signature lama tetap kompatibel di tes existing)
- [x] Migrasi: `composite_score FLOAT DEFAULT 0`, `speech_rate FLOAT DEFAULT 0`, `keyword_density FLOAT DEFAULT 0`; nilai lama 0 = tampilkan `hook_score` sebagai fallback di UI
- [x] Urut `get_video_clips` DESC `composite_score` (COALESCE ke `hook_score` bila 0/null agar klip lama tetap urut wajar)

**Acceptance:**
- [x] Skor akhir = 0.4 LLM + 0.2 speech + 0.2 keyword + 0.2 hook-pos
- [x] Fungsi scoring pure (tanpa I/O) + unit test deterministik
- [x] Klip lama (kolom 0) tetap tampil wajar via fallback
- [x] Test suite hijau (tambah tes: kandidat skor LLM sama → urutan ditentukan sinyal lokal; migrasi kolom ada)

---

## 4. 5.1 Face Anchor Analysis [x]

**Problem:** `reframe_service.py` face detection (YuNet ONNX, `_detect_faces:113` → box `x,y,w,h`) hanya dipakai tracking horizontal (sumbu X). Posisi vertikal wajah (penting untuk layout streamer) tak dianalisis.

**Files:**
- `backend/app/services/reframe_service.py` — `analyze_face_anchor()` + `classify_face_zone()` (baru, pure sebisa mungkin)
- `backend/app/routers/clips.py` — `POST /api/clips/{clip_id}/analyze-face-anchor` (ikuti pola `GET /{clip_id}/reframe-preview:334`)
- `backend/app/schemas/all_schemas.py` — `FaceAnchorResponse {dominant_zone, avg_cx, avg_cy, face_coverage, recommended_layout, recommended_preset_id}`
- `frontend/src/services/api.ts` — `clipsApi.analyzeFaceAnchor()`
- `frontend/src/pages/ClipStudioPage.tsx` — tombol "🎯 Deteksi Posisi Wajah" di tab Visual + toast rekomendasi + tombol "Terapkan Preset"

**Steps:**
- [ ] Reuse `_extract_sample_frames:169` + `_detect_faces:113` (sample 0.5 fps dalam rentang klip); hitung `avg_cx/avg_cy` relatif 0-1 + `face_coverage` (fraksi frame sampel berwajah)
- [ ] `classify_face_zone(avg_cy)`: `< 0.35` → `top`; `> 0.65` → `bottom`; else `center`; kiri/kanan opsional via `avg_cx` bila dibutuhkan layout PIP
- [ ] Rekomendasi preset hanya kategori streamer yang ada: petakan zone → `framing_layout` existing (`split_top_bottom`/`split_bottom_top`/`single`) + `recommended_preset_id` dari preset streamer builtin bila ada, else `null` (jangan hardcode id tak ada — query `TextPreset`.fase ini belum ada kategori preset, lihat catatan)
- [ ] Coverage `< 0.3` → response bawa `warning` (bukan error): "Wajah jarang terdeteksi, smart crop mungkin kurang optimal"
- [ ] Detector `None` (model hilang) → fallback `coverage 0` + warning, JANGAN gagalkan request (invariant degradasi)
- [ ] Target < 10 detik untuk klip 60 detik (0.5 fps = 30 frame deteksi)
- [ ] Frontend: tombol di tab Visual → toast *"Wajah di zona ATAS…"* + tombol terapkan (set `framingLayout` state + `presetId` bila ada)

> Catatan dependensi: kategori preset (`4.1`) baru di Phase 3 — untuk Phase 2, rekomendasi boleh berupa `framing_layout` + preset streamer builtin yang sudah ada (`streamer_pip_circle` dkk. di `database.py`). Jangan buat kolom kategori di fase ini.

**Acceptance:**
- [ ] `analyze_face_anchor()` pure untuk bagian klasifikasi (mudah di-test tanpa video)
- [ ] Analisis < 10 detik untuk klip 60 detik
- [ ] Coverage < 0.3 → warning, bukan error
- [ ] Model hilang → fallback graceful, request tetap 200
- [ ] Test suite hijau (tambah tes: klasifikasi zone batas 0.35/0.65; endpoint tanpa wajah → coverage 0 + warning)

---

## 5. 5.3 Face Coverage Badge [x]

**Problem:** User tak tahu smart crop akan optimal atau tidak untuk suatu klip.

**Files:**
- `backend/app/models/all_models.py:62` — `ClipCandidate` tambah `face_coverage FLOAT DEFAULT 0`
- `backend/app/database.py:48` — migrasi `PRAGMA` + `ALTER ADD COLUMN face_coverage`
- `backend/app/schemas/all_schemas.py` — `ClipCandidateResponse.face_coverage`
- `backend/app/routers/videos.py:491` — sertakan di response
- `backend/app/services/pipeline.py:201` — isi saat analisis (hitung murah dari sampel yang sama dengan 5.1 bila 5.1 sudah dikerjakan; else `detect_head_timeline` cepat / default 0)
- `frontend/src/types/index.ts` — `ClipItem.face_coverage?`
- `frontend/src/pages/ClipStudioPage.tsx` — badge di tiap clip card

**Steps:**
- [x] Kolom `face_coverage FLOAT DEFAULT 0` (0 = belum dianalisis → badge abu "Belum dianalisis", bukan merah)
- [x] Coverage diisi via endpoint `analyze-face-anchor` (5.1) + tersimpan ke klip — SENGAJA tanpa fill di `handle_llm_analyze` (deteksi per klip ±detik × N klip akan melambatkan analisis puluhan detik)
- [x] Badge: 🟢 `≥ 0.7` "Smart crop optimal" · 🟡 `0.3-0.7` "parsial" · 🔴 `< 0.3` (&gt;0) "gunakan center crop" · ⚪ `0/null` "belum dianalisis"
- [x] Endpoint `analyze-face-anchor` (5.1) juga update kolom ini agar badge live tanpa re-analyze

**Acceptance:**
- [x] Tiap klip card tampilkan badge sesuai ambang di atas
- [x] Klip lama (0) tampil abu-abu, bukan merah
- [x] Test suite hijau

---

## Urutan kerja disarankan

1. **1.3 dulu** (kolom skor + migrasi) — fondasi kecil, buka jalan sorting baru
2. **1.1 + 1.2** (bisa paralel setelah 1.3; keduanya sentuh `handle_llm_analyze` + `llm_service`, kerjakan berurutan agar tak konflik: 1.1 dulu baru 1.2 menumpuk chunk di atasnya)
3. **5.1** (mandiri, bisa paralel kapan saja)
4. **5.3** (butuh kolom; isi coverage reuse 5.1 — kerjakan setelah 5.1)

## Invariant (wajib jaga tiap fitur)

1. ASS warna selalu `hex_to_ass()` (BGR) — tak tersentuh fase ini, jangan regresi
2. Preset precedence selalu `pick()` di `pipeline.py`, jangan rantai `or`
3. Smart Reframe / face detection gagal → fallback center crop / coverage 0, TIDAK gagalkan job/request
4. Setting baru lewat `app_settings` generik (`_get_val`/`_set_val`), bukan kolom baru
5. Kolom `clip_candidates` baru lewat `PRAGMA` + `ALTER` di `init_db()`, default 0 agar baris lama aman
6. `PYTHONPATH=backend python3 -m pytest backend/tests -v` + `tsc --noEmit` tiap fitur
