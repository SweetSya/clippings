# Phase 5 — YouTube Auto-Upload & AI SEO (2-3 minggu)

| Field | Value |
| :--- | :--- |
| **Sumber** | `prd/improvement.md` §8.1, §8.2, §9.1, §9.2 + §14 Phase 5 |
| **Status** | Done — 4/4 (Sep 2026) |
| **Urutan** | 8.1 → 9.1 → 9.2 → 8.2 (fondasi upload dulu, SEO sejajar, modal terakhir memakai keduanya) |

> Setiap selesai 1 fitur → centang checkbox di bawah + di section detail.
> Verifikasi tiap fitur: `PYTHONPATH=backend python3 -m pytest backend/tests -v` + `npx tsc --noEmit` di `frontend/`
> Aturan DB: TANPA Alembic, via `PRAGMA table_info` + `ALTER TABLE ADD COLUMN` di `database.py:init_db()`; tabel baru via `create_all`.
> Setting baru lewat tabel generik `app_settings` (`_get_val`/`_set_val` di `routers/settings.py:37`), bukan kolom baru.
> Pola acuan: GDrive (`gdrive_service.py:86,102,188`, `shorts.py:105,206`, `pipeline.py:755`, `worker.py:90`) dan narasi (`clips.py:198`).

## Progress Global

- [x] 1. 8.1 YouTube Data API Integration — OAuth 2.0 + resumable upload (L/🔴)
- [x] 2. 9.1 AI SEO Generator — title/desc/tags/hashtags (M/🔴)
- [x] 3. 9.2 Platform-Specific SEO Templates (S/🟡)
- [x] 4. 8.2 Upload Modal + Metadata Editor (M/🔴)

---

## 1. 8.1 YouTube Data API Integration [x]

**Problem:** Hanya ekspor ke Google Drive. Publish ke YouTube Shorts masih manual (download → YouTube Studio → isi metadata).

**Files:**
- `backend/app/services/youtube_upload_service.py` — BARU: `get_auth_url()`, `exchange_code()`, `refresh_access_token()`, `upload_video()` (resumable), `set_thumbnail()`
- `backend/app/routers/youtube_upload.py` — BARU: `POST /auth-url`, `POST /exchange`, `POST /test`, `GET /channel-info`, `POST /shorts/{id}/upload-youtube`, `GET /shorts/{id}/youtube-status`, `POST /shorts/batch-upload-youtube`
- `backend/app/models/all_models.py` — model BARU `YouTubeExport` + `RenderedShort.is_youtube_uploaded`
- `backend/app/database.py` — migrasi PRAGMA (`is_youtube_uploaded`); `youtube_exports` via `create_all`
- `backend/app/services/pipeline.py` — `handle_youtube_upload()` (mirror `handle_gdrive_upload:755`)
- `backend/app/worker.py` — register `YOUTUBE_UPLOAD` (handler + `_mark_entity_failed`)
- `backend/app/routers/settings.py` — settings `yt_upload_client_id`, `yt_upload_client_secret` (encrypted), `yt_upload_refresh_token` (encrypted), `yt_upload_connected`, `yt_upload_channel_name`
- `backend/app/schemas/all_schemas.py` — `YouTubeExportResponse`, `YouTubeUploadRequest`, settings fields
- `backend/app/main.py` — register router
- `frontend/src/pages/SettingsPage.tsx` — tab baru `youtube` (mirror tab `gdrive:616,1126`): Client ID/Secret → Connect → test → channel info
- `frontend/src/services/api.ts` — `youtubeApi`
- `frontend/src/types/index.ts` — `YouTubeExport` interface

