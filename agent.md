# 🤖 Agent Operational Guide & Context (`agent.md`)
**Project**: AutoShorts Local (`clipping` / `auto-shorts-local` / Ember Shorts)  
**Target Environment**: macOS / Linux / Docker, Python 3.10–3.14, Node 18+, FFmpeg with `libass`  
**Current Date/Version**: September 2026 / Version 2.2.0

> [!IMPORTANT]
> This document is the primary briefing for any AI Agent working on this codebase. Read this file and the linked [knowledge/](file:///Users/sultanherrysan/Documents/dev/web-development/clipping/knowledge/) directory before modifying, debugging, or adding new features.

---

## 🧭 Executive Summary

AutoShorts Local is a privacy-first, local-running AI application that transforms long videos (podcasts, webinars, YouTube videos) into optimized vertical shorts (9:16 for TikTok, Reels, YouTube Shorts). The system operates on a **Local-First** architecture:
- Raw video storage, audio extraction, Whisper transcription, video cropping, subtitle burning, and TTS audio happen locally on the user's computer.
- Detached background queue worker handles heavy transcoding and chunked uploads without locking the web server.
- Optional integration with external LLMs (OpenAI, Ollama, LM Studio) and Google Drive (OAuth 2.0 or Service Account).

---

## ⚡ Quick Start for Next Agents

### 1. Common Operational Commands
```bash
# Check running processes on ports 8000 (FastAPI) and 3000 (Vite)
lsof -i :8000; lsof -i :3000

# Run all backend unit & integration tests (MUST ALWAYS PASS)
PYTHONPATH=backend python3 -m pytest backend/tests -v

# Run frontend typecheck and production build
cd frontend && npm run build && cd ..

# Launch both Backend & Frontend via the self-healing startup script
./start_local.sh
```

### 2. Live Service Endpoints
- **Web Frontend**: [http://localhost:3000](http://localhost:3000)
- **Backend API**: [http://localhost:8000](http://localhost:8000)
- **Swagger Documentation**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Health Check**: [http://localhost:8000/api/health](http://localhost:8000/api/health)

---

## 🏗️ Architecture & Component Map

### Backend Directory Layout (`backend/app/`)
- [`main.py`](file:///Users/sultanherrysan/Documents/dev/web-development/clipping/backend/app/main.py): FastAPI initialization, CORS middleware, lifespan background worker management, router registration (`/api`).
- [`database.py`](file:///Users/sultanherrysan/Documents/dev/web-development/clipping/backend/app/database.py): SQLite Async Engine (`storage/autoshorts.db`), WAL mode configuration, safe schema migration with `PRAGMA table_info`.
- [`models/all_models.py`](file:///Users/sultanherrysan/Documents/dev/web-development/clipping/backend/app/models/all_models.py): SQLAlchemy declarative models:
  - `SourceVideo`: Original long video, duration, status, `description`, `auto_generate_shorts`.
  - `ClipCandidate`: Identified viral segments, start/end timestamps, hook scores, virality reasons.
  - `RenderedShort`: 9:16 vertical shorts, render status, `is_drive_uploaded`, download paths.
  - `AppJob`: Queue jobs with retry counter and error logs (`EXTRACT_AUDIO`, `TRANSCRIBE`, `ANALYZE`, `RENDER`, `GDRIVE_UPLOAD`).
  - `AppSetting`: Key-value settings with AES-256-GCM encryption flag (`is_encrypted`).
  - `UserAuth`: Argon2id hashed PIN and active session tracking.
  - `TTSHistory`: Generated text-to-speech audio records.
  - `GDriveExport`: Google Drive export logs and WebView links.
- [`worker.py`](file:///Users/sultanherrysan/Documents/dev/web-development/clipping/backend/app/worker.py): Async queue worker polling pending `AppJob`s every 1.5 seconds.
- [`routers/`](file:///Users/sultanherrysan/Documents/dev/web-development/clipping/backend/app/routers/):
  - [`auth.py`](file:///Users/sultanherrysan/Documents/dev/web-development/clipping/backend/app/routers/auth.py): PIN setup, login, logout, brute-force lockout guard.
  - [`videos.py`](file:///Users/sultanherrysan/Documents/dev/web-development/clipping/backend/app/routers/videos.py): Video upload (supports `auto_generate`), YouTube downloading (`yt-dlp`), streaming, thumbnail serving, auto-generate endpoint.
  - [`clips.py`](file:///Users/sultanherrysan/Documents/dev/web-development/clipping/backend/app/routers/clips.py): Clip candidates CRUD, render trigger with framing & subtitle options, smart-reframe preview, AI narration generation, edge-tts voiceover synthesis, narration audio streaming.
  - [`presets.py`](file:///Users/sultanherrysan/Documents/dev/web-development/clipping/backend/app/routers/presets.py): Text/subtitle styling preset CRUD. Built-in presets are seeded by `init_db()` and cannot be updated or deleted.
  - [`audio.py`](file:///Users/sultanherrysan/Documents/dev/web-development/clipping/backend/app/routers/audio.py): BGM audio library — upload, YouTube extraction (yt-dlp → MP3), streaming, deletion.
  - [`shorts.py`](file:///Users/sultanherrysan/Documents/dev/web-development/clipping/backend/app/routers/shorts.py): Rendered shorts listing, downloads, Google Drive upload trigger & status.
  - [`tts.py`](file:///Users/sultanherrysan/Documents/dev/web-development/clipping/backend/app/routers/tts.py): Local `edge-tts` speech generation, voice listing, audio streaming.
  - [`settings.py`](file:///Users/sultanherrysan/Documents/dev/web-development/clipping/backend/app/routers/settings.py): AI settings, AI connection test, YouTube download quality, durations, Google Drive OAuth 2.0 Web Client URL / exchange / public callback route.
  - [`health.py`](file:///Users/sultanherrysan/Documents/dev/web-development/clipping/backend/app/routers/health.py): Health check (DB, local storage, FFmpeg).
- [`services/`](file:///Users/sultanherrysan/Documents/dev/web-development/clipping/backend/app/services/):
  - [`pipeline.py`](file:///Users/sultanherrysan/Documents/dev/web-development/clipping/backend/app/services/pipeline.py): End-to-end background job handlers.
  - [`llm_service.py`](file:///Users/sultanherrysan/Documents/dev/web-development/clipping/backend/app/services/llm_service.py): Two-tier context highlight extraction, heuristic fallback, connection tester.
  - [`gdrive_service.py`](file:///Users/sultanherrysan/Documents/dev/web-development/clipping/backend/app/services/gdrive_service.py): OAuth 2.0 JSON parser (`{"web": ...}` / `{"installed": ...}`), authorization URL builder, code exchanger, resumable chunked upload.
  - [`whisper_service.py`](file:///Users/sultanherrysan/Documents/dev/web-development/clipping/backend/app/services/whisper_service.py): `faster-whisper` word-level timestamps with fallback.
  - [`media_service.py`](file:///Users/sultanherrysan/Documents/dev/web-development/clipping/backend/app/services/media_service.py): FFmpeg audio extraction, poster thumbnail, 9:16 crop & libass subtitle render.
  - [`tts_service.py`](file:///Users/sultanherrysan/Documents/dev/web-development/clipping/backend/app/services/tts_service.py): `edge-tts` async speech synthesizer.
  - [`yt_service.py`](file:///Users/sultanherrysan/Documents/dev/web-development/clipping/backend/app/services/yt_service.py): `yt-dlp` video info and download helper.
  - [`reframe_service.py`](file:///Users/sultanherrysan/Documents/dev/web-development/clipping/backend/app/services/reframe_service.py): Smart reframe (head-tracking crop). Head detection on sampled frames, deadzone planning, and crop-expression generation. Model at `backend/app/assets/face_detection_yunet_2023mar.onnx`.

### Frontend Directory Layout (`frontend/src/`)
- [`pages/`](file:///Users/sultanherrysan/Documents/dev/web-development/clipping/frontend/src/pages/):
  - [`DashboardPage.tsx`](file:///Users/sultanherrysan/Documents/dev/web-development/clipping/frontend/src/pages/DashboardPage.tsx): System metrics, video list, recent rendered shorts.
  - [`UploadPage.tsx`](file:///Users/sultanherrysan/Documents/dev/web-development/clipping/frontend/src/pages/UploadPage.tsx): Local drag-and-drop upload & YouTube downloader tabs with "Auto-Generate Shorts" toggle.
  - [`ClipStudioPage.tsx`](file:///Users/sultanherrysan/Documents/dev/web-development/clipping/frontend/src/pages/ClipStudioPage.tsx): 2-level view: **Semua Video** (all videos with filter tabs: Semua, Sudah Diklip, Belum Diklip, search, auto-generate) $\rightarrow$ **Editor Klip**. The editor's control panel has two tabs — **Visual** (crop modes *Tengah* / *Manual X* / *Ikuti Wajah* + deadzone slider, text preset picker, font & size, base/active karaoke colors, outline & shadow, uppercase, subtitle position) and **Audio** (audio mode, BGM picker + volume, AI narration + edge-tts voiceover).
  - [`ShortsPage.tsx`](file:///Users/sultanherrysan/Documents/dev/web-development/clipping/frontend/src/pages/ShortsPage.tsx): Rendered shorts library, 9:16 video player modal, Google Drive export button (anti-double upload protected).
  - [`AudioLibraryPage.tsx`](file:///Users/sultanherrysan/Documents/dev/web-development/clipping/frontend/src/pages/AudioLibraryPage.tsx): BGM library management — upload audio files, pull audio from YouTube (yt-dlp → MP3), preview, delete, and hand a track straight to Clip Studio as BGM.
  - [`PresetPage.tsx`](file:///Users/sultanherrysan/Documents/dev/web-development/clipping/frontend/src/pages/PresetPage.tsx): Preset manager with sub-navigation. The **Teks** sub-tab does full CRUD on text/subtitle styling presets with a live 9:16 subtitle preview; built-in presets are read-only.
  - [`TTSPage.tsx`](file:///Users/sultanherrysan/Documents/dev/web-development/clipping/frontend/src/pages/TTSPage.tsx): Text-to-Speech studio with Indonesian/English voices.
  - [`SettingsPage.tsx`](file:///Users/sultanherrysan/Documents/dev/web-development/clipping/frontend/src/pages/SettingsPage.tsx): 4 tabs: "Koneksi AI (LLM)", "Durasi Klip & YouTube", "Google Drive Export" (OAuth2 Web Client + Service Account), "Status Mesin Lokal".
- [`services/api.ts`](file:///Users/sultanherrysan/Documents/dev/web-development/clipping/frontend/src/services/api.ts): Centralized Axios API client with token interceptor and media URL builder.
- [`types/index.ts`](file:///Users/sultanherrysan/Documents/dev/web-development/clipping/frontend/src/types/index.ts): Strict TypeScript interfaces for all payloads and domain models.

---

## 🛡️ Critical Rules & Invariants for Agents

1. **Test Suite Integrity**:
   Always run `PYTHONPATH=backend python3 -m pytest backend/tests -v` before declaring any task done. All tests must pass.
2. **Port Conflict Management**:
   The backend runs on port `8000` and the frontend on port `3000`. Never leave orphaned background processes hanging. [`start_local.sh`](file:///Users/sultanherrysan/Documents/dev/web-development/clipping/start_local.sh) is configured to automatically kill old processes on ports 8000 and 3000 before binding.
3. **Database Migrations in SQLite**:
   Do NOT run `alembic` commands in local SQLite mode. Migration is handled safely in [`database.py:init_db()`](file:///Users/sultanherrysan/Documents/dev/web-development/clipping/backend/app/database.py) using `PRAGMA table_info` and `ALTER TABLE ADD COLUMN`. When adding columns to models, always add the check to `init_db()`.
4. **ASS Subtitle BGR Color Rule**:
   The Advanced SubStation Alpha (`.ass`) specification expects colors in `&HAABBGGRR&` (Alpha, Blue, Green, Red) format. Web colors are `#RRGGBB`. Always use [`hex_to_ass_color`](file:///Users/sultanherrysan/Documents/dev/web-development/clipping/backend/app/core/security.py) when generating subtitles.
5. **AI Gating Rule**:
   AI highlights extraction requires `llm_connected == True`. If the user updates the LLM settings, `llm_connected` is reset to `False` until the user successfully runs "Uji Koneksi AI" via `POST /api/settings/ai/test`.
6. **Two-Tier Context Rule (Konteks Besar + Konteks Kecil)**:
   When modifying `llm_service.py`, preserve both macro context (`video_title`, `video_description`, `full_text` summary) to filter out sponsors and casual intro chatter, and micro context (timestamped segments) to cut viral hooks in the first 3 seconds.
7. **Google Drive Anti-Double Upload**:
   When exporting shorts to Google Drive, check `short.is_drive_uploaded`. Never re-upload an already uploaded short unless explicitly requested.
8. **Ember Studio Visual Consistency**:
   Maintain visual styling: Terracotta (`#C2410C`), Amber (`#F59E0B`), warm background (`#FAFAF9`), border (`#D6D3D1`), and fonts (`Playfair Display`, `Source Sans 3`, `Poppins`).
9. **Smart Reframe Containment**:
   All head-tracking crop logic lives in [`reframe_service.py`](file:///Users/sultanherrysan/Documents/dev/web-development/clipping/backend/app/services/reframe_service.py). Keep `smooth_head_track`, `plan_crop_track` and `crop_keyframes_to_expression` pure (no I/O) so they stay unit-testable. `crop_mode="smart"` must always degrade to a static crop instead of failing a render job — `cv2` and the YuNet model are both optional at runtime.
10. **Preset Precedence in `handle_render`**:
    An explicit render-request value always beats the selected preset, and `0`/`False` are meaningful values. Resolve every style field through the `pick()` helper in [`pipeline.py`](file:///Users/sultanherrysan/Documents/dev/web-development/clipping/backend/app/services/pipeline.py) — never through an `or` chain, or `outline_width=0` will silently fall back to the preset's value. Auto-generate paths must keep omitting the per-field style keys (see `default_render_settings()`) so presets stay in full control.
11. **Subtitle Preview Must Match the Render**:
    Every subtitle preview (Clip Studio simulator, Preset page) goes through [`SubtitleFrame.tsx`](file:///Users/sultanherrysan/Documents/dev/web-development/clipping/frontend/src/components/SubtitleFrame.tsx), which scales from the real 1080x1920 canvas using `width / 1080`. Its constants mirror `ass_service.py`: `SCRIPT_WIDTH/HEIGHT` = 1080/1920, `SIDE_MARGIN` = 60, and `DEFAULT_MARGIN_V` = top 1540 / middle 920 / bottom 340. If you change the ASS script resolution, margins, or alignment in the backend, update that component in the same commit — otherwise the preview silently stops representing the rendered output.

---

## 📚 Specialized Knowledge Directory

For deep-dive technical explanations, read the domain guides in the `knowledge/` directory:

| Knowledge Document | Topics Covered |
| :--- | :--- |
| [architecture.md](file:///Users/sultanherrysan/Documents/dev/web-development/clipping/knowledge/architecture.md) | Full system pipeline, data flow diagram, background worker lifecycle, database schema |
| [ai-curation-and-context.md](file:///Users/sultanherrysan/Documents/dev/web-development/clipping/knowledge/ai-curation-and-context.md) | Konteks Besar vs Konteks Kecil, prompt engineering, hook scoring, heuristic fallback, AI gatekeeping |
| [media-engine.md](file:///Users/sultanherrysan/Documents/dev/web-development/clipping/knowledge/media-engine.md) | FFmpeg 9:16 crop filters, libass subtitle burn-in, BGR color conversion, yt-dlp downloading |
| [gdrive-integration.md](file:///Users/sultanherrysan/Documents/dev/web-development/clipping/knowledge/gdrive-integration.md) | OAuth 2.0 Web Client (`{"web": ...}`) vs Service Account, redirect URI setup, chunked resumable upload |
| [security-and-auth.md](file:///Users/sultanherrysan/Documents/dev/web-development/clipping/knowledge/security-and-auth.md) | Argon2id PIN auth, JWT session verification, AES-256-GCM encryption for settings |
| [troubleshooting.md](file:///Users/sultanherrysan/Documents/dev/web-development/clipping/knowledge/troubleshooting.md) | Resolving port conflicts, Python 3.14 quirks, YouTube throttles, Drive 404/403 errors |
