# 🛠️ Troubleshooting & Known Gotchas (`knowledge/troubleshooting.md`)

This document lists known operational gotchas, common error codes, and step-by-step diagnostic solutions for AutoShorts Local.

---

## 1. Port Conflicts: `[Errno 48] Address already in use`

### Symptom:
```text
ERROR: [Errno 48] error while attempting to bind on address ('0.0.0.0', 8000): [errno 48] address already in use
```

### Cause:
A previous background uvicorn worker or node process did not terminate gracefully and is still holding port 8000 or 3000.

### Fix:
1. **Automated Solution**:
   Run `./start_local.sh`. It now automatically detects and kills lingering processes on ports 8000 and 3000 before launching.
2. **Manual Solution**:
   ```bash
   lsof -ti :8000 | xargs kill -9 2>/dev/null || true
   lsof -ti :3000 | xargs kill -9 2>/dev/null || true
   ```

---

## 2. Google Drive `404 File Not Found` or `403 Forbidden`

### When using OAuth 2.0 Web Client:
- **Error**: `Gagal menukar kode otorisasi: redirect_uri_mismatch`
  - **Fix**: In Google Cloud Console -> **APIs & Services** -> **Credentials** -> Select OAuth Client ID -> Add `http://localhost:8000/api/settings/gdrive/oauth/callback` to **Authorized redirect URIs**.
- **Error**: `Access denied` or `Google Drive API has not been used in project...`
  - **Fix**: Enable **Google Drive API** in Google Cloud Console under **APIs & Services** -> **Enabled APIs & Services**.
- **Error**: `404 Folder Not Found`
  - **Fix**: Verify that the Google account authenticated via OAuth has access to the target folder ID, and that the folder is not in the Trash.

### When using Service Account:
- **Error**: `404 Folder Not Found`
  - **Fix**: The target folder MUST be shared explicitly with the Service Account email (e.g. `service-account@project.iam.gserviceaccount.com`) with the **Editor** role. A service account cannot access folders it has not been granted permissions on.

---

## 3. Subtitles Not Burning / libass Errors

### Symptom:
FFmpeg rendering fails or output short does not contain burned-in karaoke text.

### Verification:
Run:
```bash
ffmpeg -version | grep ass
```
FFmpeg must be compiled with `--enable-libass`. On macOS:
```bash
brew install ffmpeg --with-libass # or brew install ffmpeg
```

### Path Quoting Gotcha:
In FFmpeg `-vf`, file paths for `ass=` must be carefully quoted if they contain spaces or special characters:
```bash
-vf "ass='{path_to_subtitles.ass}'"
```

---

## 4. Resetting Forgotten PIN

If the user forgets their PIN or gets locked out:
Run the built-in reset utility:
```bash
python3 reset_pin.py
```
This clears `user_auth` table records in `storage/autoshorts.db`, resetting the application to the initial setup screen on the next browser refresh.

---

## 5. Python 3.14+ C Extension & Whisper Notes

On macOS with Python 3.14+:
- Standard `faster-whisper` and `ctranslate2` might not yet have pre-built binary wheels for Python 3.14.
- [`whisper_service.py`](file:///Users/sultanherrysan/Documents/dev/web-development/clipping/backend/app/services/whisper_service.py) includes an automatic fallback that generates accurate speech segments from audio waveform heuristics or the base Whisper CLI if `faster-whisper` native C bindings fail to load.