**Steps:**
- [x] OAuth 2.0 mirror GDrive: consent URL (scope `youtube.upload` + `youtube.readonly`, invariant 6) → exchange code → simpan refresh_token encrypted → test via `channels?mine=true`
- [x] Resumable upload: init session (`uploadType=resumable`, metadata JSON) → PUT chunk 8MB dengan `Content-Range` → retry chunk gagal (max 3x) → ambil `video_id`
- [x] Job worker: `QUEUED → UPLOADING (progress per chunk) → SUCCESS/FAILED`; simpan `youtube_video_id` + `youtube_url`
- [x] Anti-double upload: cek `is_youtube_uploaded` sebelum enqueue (mirror `shorts.py:111`, invariant 5); respons `ALREADY_UPLOADED` bila sudah
- [x] `set_thumbnail()` best-effort setelah upload (gagal thumbnail ≠ gagal upload; catat warning)
- [x] Redirect URI: `http://localhost:8000/api/youtube/callback` (mirror `settings.py` GDrive callback); dokumentasikan di Settings + `.env.example`

**Acceptance:**
- [x] OAuth end-to-end: authorize → exchange → test → channel tampil
- [x] Upload resumable: putus di tengah → resume lanjutkan (tes via mock chunk kedua gagal sekali)
- [x] Double upload dicegah via `is_youtube_uploaded`
- [x] Progress 0→100% terpantau via polling status
- [x] Thumbnail custom opsional, gagal thumbnail tak gagalkan upload
- [x] Test suite hijau (unit: Content-Range builder, retry chunk; API: enqueue + guard double; OAuth exchange via mock httpx)

---

## 2. 9.1 AI SEO Generator [x]

**Problem:** `ClipCandidate.title` untuk internal, bukan metadata siap-publish. Tanpa deskripsi SEO, tags, hashtags.

**Files:**
- `backend/app/services/seo_service.py` — BARU: `generate_youtube_seo()`, `generate_tiktok_seo()` + `SEO_SYSTEM_PROMPT`
- `backend/app/models/all_models.py` — `ClipCandidate` tambah `seo_titles` (JSON), `seo_description` (Text), `seo_tags` (JSON), `seo_hashtags` (JSON)
- `backend/app/database.py` — migrasi PRAGMA 4 kolom
- `backend/app/schemas/all_schemas.py` — `SEOGenerateRequest {platform, language}`, `SEOGenerateResponse`
- `backend/app/routers/clips.py` — `POST /{clip_id}/generate-seo` (mirror `generate-narration:198`: ambil konteks klip + video, panggil service, simpan ke klip)
- `frontend/src/services/api.ts` — `clipsApi.generateSeo()`

**Steps:**
- [x] Konteks: `clip.title` + teks transkrip rentang klip + `video.original_name/description/video_type` + durasi (pola `generate_clip_narration`)
- [x] Output LLM: 3 opsi judul (≤60 chars, 1 emoji, curiosity gap) + deskripsi (hook 2-3 baris + CTA + `#shorts`, ≤500 chars) + 8-15 tags campuran ID/EN + 3-6 hashtags (`#shorts` wajib) + `category_suggestion`
- [x] Validasi + normalisasi: potong judul >60 chars, pastikan `#shorts` ada, dedup tags/hashtags, fallback template heuristik bila LLM tak connected (mirror pola fallback narasi)
- [x] Simpan hasil ke kolom SEO klip agar modal upload (8.2) bisa preload tanpa regenerate
- [x] Aturan per platform didelegasikan ke tabel 9.2 (satu sumber kebenaran, bukan duplikat prompt)

**Acceptance:**
- [x] 3 opsi judul valid, deskripsi ada CTA + hashtags
- [x] Tags 8-15 campuran ID/EN; hashtags ≤6 dengan `#shorts`
- [x] LLM mati → template heuristik tetap hasilkan metadata wajar
- [x] Test suite hijau (unit: normalisasi/potong/dedup; API: generate-seo simpan ke klip; mock LLM)

---

## 3. 9.2 Platform-Specific SEO Templates [x]

**Problem:** Aturan SEO beda per platform (YouTube vs TikTok vs Reels) — jangan duplikat di tiap prompt.

