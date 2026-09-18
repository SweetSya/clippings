# Phase 4 — Vision & Infrastructure (4-6 minggu)

| Field | Value |
| :--- | :--- |
| **Sumber** | `prd/improvement.md` §8 Phase 4 |
| **Status** | Done — 4/4 (Sep 2026) |
| **Urutan** | 7.1 (verifikasi, sudah ada) → 7.2 → 6.4 → 2.1 (mandiri, bisa paralel kapan saja) |

> Setiap selesai 1 fitur → centang checkbox di bawah + di section detail.
> Verifikasi tiap fitur: `PYTHONPATH=backend python3 -m pytest backend/tests -v` + `npx tsc --noEmit` di `frontend/`
> Aturan DB: TANPA Alembic, via `PRAGMA table_info` + `ALTER TABLE ADD COLUMN` di `database.py:init_db()`.
> Setting baru lewat tabel generik `app_settings` (`_get_val`/`_set_val` di `routers/settings.py:37`), bukan kolom baru.

## Progress Global

- [x] 1. 2.1 Vision-Aware Clipping (XL/H)
- [x] 2. 7.1 Parallel Render Workers (M/H) — sudah terimplementasi, tinggal verifikasi
- [x] 3. 7.2 Transcript Cache Invalidation (M/M)
- [x] 4. 6.4 Dark Mode Support (M/M)

---

## 1. 2.1 Vision-Aware Clipping [x]

**Problem:** Sistem hanya analisis **teks** (transkrip Whisper). Momen visual (ekspresi intens, gestur dramatis, slide penting, reaksi wajah) tak terdeteksi.

**Files:**
- `backend/app/services/vision_service.py` — BARU: `extract_visual_highlights()`, `batch_frames_to_grid()`, `analyze_frames_with_vision()`
- `backend/app/services/llm_service.py:431` — `extract_highlights_with_llm()` + `extract_highlights_chunked()` + `extract_highlights_two_pass()` terima `vision_boost: Optional[dict]` (timestamp → skor) untuk menaikkan composite kandidat di sekitar momen visual
- `backend/app/services/pipeline.py:201` — `handle_llm_analyze()` jalankan vision pass sebelum text LLM bila setting aktif
- `backend/app/routers/settings.py` — `_get_val`/`_set_val` key `llm_vision_enabled`, `llm_vision_model`, `llm_vision_weight`
- `backend/app/schemas/all_schemas.py` — `AISettingsRequest` + `SettingsResponse` tambah 3 field
- `frontend/src/pages/SettingsPage.tsx` — toggle + model + slider bobot di tab AI

**Steps:**
- [x] Ekstrak 1 frame per 2 detik (`ffmpeg -r 0.5`, JPEG ≤ 512px) di window analisis; batch ke grid 4x4 (16 frame/gambar) via OpenCV/Pillow agar hemat request
- [x] Kirim grid ke Vision LLM (OpenAI-compatible `chat/completions` dengan `image_url` base64, reuse helper `_post_chat`) dengan prompt identifikasi ekspresi/gestur/slide/momen "wow" → `{timestamp, visual_score, description}[]`
- [x] Gabung ke composite: kandidat dengan momen visual dalam rentangnya dapat boost `visual_score * llm_vision_weight` (default weight `0.3`, max boost dibatasi agar teks tetap dominan); tanpa `vision_boost` → perilaku lama identik
- [x] Vision pass opsional (default OFF), gagal/timeout → lanjut text analysis tanpa boost (JANGAN gagalkan job); model tanpa image support → degrade graceful via pesan error API
- [x] Bersihkan frame/grid sementara; batasi total request (mis. max 8 grid per video) agar biaya terkendali

**Acceptance:**
- [x] Vision OFF = output identik single-pass lama
- [x] Vision ON + mock respons → kandidat di sekitar timestamp visual naik peringkat
- [x] Vision gagal/timeout → job tetap COMPLETED tanpa boost
- [x] Test suite hijau (unit: grid batching 16 frame; merge boost dengan bobot; tanpa cv2/PIL → skip graceful)

---

## 2. 7.1 Parallel Render Workers [x] — sudah ada, verifikasi saja

**Status awal:** Sudah terimplementasi — `worker.py:24-25` (`_transcribe_sem`, `_render_sem`), `config.py:24-25` (`TRANSCRIBE_CONCURRENCY=1`, `RENDER_CONCURRENCY=2`), terdokumentasi di `.env.example:31-32`. PRD §7.1 minta `MAX_PARALLEL_RENDERS` default 2 — terpenuhi secara fungsi via `RENDER_CONCURRENCY`.

**Files (bila perlu sentuh):**
- `backend/app/worker.py` — `_execute_job()` + semafor
- `backend/app/config.py` — nilai default
- `.env.example` — dokumentasi (sudah ada)

**Steps:**
- [x] Verifikasi: antre 3+ job RENDER → max 2 berjalan paralel (`RENDERING`), sisanya `QUEUED`; job non-render tetap sequential sesuai semafornya
- [x] Verifikasi `handle_render` aman konkurensi (crop cache per `clip_id` di `reframe_service.get_head_samples`, output per `short_id` — tak ada file bersama)
- [x] Bila ditemukan race (mis. log/progress `job.progress` tertimpa), perbaiki dengan scope session per job (sudah per job di `_execute_job`)
- [x] Tambah tes konkurensi ringan bila belum ada (mock 3 render cepat → wall-time < 3x serial)