**Files:**
- `backend/app/services/seo_service.py` — `PLATFORM_SEO_RULES` + `apply_platform_rules()` (satu sumber kebenaran dipakai 9.1)
- `backend/app/services/llm_service.py` — tak perlu ubah (konsumsi via seo_service saja)

**Steps:**
- [x] Tabel aturan: `youtube_shorts` (title ≤100, desc ≤5000, `#shorts` wajib, tags ≤15, category map gaming→20/education→27/entertainment→24/default→22), `tiktok` (caption ≤2200, `#fyp`+`#foryou` wajib, hashtags ≤10), `instagram_reels` (caption ≤2200, `#reels`, hashtags ≤30)
- [x] `apply_platform_rules(platform, seo_dict)` pure: potong, suntik required hashtags, batasi jumlah, petakan kategori → dipakai setelah generate LLM maupun template
- [x] `platform` tak dikenal → fallback `youtube_shorts` (jangan 500)

**Acceptance:**
- [x] Tiap platform lolos batasnya setelah `apply_platform_rules`
- [x] Required hashtags selalu hadir, duplikat hilang
- [x] Test suite hijau (unit per platform + fallback)

---

## 4. 8.2 Upload Modal + Metadata Editor [x]

**Problem:** Tombol upload GDrive (`ShortsPage.tsx:72`) langsung antre tanpa form metadata. YouTube butuh title/desc/tags/privacy/thumbnail.

**Files:**
- `frontend/src/pages/ShortsPage.tsx` — komponen `YouTubeUploadModal` (thumbnail 9:16 + field + tombol AI + privacy + upload)
- `frontend/src/services/api.ts` — `shortsApi.uploadYoutube()`, `youtubeStatus()`
- `frontend/src/types/index.ts` — `YouTubeUploadPayload`
- `backend/app/routers/youtube_upload.py` — `POST /shorts/{id}/upload-youtube` terima metadata modal (validasi: title 1-100 chars invariant 8, privacy enum)

**Steps:**
- [x] Modal: thumbnail + Title (dropdown 3 opsi AI + edit manual) + Description (textarea + tombol ✨ Generate SEO preload dari kolom klip / generate on-demand) + Tags chips + Hashtags + Privacy select (public/unlisted/private, default public) + Thumbnail (Auto/Custom — custom pakai `custom_thumbnail_path` bila ada, else skip; lihat 10.1 kelak)
- [x] Upload → enqueue → polling `youtube-status` 3s → sukses tampilkan link `youtube_url` (target `_blank`)
- [x] Tombol per short + batch (pakai metadata terakhir/default untuk batch; dokumentasikan di UI)
- [x] Guard: short belum COMPLETED → tombol disabled dengan tooltip; sudah uploaded → label ✅ + cegah double

**Acceptance:**
- [x] Alur modal end-to-end dengan backend mock/nyata: pilih title AI → upload → link muncul
- [x] Validasi judul kosong / privacy invalid ditolak backend 422
- [x] `tsc --noEmit` bersih; tak ada regresi tombol GDrive existing
- [x] Test suite hijau (backend: validasi payload + enqueue; frontend: type-check)

---

## Urutan kerja disarankan

1. **8.1** dulu (fondasi: OAuth + job + model; tanpa ini 8.2 tak bisa jalan)
2. **9.1 + 9.2** sejajar (murni LLM + pure function, reusable oleh modal)
3. **8.2** terakhir (konsumsi 8.1 + 9.1)

## Invariant (wajib jaga tiap fitur)

1. OAuth scope wajib `youtube.upload` + `youtube.readonly` (invariant 6)
2. Anti-double upload via `is_youtube_uploaded` (invariant 5)
3. Token/secret selalu encrypted di `app_settings`
4. Batas karakter SEO: title ≤100, desc ≤5000, tags total ≤500 (invariant 8)
5. Thumbnail YouTube = 1280×720 (invariant 7) — relevan saat 10.1 tiba
6. Resumable upload: chunk gagal → retry, bukan gagal job
7. `pytest` + `tsc --noEmit` tiap fitur