**Acceptance:**
- [x] 2 render berjalan paralel, non-render tak saling blokir render
- [x] Tak ada race pada file output/progress
- [x] Test suite hijau

---

## 3. 7.2 Transcript Cache Invalidation [x]

**Problem:** Upload video sama dua kali → Whisper transkripsi ulang dari nol.

**Files:**
- `backend/app/models/all_models.py` — `SourceVideo` tambah `file_hash VARCHAR(64) NULL`
- `backend/app/database.py` — migrasi PRAGMA + ALTER
- `backend/app/routers/videos.py` — `upload_video` + `download_yt_video`: hitung hash 1MB pertama saat simpan; bila hash cocok video lain yang punya transkrip → salin `transcript_json_path` + status lompat ke `TRANSCRIBING` selesai (enqueue `LLM_ANALYZE` langsung, skip `AUDIO_EXTRACT`/`TRANSCRIBE`)
- `backend/app/services/pipeline.py` — `handle_transcribe()` update `file_hash` bila kosong (untuk video lama)

**Steps:**
- [x] Hash = SHA256 dari 1MB pertama berkas (cepat, cukup untuk dedup praktis); helper pure `hash_file_head(path, n_bytes)` di `storage_service.py` (mudah di-test)
- [x] Lookup: `SourceVideo.file_hash == hash AND id != new_id` + ada `Transcript` → salin baris `Transcript` (id baru) + salin file JSON `transcripts/{new_id}.json` + enqueue `LLM_ANALYZE` saja
- [x] Tak cocok → alur lama tak berubah; `file_hash` tetap disimpan untuk upload berikutnya
- [x] Video lama (hash NULL) → diisi saat transcribe berikutnya; tak ada backfill massal

**Acceptance:**
- [x] Upload duplikat → analisis klip tanpa transcribe ulang (cek job: tanpa `TRANSCRIBE`)
- [x] File beda 1 byte setelah 1MB pertama → tetap dianggap sama (dokumentasikan batasan di kode)
- [x] Test suite hijau (unit hash deterministik; API: upload 2x file sama → klip muncul tanpa job transcribe)

---

## 4. 6.4 Dark Mode Support [x]

**Problem:** Ember Studio warm-white only. Kendala: warna hardcoded (`text-[#1C1917]` dkk., ratusan pemakaian di ~10 file) — retrofit penuh tak realistis sekali jalan.

**Files:**
- `frontend/tailwind.config.js` — `darkMode: 'class'` + peta warna `ember.*` ke CSS variables
- `frontend/src/index.css` — `:root` + `.dark` variable set + `body` pakai variable + `color-scheme`
- `frontend/src/components/Sidebar.tsx` — pakai variable (navigasi selalu terlihat)
- `frontend/src/pages/SettingsPage.tsx` — toggle tema (Light/Dark/Sistem) tersimpan di `localStorage`
- Bertahap: halaman lain migrasi dari hex hardcoded ke token `ember-*`/variable per halaman

**Steps:**
- [x] Definisikan token: `--bg`, `--surface`, `--surface-raised`, `--text`, `--text-dim`, `--border` untuk light (nilai existing) + dark (stone-950/900/800, text stone-100/400)
- [x] `tailwind.config.js`: `darkMode: 'class'`, warna `ember.background/surface/text-*/border` → `var(...)` agar kelas existing ikut tema tanpa ubah semua file
- [x] Toggle di Settings + hormati `prefers-color-scheme` saat pertama kali (value `system`); class `dark` di `document.documentElement`
- [x] Arbitrary hex (`[#1C1917]` dkk.) TETAP light-only di fase ini — dicatat sebagai tech debt, migrasi per halaman menyusul (mulai Sidebar + SettingsPage sebagai contoh)
- [x] SubtitleFrame preview TIDAK ikut dark mode (pratinjau video harus WYSIWYG)

**Acceptance:**
- [x] Toggle Light/Dark/System berfungsi + persisten reload
- [x] Sidebar + SettingsPage rapi di kedua mode; halaman lain tetap terbaca (fallback light)
- [x] `tsc --noEmit` bersih; tak ada regresi visual mode light (screenshot-compare manual)

---

## Urutan kerja disarankan

1. **7.1** dulu (verifikasi cepat, fondasi worker)
2. **7.2** (kecil, mandiri)
3. **6.4** (frontend saja, bisa paralel dengan 7.2)
4. **2.1** terakhir (XL, mandiri, butuh fokus; manfaatkan `_post_chat` + pola fallback Phase 2)

## Invariant (wajib jaga tiap fitur)

1. Fitur gagal (vision/timeout/model hilang) → degradasi graceful, TIDAK gagalkan job
2. Default OFF → perilaku lama identik (vision, dark mode, cache tak mengubah alur normal)
3. Kolom baru via PRAGMA + ALTER; setting baru via `app_settings` generik
4. Worker: session per job, tak ada file output bersama antar job paralel
5. Subtitle preview (SubtitleFrame) tak ikut tema/filter UI
6. `pytest` + `tsc --noEmit` tiap fitur
