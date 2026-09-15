# Product Requirements Document (PRD)
## Local AI Video Clipper & Shorts Generator (`auto-shorts-local`)

| Field | Value |
| :--- | :--- |
| **Document Version** | 2.1.0 |
| **Status** | Ready for Implementation |
| **Target Environment** | Local Dockerized (Single Node / Workstation) |
| **Audience** | AI Coding Agents & Full-Stack Developers |
| **Primary Language** | Indonesian (Technical Specification in English / ID) |

---

### Riwayat Revisi
| Versi | Perubahan |
| :--- | :--- |
| **2.0.0** | PRD awal: arsitektur single-node, pipeline Whisper + LLM + FFmpeg + ASS. |
| **2.1.0** | Penambahan tabel `app_jobs` (persistent queue), komplemen endpoint API yang hilang (`list`/`delete`/`health`), standar error envelope, state machine visual, spesifikasi variabel lingkungan (`.env`) & `docker-compose.yml`, template prompt LLM lengkap, template subtitle ASS (termasuk mitigasi jebakan konversi warna RGB→BGR), retry/timeout policy, kriteria penerimaan (*Definition of Done*), dan panduan implementasi bertahap untuk AI Coding Agent. |

---

## 1. Overview & Scope

### 1.1 Problem Statement
Membuat video pendek vertikal (*TikTok*, *Instagram Reels*, *YouTube Shorts*) dari video berdurasi panjang (podcast, seminar, webinar, vlog) secara manual memakan waktu yang sangat signifikan. Editor harus menonton ulang rekaman berjam-jam, mencari momen menarik (*hook*), memotong klip, melakukan *re-framing* (crop ke 9:16), mengetik transkrip manual, serta menyinkronkan animated subtitle. Proses ini bersifat mekanis, repetitif, dan sangat rentan terhadap inefisiensi alur kerja.

### 1.2 Objective
Membangun sistem *self-hosted* dan *local-first* yang berjalan di lingkungan Docker mesin pengguna untuk:
1. Menerima *upload* video panjang berformat `.mp4`, `.mkv`, `.mov`, `.webm`.
2. Mengekstraksi audio dan melakukan transkripsi kata-per-kata (*word-level timestamps*) menggunakan engine **faster-whisper** secara lokal tanpa ketergantungan API cloud berbayar.
3. Mendeteksi dan merekomendasikan momen klip paling berpotensi viral via **Custom LLM API** (*OpenAI-compatible endpoint*).
4. Merender klip vertikal rasio 9:16 (1080x1920) dengan *animated karaoke burn-in caption* memanfaatkan **FFmpeg** dan format **ASS (Advanced SubStation Alpha)**.
5. Mengelola state pekerjaan, metadata klip, dan riwayat di **MySQL 8.0**, dengan seluruh aset media tersimpan di bind-mount *local storage*.
6. Menyediakan opsi sinkronisasi otomatis (*resumable upload*) hasil klip ke **Google Drive** pengguna.

### 1.3 Scope

#### In Scope (v2.1.0)
- Single-user access model via Local Area Network (desktop/tablet).
- Sistem keamanan *PIN Gatekeeper* lokal + autentikasi JWT stateless.
- Pipeline pemrosesan asinkron berbasis *worker poller* dengan persistensi antrean di tabel `app_jobs`.
- Render video resolusi tinggi 1080x1920 H.264/AAC dengan *smart center crop* atau *manual crop offset*.
- Subtitle *karaoke-style* dengan animasi highlight kata aktif dan validasi warna BGR.
- Web UI responsif (Upload, Live Status Polling, Video Preview Player, Clip Candidate Reviewer, Manual Crop/Caption Customizer).
- Sinkronisasi ekspor ke Google Drive melalui Google Service Account atau OAuth2 Refresh Token.

#### Out of Scope (v2.x - Dicadangkan untuk v3+)
- Manajemen multi-tenant atau sistem role pengguna (RBAC kompleks).
- Editor timeline non-linear multi-track di browser.
- Integrasi direct publish API ke TikTok, YouTube Shorts, atau Instagram Reels.
- Fitur auto-face tracking dengan AI vision dinamis (B-roll overlay otomatis dan dynamic zoom framing masuk ke roadmap v3).
- Orkestrasi kluster multi-node horizontal (Kubernetes / Celery multi-worker).

### 1.4 User Persona
| Persona | Profil & Karakteristik | Kebutuhan Utama |
| :--- | :--- | :--- |
| **Content Creator Solo** | Memproduksi 1–5 video panjang per minggu, mengelola kanal YouTube & media sosial sendiri tanpa tim editor. | Pipeline "1-klik": upload video mentah → sistem menganalisis → langsung dapat 3–5 klip 9:16 siap posting. |
| **Podcaster / Webinar Host** | Memiliki episode rekaman 60–120 menit dengan banyak pembahasan menarik yang tersebar. | Transkripsi akurat berbahasa Indonesia/Inggris, deteksi segmen berbobot tinggi otomatis, export ke Google Drive untuk dibagikan ke tim media. |

---

## 2. Arsitektur & Infrastruktur

### 2.1 Diagram Arsitektur

```mermaid
flowchart TB
    subgraph Docker ["Docker Compose (Single Node / Host Machine)"]
        FE["web-frontend\nReact + Vite + Tailwind\nPort :3000"]
        BE["api-backend\nFastAPI + Async Workers\nPort :8000"]
        DB[("db-mysql\nMySQL 8.0 (InnoDB)\nPort :3306")]
        
        FE -- "REST API + Polling" --> BE
        BE -- "SQLAlchemy 2.0 (Async)" --> DB
    end

    subgraph Storage ["Bind Mount: ./storage (Host Filesystem)"]
        UP["uploads/ (Video mentah)"]
        AU["audio/ (PCM 16kHz WAV)"]
        TR["transcripts/ (Whisper JSON)"]
        SU["subtitles/ (ASS files)"]
        TH["thumbnails/ (Poster JPG)"]
        EX["exports/ (MP4 9:16 rendered)"]
        CR["credentials/ (Tokens, gdrive_token.json)"]
    end

    subgraph Tools ["Heavy Processing Tools (Di dalam BE Container)"]
        FF["FFmpeg 6.x & FFprobe\n(Extract / Filter Crop / Subtitles libass)"]
        WH["faster-whisper (CTranslate2)\n(VAD Filter + Word Timestamps)"]
    end

    subgraph External ["External Services"]
        LLM["Custom LLM API\n(OpenAI-Compatible: Ollama / vLLM / Cloud)"]
        GD["Google Drive API v3\n(Service Account / OAuth2 Resumable)"]
    end

    BE --> FF
    BE --> WH
    FF --> Storage
    WH --> Storage
    BE --> Storage
    BE --> LLM
    BE --> GD
```

### 2.2 Tech Stack

| Layer | Teknologi | Versi Minimal | Peran & Tanggung Jawab |
| :--- | :--- | :--- | :--- |
| **Frontend** | React, Vite, Tailwind CSS, TanStack Query v5, Axios | React 18, Vite 5 | Single Page Application (SPA), polling status, video player preview, kontrol crop offset, pengaturan caption & export. |
| **Backend API** | Python, FastAPI, Pydantic v2 | Python 3.11+, FastAPI 0.109+ | Web server REST API, pipeline orchestrator, dependency injection, validasi payload. |
| **Data Layer** | SQLAlchemy 2.0 (Async), Alembic, asyncmy / aiomysql | SQLAlchemy 2.0.25+ | ORM asinkron, migrasi skema database, transaksi atomik. |
| **Database** | MySQL 8.0 (fallback MariaDB 10.11+) | MySQL 8.0.35 | Penyimpanan relational state, antrean pekerjaan (`app_jobs`), metadata transkrip & klip. |
| **ASR Engine** | faster-whisper (CTranslate2) | faster-whisper 1.0+ | Transkripsi audio lokal kecepatan tinggi, VAD (Voice Activity Detection), ekstraksi kata ber-timestamp. |
| **Media Engine**| FFmpeg, FFprobe (compiled with `libass`, `libx264`, `libmp3lame`, `fdk-aac`) | FFmpeg 6.0+ | Probe metadata, ekstraksi audio mono 16kHz, generate poster thumbnail, cropping 9:16, burning subtitle ASS. |
| **AI LLM** | HTTP Client (OpenAI SDK / httpx) | OpenAI API spec v1 | Analisis transkrip, penentuan segmentasi klip, scoring viralitas (*hook score*), dan ekstraksi judul. |
| **Cloud Client**| `google-api-python-client`, `google-auth` | v2.0+ | Resumable chunk upload ke folder Google Drive pengguna. |

### 2.3 Kebutuhan Hardware

| Profil | CPU | RAM | GPU (Opsional) | Estimasi Waktu (Video 60 Menit) |
| :--- | :--- | :--- | :--- | :--- |
| **Minimum** | 4 Cores (x86_64 / Apple Silicon) | 8 GB | Tidak ada (CPU mode, Whisper `tiny`/`base`, int8) | Transkripsi: ~15–25 mnt; Render per klip: ~1.5–2x durasi klip. |
| **Rekomendasi** | 8 Cores (Modern CPU) | 16 GB | NVIDIA GPU ≥6 GB VRAM / Apple Metal (Whisper `small`/`medium`, float16) | Transkripsi: ~2–5 mnt; Render per klip: ≤0.8x durasi klip (NVENC/VAAPI). |

---

## 3. Desain Data & Relasional (MySQL 8.0)

### 3.1 Entity Relationship Diagram (ERD)

```mermaid
erDiagram
    source_videos ||--o| transcripts : "1:0..1 has transcript"
    source_videos ||--o{ clip_candidates : "1:N generates"
    clip_candidates ||--o{ rendered_shorts : "1:N renders into"
    rendered_shorts ||--o{ google_drive_exports : "1:N logs export"
    app_jobs }o--|| source_videos : "polymorphic ref_id"
    app_jobs }o--|| clip_candidates : "polymorphic ref_id"
    app_jobs }o--|| rendered_shorts : "polymorphic ref_id"
    
    app_settings {
        varchar setting_key PK
        text setting_value
        boolean is_encrypted
        timestamp updated_at
    }

    auth_pin {
        int id PK
        varchar pin_hash
        varchar salt
        boolean is_active
        timestamp created_at
    }

    source_videos {
        varchar id PK "UUID v4"
        varchar filename
        varchar original_name
        varchar local_file_path
        bigint file_size_bytes
        float duration_seconds
        varchar language
        enum status
        text error_message
        timestamp created_at
    }

    transcripts {
        varchar id PK "UUID v4"
        varchar video_id FK "UNIQUE"
        longtext full_text
        varchar transcript_json_path
        timestamp created_at
    }

    clip_candidates {
        varchar id PK "UUID v4"
        varchar video_id FK
        varchar title
        float start_time_seconds
        float end_time_seconds
        float duration_seconds
        int hook_score
        text virality_reason
        boolean is_selected
        timestamp created_at
    }

    rendered_shorts {
        varchar id PK "UUID v4"
        varchar clip_id FK
        varchar output_filename
        varchar local_path
        bigint file_size_bytes
        json render_settings
        enum render_status
        int render_progress
        text error_message
        timestamp created_at
    }

    google_drive_exports {
        varchar id PK "UUID v4"
        varchar short_id FK
        varchar gdrive_file_id
        text gdrive_web_view_link
        enum upload_status
        int upload_progress
        text error_message
        timestamp uploaded_at
        timestamp created_at
    }

    app_jobs {
        varchar id PK "UUID v4"
        enum job_type
        varchar ref_id
        enum status
        int progress
        int attempts
        int max_attempts
        json payload
        text error_message
        timestamp started_at
        timestamp finished_at
        timestamp created_at
    }
```

### 3.2 DDL Lengkap (MySQL 8.0)

```sql
CREATE DATABASE IF NOT EXISTS autoshorts
CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE autoshorts;

-- 1. Konfigurasi Sistem (termasuk kredensial sensitif terenkripsi)
CREATE TABLE app_settings (
    setting_key VARCHAR(50) PRIMARY KEY,
    setting_value TEXT NOT NULL,
    is_encrypted BOOLEAN DEFAULT FALSE,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- 2. PIN Gatekeeper
CREATE TABLE auth_pin (
    id INT AUTO_INCREMENT PRIMARY KEY,
    pin_hash VARCHAR(255) NOT NULL,
    salt VARCHAR(64) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- 3. Video Mentah Sumber
CREATE TABLE source_videos (
    id VARCHAR(36) PRIMARY KEY, -- UUID v4
    filename VARCHAR(255) NOT NULL, -- Format: {id}.mp4
    original_name VARCHAR(255) NOT NULL,
    local_file_path VARCHAR(500) NOT NULL, -- Path relatif: uploads/{id}.mp4
    file_size_bytes BIGINT NOT NULL,
    duration_seconds FLOAT NOT NULL DEFAULT 0.0,
    language VARCHAR(10) NULL, -- Deteksi Whisper, misal: 'id', 'en'
    status ENUM('UPLOADED', 'EXTRACTING_AUDIO', 'TRANSCRIBING', 'ANALYZING', 'READY', 'FAILED') DEFAULT 'UPLOADED',
    error_message TEXT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_video_status (status, created_at)
) ENGINE=InnoDB;

-- 4. Transkrip Lengkap Video
CREATE TABLE transcripts (
    id VARCHAR(36) PRIMARY KEY, -- UUID v4
    video_id VARCHAR(36) NOT NULL,
    full_text LONGTEXT NOT NULL,
    transcript_json_path VARCHAR(500) NOT NULL, -- Path relatif: transcripts/{video_id}.json
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_transcript_video (video_id),
    FOREIGN KEY (video_id) REFERENCES source_videos (id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- 5. Kandidat Klip (Hasil Analisis LLM)
CREATE TABLE clip_candidates (
    id VARCHAR(36) PRIMARY KEY, -- UUID v4
    video_id VARCHAR(36) NOT NULL,
    title VARCHAR(255) NOT NULL,
    start_time_seconds FLOAT NOT NULL,
    end_time_seconds FLOAT NOT NULL,
    duration_seconds FLOAT NOT NULL,
    hook_score INT DEFAULT 0, -- Rentang 0..100
    virality_reason TEXT NULL,
    is_selected BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_clip_video (video_id, hook_score DESC),
    FOREIGN KEY (video_id) REFERENCES source_videos (id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- 6. Hasil Render Klip 9:16
CREATE TABLE rendered_shorts (
    id VARCHAR(36) PRIMARY KEY, -- UUID v4
    clip_id VARCHAR(36) NOT NULL,
    output_filename VARCHAR(255) NOT NULL, -- Format: {short_id}_9x16.mp4
    local_path VARCHAR(500) NOT NULL, -- Path relatif: exports/{short_id}_9x16.mp4
    file_size_bytes BIGINT DEFAULT 0,
    render_settings JSON NULL, -- Parameter crop, offset, warna caption, font
    render_status ENUM('PENDING', 'RENDERING', 'COMPLETED', 'FAILED') DEFAULT 'PENDING',
    render_progress INT DEFAULT 0, -- Rentang 0..100
    error_message TEXT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_short_status (render_status),
    FOREIGN KEY (clip_id) REFERENCES clip_candidates (id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- 7. Log Ekspor Google Drive
CREATE TABLE google_drive_exports (
    id VARCHAR(36) PRIMARY KEY, -- UUID v4
    short_id VARCHAR(36) NOT NULL,
    gdrive_file_id VARCHAR(150) NULL,
    gdrive_web_view_link TEXT NULL,
    upload_status ENUM('QUEUED', 'UPLOADING', 'SUCCESS', 'FAILED') DEFAULT 'QUEUED',
    upload_progress INT DEFAULT 0, -- Rentang 0..100
    error_message TEXT NULL,
    uploaded_at TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_export_status (upload_status),
    FOREIGN KEY (short_id) REFERENCES rendered_shorts (id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- 8. Persistent Job Queue (Asynchronous Pipeline Engine)
CREATE TABLE app_jobs (
    id VARCHAR(36) PRIMARY KEY, -- UUID v4
    job_type ENUM('AUDIO_EXTRACT', 'TRANSCRIBE', 'LLM_ANALYZE', 'RENDER', 'GDRIVE_UPLOAD') NOT NULL,
    ref_id VARCHAR(36) NOT NULL, -- Polymorphic: video_id / clip_id / short_id
    status ENUM('QUEUED', 'RUNNING', 'COMPLETED', 'FAILED', 'CANCELLED') DEFAULT 'QUEUED',
    progress INT DEFAULT 0, -- Rentang 0..100
    attempts INT DEFAULT 0,
    max_attempts INT DEFAULT 3,
    payload JSON NULL, -- Parameter spesifik job
    error_message TEXT NULL,
    started_at TIMESTAMP NULL,
    finished_at TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_job_status (status, created_at),
    INDEX idx_job_ref (ref_id)
) ENGINE=InnoDB;
```

### 3.3 Aturan Integritas Data Penting
1. **Path Isolation**: Database dilarang keras menyimpan *absolute path* sistem operasi host. Seluruh path berkas disimpan relatif terhadap root penyimpanan (`STORAGE_ROOT`), contoh: `uploads/{id}.mp4` atau `exports/{short_id}_9x16.mp4`. Konversi path absolut ditangani di runtime oleh service layer.
2. **Kriptografi Kredensial**: Nilai konfigurasi pada `app_settings` dengan `is_encrypted = TRUE` wajib dienkripsi menggunakan algoritma **AES-256-GCM**. Kunci 32-byte dibaca dari environment variable `SETTINGS_ENCRYPTION_KEY`. Format payload tersimpan adalah gabungan Base64:
   $$\text{base64}(\text{nonce}) : \text{base64}(\text{ciphertext}) : \text{base64}(\text{tag})$$
3. **Primary Key UUID**: Semua ID unik dibangkitkan pada level aplikasi (`uuid.uuid4().hex` atau string standard 36-karakter) sebelum query SQL dieksekusi.
4. **Cascade Cleanliness**: Semua relasi Foreign Key dilengkapi `ON DELETE CASCADE`. Menghapus baris pada `source_videos` secara otomatis menghapus record transkrip, kandidat klip, rendered shorts, dan riwayat ekspor terkait di database. Pembersihan berkas fisik pada filesystem ditangani oleh service hook `delete_video_artifacts()`.

### 3.4 State Machine

#### Pipeline Pemrosesan Video Sumber
```mermaid
stateDiagram-v2
    [*] --> UPLOADED : Video berhasil di-upload
    UPLOADED --> EXTRACTING_AUDIO : Worker mengambil job AUDIO_EXTRACT
    EXTRACTING_AUDIO --> TRANSCRIBING : Berkas .wav 16kHz siap
    EXTRACTING_AUDIO --> FAILED : ffprobe / stream audio rusak
    TRANSCRIBING --> ANALYZING : Berkas transcript.json tersimpan
    TRANSCRIBING --> FAILED : Whisper error / out-of-memory
    ANALYZING --> READY : clip_candidates berhasil disimpan
    ANALYZING --> FAILED : LLM timeout / response invalid
    FAILED --> EXTRACTING_AUDIO : Trigger retry manual via UI
```

#### Pipeline Render Video Vertikal
```mermaid
stateDiagram-v2
    [*] --> PENDING : User request POST /clips/{id}/render
    PENDING --> RENDERING : Worker claim job RENDER
    RENDERING --> COMPLETED : FFmpeg exit code 0 & progress 100%
    RENDERING --> FAILED : FFmpeg error / timeout / disk full
```

#### Pipeline Upload Google Drive
```mermaid
stateDiagram-v2
    [*] --> QUEUED : User request POST /shorts/{id}/upload-gdrive
    QUEUED --> UPLOADING : Worker claim job GDRIVE_UPLOAD
    UPLOADING --> SUCCESS : Chunk upload selesai & file_id tersimpan
    UPLOADING --> FAILED : Max retry (5x) terlampaui / auth gagal
```

---

## 4. Spesifikasi Storage Lokal

### 4.1 Struktur Direktori

Seluruh berkas media disimpan dalam direktori fisik `./storage` pada host yang di-*bind-mount* ke dalam container backend pada direktori `/storage` (didefinisikan melalui variabel lingkungan `STORAGE_ROOT`).

```text
./storage/
├── uploads/       # Video asli mentah ({video_id}.{ext})
├── audio/         # Audio hasil ekstraksi PCM 16kHz mono ({video_id}.wav)
├── transcripts/   # Berkas transkripsi terstruktur JSON ({video_id}.json)
├── subtitles/     # Berkas subtitle ASS per klip ({clip_id}.ass)
├── thumbnails/    # Poster frame JPEG ({video_id}.jpg)
├── exports/       # Hasil video vertikal 9:16 ({short_id}_9x16.mp4)
└── credentials/   # Berkas OAuth token / gdrive_token.json (wajib .gitignore!)
```

### 4.2 Format Kontrak Transcript JSON (`transcripts/{video_id}.json`)
File transkrip lokal menjadi kontrak internal antara Whisper Service, LLM Service, dan ASS Subtitle Generator:

```json
{
  "video_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "language": "id",
  "duration": 3600.5,
  "segments": [
    {
      "id": 0,
      "seek": 0,
      "start": 12.40,
      "end": 15.90,
      "text": " Halo semuanya selamat datang kembali di podcast kami.",
      "words": [
        { "word": "Halo", "start": 12.40, "end": 12.82 },
        { "word": "semuanya", "start": 12.85, "end": 13.40 },
        { "word": "selamat", "start": 13.45, "end": 13.90 },
        { "word": "datang", "start": 13.92, "end": 14.30 },
        { "word": "kembali", "start": 14.35, "end": 14.80 },
        { "word": "di", "start": 14.85, "end": 15.00 },
        { "word": "podcast", "start": 15.05, "end": 15.50 },
        { "word": "kami.", "start": 15.55, "end": 15.90 }
      ]
    }
  ]
}
```

### 4.3 Kebijakan Retensi & Pembersihan Berkas
- **Manual Deletion**:
  - `DELETE /api/videos/{id}`: Menghapus baris pada database (otomatis men-cascade seluruh anak entitas) dan menghapus berkas fisik pada `uploads/`, `audio/`, `transcripts/`, dan `thumbnails/`.
  - `DELETE /api/shorts/{id}`: Menghapus record pada database serta berkas `.mp4` pada direktori `exports/`.
- **Automated Cleanup (Opsional)**:
  - Variabel `AUTO_CLEANUP_DAYS` (default `0` = nonaktif): Jika diaktifkan (>0), background job harian akan menghapus berkas sementara berukuran besar di `audio/` dan `transcripts/` untuk video yang statusnya telah mencapai `READY` lebih lama dari $N$ hari, sementara berkas sumber di `uploads/` dan hasil render di `exports/` tetap dipertahankan.

---

## 5. Spesifikasi Fungsional Per Modul

### 5.1 Modul 1: PIN Authentication (Gatekeeper)

#### Diagram Alir Autentikasi
```mermaid
sequenceDiagram
    autonumber
    actor User as Pengguna (Browser)
    participant FE as Web Frontend
    participant BE as FastAPI Backend
    participant DB as MySQL Database

    FE->>BE: GET /api/auth/status
    BE->>DB: SELECT COUNT(*) FROM auth_pin WHERE is_active = TRUE
    alt Belum Dikonfigurasi (First Run)
        BE-->>FE: {"is_configured": false, "has_session": false}
        User->>FE: Masukkan 4-8 Digit PIN Pertama Kali
        FE->>BE: POST /api/auth/setup {"pin": "123456"}
        BE->>DB: Simpan Hash Argon2id + Salt Baru
        BE-->>FE: 201 Created {"token": "<JWT_TOKEN>"}
    else Sudah Dikonfigurasi
        BE-->>FE: {"is_configured": true, "has_session": false}
        User->>FE: Masukkan PIN
        FE->>BE: POST /api/auth/login {"pin": "123456"}
        BE->>DB: Ambil hash & verifikasi PIN via Argon2id
        alt Verifikasi Sukses
            BE-->>FE: 200 OK {"token": "<JWT_TOKEN>"}
        else Verifikasi Gagal
            BE-->>FE: 401 Unauthorized (atau 429 jika cooldown aktif)
        end
    end

    Note over FE,BE: Akses Request Terproteksi
    FE->>BE: GET /api/videos (Header: Authorization: Bearer <token>)
    BE->>BE: Validasi Signature & Expiration JWT
    BE-->>FE: 200 OK Data Response
```

#### Aturan Teknis PIN
- **Format PIN**: 4 sampai 8 digit numerik murni (`^\d{4,8}$`).
- **Hashing Algorithm**: **Argon2id** (`time_cost=3`, `memory_cost=65536` [64 MB], `parallelism=2`) melalui library `argon2-cffi`. Fallback: bcrypt dengan cost factor 12.
- **Session Token**: JWT (JSON Web Token) dengan algoritma HS256 menggunakan secret key dari `JWT_SECRET` (minimal 32 karakter acak). Masa aktif token adalah 7 hari (`exp = now + 7 days`).
- **Brute-force Guard**: Maksimal 5 kali percobaan salah berturut-turut akan memicu *cooldown* selama 5 menit untuk IP yang bersangkutan (disimpan di in-memory lock dict backend).
- **Idempotency Setup**: Panggilan `POST /api/auth/setup` akan ditolak dengan error `409 Conflict` jika PIN aktif sudah pernah dibuat sebelumnya.

---

### 5.2 Modul 2: Upload, Ekstraksi Audio & Transkripsi Lokal

#### Alur Eksekusi
1. Client mengunggah berkas via `POST /api/videos/upload`.
2. Backend memvalidasi berkas, menulis stream ke `storage/uploads/{video_id}.mp4`, menyisipkan record `source_videos` berstatus `UPLOADED`, dan mengekstrak thumbnail poster frame.
3. Client atau sistem memicu `POST /api/videos/{video_id}/process` untuk memulai pipeline worker:
   $$\text{Job AUDIO\_EXTRACT} \longrightarrow \text{Job TRANSCRIBE} \longrightarrow \text{Job LLM\_ANALYZE}$$

#### Perintah Ekstraksi Audio & Metadata (FFmpeg & FFprobe)
```bash
# 1. Probe durasi, resolusi, dan audio stream
ffprobe -v quiet -print_format json -show_format -show_streams "storage/uploads/{video_id}.mp4"

# 2. Ekstraksi audio ke format PCM 16kHz mono (optimal untuk faster-whisper)
ffmpeg -y -i "storage/uploads/{video_id}.mp4" -vn -acodec pcm_s16le -ar 16000 -ac 1 "storage/audio/{video_id}.wav"

# 3. Ekstraksi 1 frame thumbnail pada detik ke-1
ffmpeg -y -ss 00:00:01 -i "storage/uploads/{video_id}.mp4" -frames:v 1 -vf "scale=480:-2" "storage/thumbnails/{video_id}.jpg"
```

#### Eksekusi Transkripsi (Python `faster-whisper`)
```python
from faster_whisper import WhisperModel

model = WhisperModel(
    model_size_or_path=settings.WHISPER_MODEL,     # cth: 'small', 'base'
    device=settings.WHISPER_DEVICE,                 # 'cpu' atau 'cuda'
    compute_type=settings.WHISPER_COMPUTE_TYPE     # 'int8' atau 'float16'
)

segments, info = model.transcribe(
    audio_path=f"{STORAGE_ROOT}/audio/{video_id}.wav",
    word_timestamps=True,   # Wajib bernilai True untuk animasi kata ASS
    vad_filter=True,        # Membuang keheningan agar transkripsi presisi dan cepat
    language=None           # Auto-detect bahasa (disimpan ke source_videos.language)
)
```

#### Matriks Penanganan Masalah Audio & Transkripsi
| Kondisi | Penanganan Sistem |
| :--- | :--- |
| Ekstensi berkas tidak didukung | Ditolak pada endpoint upload dengan status HTTP `422 Unprocessable Entity` (hanya menerima `.mp4`, `.mkv`, `.mov`, `.avi`, `.webm`). |
| Ukuran file > `MAX_UPLOAD_SIZE_MB` | Ditolak oleh server dengan HTTP `413 Payload Too Large`. |
| Video tidak memiliki stream audio | `AUDIO_EXTRACT` gagal, record ditandai `FAILED` dengan pesan *"No audio stream found in source file"*. |
| FFmpeg exit code $\ne 0$ | Job ditandai `FAILED`, 500 karakter terakhir dari `stderr` disimpan ke `error_message`. |
| Whisper Out-Of-Memory (OOM) | Job ditandai `FAILED`, sistem menambahkan rekomendasi: *"Turunkan WHISPER_MODEL ke model lebih kecil (base/small) atau gunakan compute_type int8"*. |
| Timeout eksekusi | Timeout default: `AUDIO_EXTRACT` 30 menit; `TRANSCRIBE` 6 jam (dapat dikonfigurasi). |

---

### 5.3 Modul 3: AI Highlight Extraction (LLM)

#### Input Data
Transkrip diringkas per segmen berpenanda waktu (contoh: `[00:12.4 - 00:15.9] Halo semuanya selamat datang...`), dibatasi maksimal $\pm 24.000$ karakter. Jika teks melebihi batas, bagian tengah transkrip diringkas dengan penanda `...[omitted]...` untuk mempertahankan konteks awal dan penutup video.

#### System Prompt Template
Disimpan pada tabel `app_settings` dengan key `llm_prompt` dan dapat diubah secara dinamis melalui antarmuka Settings UI:

```text
Kamu adalah editor video profesional yang sangat ahli mencari dan mengkurasi momen viral untuk format TikTok, Instagram Reels, dan YouTube Shorts.

TUGAS:
Analisis transkrip rekaman video berikut, lalu pilih 3 sampai 5 segmen klip terbaik yang memiliki potensi retensi dan interaksi penonton tertinggi.

ATURAN KURASI:
1. Setiap klip harus berupa pemikiran yang utuh (tidak terpotong di tengah kalimat).
2. Durasi setiap klip wajib berada di antara {min_dur} sampai {max_dur} detik.
3. Awali setiap klip dengan "hook" kuat pada kalimat pertama untuk menarik perhatian penonton dalam 3 detik pertama.
4. Berikan nilai `hook_score` antara 0 sampai 100 berdasarkan kekuatan pembuka dan kelengkapan inti cerita.
5. Berikan `virality_reason` singkat (maksimal 1-2 kalimat) yang menjelaskan kenapa momen ini menarik.

FORMAT JAWABAN:
Balas HANYA dengan array JSON yang valid, TANPA format markdown block (tanpa ```json), TANPA salam pembuka atau penjelasan tambahan.

[
  {
    "title": "Judul klip singkat & menarik (maksimal 80 karakter)",
    "start_time_seconds": 12.5,
    "end_time_seconds": 58.2,
    "hook_score": 92,
    "virality_reason": "Pernyataan kontroversial di awal langsung memicu rasa ingin tahu penonton."
  }
]

TRANSKRIP VIDEO:
{transcript}
```

#### Validasi Bisnis & Sanitasi Output
- **Pembersihan Respon**: Menghapus tanda markdown ```json dan ``` jika LLM tetap menyertakannya, lalu mem-parse string ke array Pydantic model.
- **Validasi Nilai**:
  - $0 \le \text{start\_time\_seconds} < \text{end\_time\_seconds} \le \text{duration\_video}$.
  - Durasi klip ($\text{end} - \text{start}$) wajib di antara `MIN_CLIP_SECONDS` (default 10 detik) dan `MAX_CLIP_SECONDS` (default 90 detik).
  - **Overlap Suppression**: Jika dua kandidat memiliki tumpang tindih waktu $>50\%$, kandidat dengan `hook_score` lebih rendah akan dieliminasi.
  - `hook_score` dipastikan berada di rentang 0–100.
- **Mekanisme Retry**: Jika respons LLM rusak / tidak dapat di-parse, lakukan retry maksimal 3 kali dengan *exponential backoff* (2s, 4s, 8s). Jika seluruh retry gagal, video tetap berstatus `READY` (tanpa kandidat klip) dan UI menampilkan tombol *"Analisis Ulang"*.

---

### 5.4 Modul 4: Vertical Rendering & Burn-in Caption (FFmpeg + ASS)

#### Template Subtitle ASS (`storage/subtitles/{clip_id}.ass`)
Subtitle dibuat dinamis per klip dari *word-level timestamps*. Kata aktif diwarnai menggunakan tag inline `{\c&H<active_color>&}`.

```ini
[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Caption,Poppins,44,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,3,1,2,60,60,320,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.00,0:00:02.40,Caption,,0,0,0,,{\c&H0000CCFF&}Halo{\c&H00FFFFFF&} semuanya selamat datang
Dialogue: 0,0:00:02.40,0:00:04.10,Caption,,0,0,0,,kembali di podcast {\c&H0000CCFF&}kami{\c&H00FFFFFF&} hari ini
```

> [!CAUTION]
> ### Jebakan Konversi Warna ASS (Wajib Dibaca Pengembang)
> Format warna standar ASS adalah **`&HAABBGGRR&`** (Blue-Green-Red, **bukan** Red-Green-Blue).
> Jika warna hex dari UI adalah `#FFCC00` (Kuning Emas, R=FF, G=CC, B=00), maka konversinya ke format ASS adalah:
> $$\text{\#FFCC00} \longrightarrow \mathbf{\&H0000CCFF\&}$$
> *Implementer wajib menggunakan utilitas teruji `hex_to_ass()` beserta unit test.*

#### Perintah Render FFmpeg (Progress-Aware)
```bash
# 1. Center Crop (Default 9:16)
ffmpeg -y -progress pipe:1 -nostats \
  -ss {start_time} -to {end_time} -i "storage/uploads/{video_id}.mp4" \
  -vf "crop=ih*(9/16):ih:(iw-ow)/2:0,subtitles=storage/subtitles/{clip_id}.ass:fontsdir=/usr/share/fonts/truetype/custom" \
  -c:v libx264 -preset fast -crf 22 -profile:v high \
  -c:a aac -b:a 128k -movflags +faststart \
  "storage/exports/{short_id}_9x16.mp4"

# 2. Manual Shift Crop (Jika crop_offset_x ditentukan via UI, diclamp: 0 <= x <= iw - ow)
ffmpeg -y -progress pipe:1 -nostats \
  -ss {start_time} -to {end_time} -i "storage/uploads/{video_id}.mp4" \
  -vf "crop=ih*(9/16):ih:{crop_offset_x}:0,subtitles=storage/subtitles/{clip_id}.ass:fontsdir=/usr/share/fonts/truetype/custom" \
  -c:v libx264 -preset fast -crf 22 -profile:v high \
  -c:a aac -b:a 128k -movflags +faststart \
  "storage/exports/{short_id}_9x16.mp4"
```

#### Parsing Progress Render
Backend membaca output `pipe:1` secara realtime. Baris `out_time_us=...` diekstraksi untuk menghitung persentase:
$$\text{Progress (\%)} = \min\left(100, \left(\frac{\text{out\_time\_us} / 1.000.000}{\text{durasi\_klip\_detik}}\right) \times 100\right)$$
Update progress ke tabel `rendered_shorts.render_progress` di-throttle setiap interval kenaikan minimal 5% untuk mencegah overload database I/O.

---

### 5.5 Modul 5: Google Drive Upload

#### Mode Autentikasi
Kredensial disimpan terenkripsi pada tabel `app_settings`:

| Mode | Field yang Disimpan | Karakteristik & Catatan Khusus |
| :--- | :--- | :--- |
| **Service Account** *(Direkomendasikan)* | `gdrive_sa_json`, `gdrive_folder_id` | Sangat cocok untuk local server/daemon. **Wajib:** Folder tujuan di Google Drive pengguna HARUS dibagikan (*shared*) ke email Service Account (`xxx@yyy.iam.gserviceaccount.com`) dengan role **Editor**. Jika tidak di-share, Google API mengembalikan error `404 File Not Found`. |
| **OAuth2 User Auth** | `gdrive_client_id`, `gdrive_client_secret`, `gdrive_refresh_token`, `gdrive_folder_id` | Memerlukan login interaktif satu kali untuk mendapatkan Refresh Token. Access token diperbarui otomatis oleh library `google-auth`. |

#### Eksekusi Resumable Upload
```python
from googleapiclient.http import MediaFileUpload

media = MediaFileUpload(
    file_path, 
    mimetype="video/mp4", 
    resumable=True, 
    chunksize=8 * 1024 * 1024  # 8 MB chunks
)

request = drive_service.files().create(
    body={"name": filename, "parents": [target_folder_id]},
    media_body=media,
    fields="id, webViewLink"
)

response = None
while response is None:
    status, response = request.next_chunk(num_retries=5)
    if status:
        progress = int(status.progress() * 100)
        update_export_progress(export_id, progress)

# Simpan ID dan tautan publik
save_drive_result(export_id, response["id"], response["webViewLink"])
```

---

## 6. Spesifikasi API (RESTful)

### 6.1 Konvensi Global
- **Base URL**: `/api`
- **Header Default**: `Content-Type: application/json` (kecuali upload: `multipart/form-data`)
- **Format Error Envelope Standar**:
```json
{
  "error": {
    "code": "VIDEO_NOT_FOUND",
    "message": "Video dengan ID tersebut tidak ditemukan.",
    "detail": null
  }
}
```
- **Format Respons Paginasi Standar**:
```json
{
  "items": [],
  "page": 1,
  "limit": 20,
  "total": 57
}
```

### 6.2 Daftar Endpoint

#### 1. Authentication (`/api/auth`)
| Method | Path | Deskripsi & Payload | Status & Response |
| :--- | :--- | :--- | :--- |
| `GET` | `/auth/status` | Cek status inisialisasi PIN dan status sesi aktif. | `200 OK` `{"is_configured": true, "has_session": false}` |
| `POST` | `/auth/setup` | Inisialisasi PIN pertama kali. Body: `{"pin": "123456"}`. | `201 Created` `{"token": "..."}` atau `409 Conflict` jika sudah pernah diset. |
| `POST` | `/auth/login` | Login menggunakan PIN. Body: `{"pin": "123456"}`. | `200 OK` `{"token": "..."}`, `401` jika salah, `429` jika cooldown. |
| `POST` | `/auth/logout` | Invalidate token pada sisi klien (stateless). | `200 OK` `{}` |

#### 2. Settings (`/api/settings`)
| Method | Path | Deskripsi & Payload | Status & Response |
| :--- | :--- | :--- | :--- |
| `GET` | `/settings` | Membaca konfigurasi aktif (nilai sensitif dimasking `******` dengan flag `is_set: true/false`). | `200 OK` `{"llm_base_url": "...", "llm_model": "...", "gdrive_configured": true, ...}` |
| `POST` | `/settings/ai` | Menyimpan konfigurasi LLM. Body: `{"base_url": "...", "api_key": "...", "model_name": "...", "temperature": 0.4, "prompt": "..."}`. | `200 OK` `{"status": "saved"}` |
| `POST` | `/settings/gdrive` | Menyimpan konfigurasi Google Drive (Mode SA / OAuth2). | `200 OK` `{"status": "saved"}` |
| `POST` | `/settings/gdrive/test`| Melakukan uji verifikasi akses ke folder Google Drive tujuan. | `200 OK` `{"ok": true, "folder_name": "My Shorts"}` atau `{"ok": false, "error": "..."}` |

#### 3. Videos & Processing Pipeline (`/api/videos`)
| Method | Path | Deskripsi & Payload | Status & Response |
| :--- | :--- | :--- | :--- |
| `POST` | `/videos/upload` | Mengunggah video mentah (`multipart/form-data`, key: `file`). | `201 Created` `{"video_id": "...", "filename": "...", "duration_seconds": 120.5, "file_size_bytes": 10485760}` |
| `GET` | `/videos` | List video terpaginasi dengan filter opsional `?status=READY`. | `200 OK` `{"items": [{"id": "...", "original_name": "...", "status": "...", ...}], "page": 1, ...}` |
| `POST` | `/videos/{id}/process` | Memicu eksekusi pipeline asinkron (Ekstraksi Audio → Whisper → LLM). | `202 Accepted` `{"status": "QUEUED", "video_id": "..."}` atau `409` jika sedang berjalan. |
| `GET` | `/videos/{id}/status` | Polling ringkasan status dan progress per sub-job. | `200 OK` `{"status": "TRANSCRIBING", "error_message": null, "job_progress": {"audio_extract": 100, "transcribe": 45, "analyze": 0}}` |
| `GET` | `/videos/{id}/transcript` | Mengambil transkrip lengkap teks dan link JSON. | `200 OK` `{"full_text": "...", "language": "id", "json_url": "/api/videos/{id}/transcript/json"}` |
| `GET` | `/videos/{id}/clips` | Mengambil daftar rekomendasi kandidat klip hasil analisis LLM. | `200 OK` `[{"id": "...", "title": "...", "start_time_seconds": 12.5, "end_time_seconds": 58.2, "hook_score": 92, "virality_reason": "..."}]` |
| `GET` | `/videos/{id}/thumbnail` | Mengambil berkas gambar poster video. | `200 OK` Stream Image (`image/jpeg`) |
| `DELETE`| `/videos/{id}` | Menghapus video beserta seluruh artefak fisik dan relasi DB. | `204 No Content` |

#### 4. Clips & Customization (`/api/clips`)
| Method | Path | Deskripsi & Payload | Status & Response |
| :--- | :--- | :--- | :--- |
| `PATCH` | `/clips/{id}` | Penyesuaian manual segmen klip sebelum dirender. Body: `{"is_selected": true, "title": "...", "start_time_seconds": 15.0, "end_time_seconds": 50.0}`. | `200 OK` Object `clip_candidates` terupdate |
| `POST` | `/clips/{id}/render` | Memicu render vertikal klip. Body: `{"crop_mode": "center"|"manual", "crop_offset_x": 120, "font": "Poppins", "font_size": 44, "active_color": "#FFCC00", "primary_color": "#FFFFFF"}`. | `202 Accepted` `{"short_id": "...", "status": "PENDING"}` |

#### 5. Rendered Shorts & Export (`/api/shorts`)
| Method | Path | Deskripsi & Payload | Status & Response |
| :--- | :--- | :--- | :--- |
| `GET` | `/shorts` | List hasil render vertikal terpaginasi. | `200 OK` Paged response rendered shorts |
| `GET` | `/shorts/{id}` | Detail status render dan informasi unduhan klip. | `200 OK` `{"id": "...", "render_status": "COMPLETED", "render_progress": 100, "download_url": "...", "gdrive": {...}}` |
| `GET` | `/shorts/{id}/download`| Mengunduh atau streaming berkas MP4 hasil render. | `200 OK` Stream Video (`video/mp4`, `Content-Disposition: attachment`) |
| `POST` | `/shorts/{id}/upload-gdrive` | Memicu antrean upload hasil klip ke Google Drive. | `202 Accepted` `{"export_id": "...", "status": "QUEUED"}` |
| `GET` | `/shorts/{id}/upload-gdrive/status` | Polling status dan persentase upload Google Drive. | `200 OK` `{"upload_status": "UPLOADING", "upload_progress": 70, "gdrive_web_view_link": null}` |
| `DELETE`| `/shorts/{id}` | Menghapus berkas video 9:16 dan record terkait. | `204 No Content` |

#### 6. System & Health (`/api/health`)
| Method | Path | Deskripsi & Payload | Status & Response |
| :--- | :--- | :--- | :--- |
| `GET` | `/health` | Healthcheck tanpa autentikasi untuk Docker dan monitoring. | `200 OK` `{"status": "ok", "db": true, "storage_writable": true, "ffmpeg": "6.1"}` |

---

## 7. Non-Functional Requirements (NFR)

| Kategori | Target Kinerja & Batasan Teknis |
| :--- | :--- |
| **Performa Render** | Waktu render video vertikal $\le 2\times$ durasi klip pada CPU, atau $\le 0.8\times$ durasi klip jika akselerasi GPU aktif. Transkripsi 60 menit audio $\le 30$ menit pada CPU (model `base`), atau $\le 5$ menit pada GPU (model `small`). |
| **Concurrency Control**| Dibatasi secara eksplisit di environment: `TRANSCRIBE_CONCURRENCY=1` (mencegah memory thrashing) dan `RENDER_CONCURRENCY=2`. Pekerjaan lain mengantre di `app_jobs`. |
| **Reliability & Self-Healing** | Loop *Job Reaper* berjalan periodik setiap 60 detik. Job berstatus `RUNNING` dengan `started_at` $> 30$ menit yang terputus (misal akibat restart container) otomatis dikembalikan ke `QUEUED` untuk dieksekusi ulang. |
| **Keamanan Sistem** | PIN di-hash dengan **Argon2id**; kredensial eksternal dienkripsi **AES-256-GCM**; token JWT bertanda tangan digital HS256; CORS dikunci hanya untuk origin web frontend; upload file diverifikasi via ekstensi dan header magic-bytes. |
| **Observabilitas** | Logging terstruktur berformat JSON (`job_id`, `video_id`, `stage`, `duration_ms`). Jika FFmpeg atau Whisper gagal, 500 karakter terakhir dari `stderr` dicatat ke database dan log file. |
| **Portabilitas Kontainer**| Bebas dari path absolut host; seluruh referensi media berakar pada `/storage`. Migrasi skema database dijalankan otomatis via `alembic upgrade head` pada startup backend. |

---

## 8. Docker & Environment

### 8.1 `.env.example`

```bash
# ==========================================
# Database Configuration (MySQL 8.0)
# ==========================================
MYSQL_ROOT_PASSWORD=super_secret_root_password
MYSQL_DATABASE=autoshorts
MYSQL_USER=autoshorts
MYSQL_PASSWORD=autoshorts_secure_password
DATABASE_URL=mysql+asyncmy://autoshorts:autoshorts_secure_password@db-mysql:3306/autoshorts

# ==========================================
# Security & Cryptography
# ==========================================
# Generate dengan: openssl rand -hex 32
JWT_SECRET=b64e5912443f115a31a9805d76d4982ba6911c4715dc2112d71fa8430e3be75a
# Kunci 32-byte Base64 untuk enkripsi AES-256-GCM (openssl rand -base64 32)
SETTINGS_ENCRYPTION_KEY=cDRzc3cwcmRfa2V5XzMyX2J5dGVzX2xvbmdfYmFzZTY0IQ==

# ==========================================
# Storage & Application Limits
# ==========================================
STORAGE_ROOT=/storage
MAX_UPLOAD_SIZE_MB=2048
MIN_CLIP_SECONDS=10
MAX_CLIP_SECONDS=90
AUTO_CLEANUP_DAYS=0

# ==========================================
# Worker Concurrency
# ==========================================
TRANSCRIBE_CONCURRENCY=1
RENDER_CONCURRENCY=2

# ==========================================
# Faster-Whisper Configuration
# ==========================================
# Model: tiny | base | small | medium | large-v3
WHISPER_MODEL=small
# Device: cpu | cuda
WHISPER_DEVICE=cpu
# Compute Type: int8 | float16 | int8_float16
WHISPER_COMPUTE_TYPE=int8

# ==========================================
# Frontend Configuration
# ==========================================
VITE_API_BASE_URL=/api
```

### 8.2 `docker-compose.yml`

```yaml
version: "3.8"

services:
  db-mysql:
    image: mysql:8.0
    container_name: autoshorts-db
    restart: unless-stopped
    environment:
      MYSQL_ROOT_PASSWORD: ${MYSQL_ROOT_PASSWORD}
      MYSQL_DATABASE: ${MYSQL_DATABASE}
      MYSQL_USER: ${MYSQL_USER}
      MYSQL_PASSWORD: ${MYSQL_PASSWORD}
    volumes:
      - mysql_data:/var/lib/mysql
    ports:
      - "3306:3306"
    healthcheck:
      test: ["CMD", "mysqladmin", "ping", "-h", "localhost", "-u", "${MYSQL_USER}", "-p${MYSQL_PASSWORD}"]
      interval: 10s
      timeout: 5s
      retries: 10

  api-backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: autoshorts-backend
    restart: unless-stopped
    env_file: .env
    volumes:
      - ./storage:/storage
    ports:
      - "8000:8000"
    depends_on:
      db-mysql:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/health"]
      interval: 15s
      timeout: 5s
      retries: 5

  web-frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    container_name: autoshorts-frontend
    restart: unless-stopped
    ports:
      - "3000:80"
    depends_on:
      - api-backend

volumes:
  mysql_data:
    driver: local
```

---

## 9. Struktur Proyek (`auto-shorts-local`)

```text
auto-shorts-local/
├── prd/
│   └── PRD.md                       # Single Source of Truth Dokumen Spesifikasi
├── .env.example                     # Template environment variables
├── docker-compose.yml               # Definisi multi-container orchestration
├── storage/                         # Volume bind-mount (terabaikan di git)
│   └── ...
│
├── frontend/                        # React + Vite + Tailwind CSS
│   ├── Dockerfile
│   ├── nginx.conf                   # Reverse proxy /api ke backend:8000
│   ├── package.json
│   ├── vite.config.ts
│   └── src/
│       ├── components/              # AuthModal, VideoPlayer, ClipCard, CropPreview, SettingsModal
│       ├── hooks/                   # usePolling, useAuth, useVideos
│       ├── pages/                   # Dashboard, VideoDetail, ClipEditor, Settings
│       ├── services/
│       │   └── api.ts               # Axios instance, Bearer interceptor, error envelope parser
│       └── App.tsx
│
└── backend/                         # FastAPI + Async Workers
    ├── Dockerfile                   # Python 3.11-slim + FFmpeg + fonts-dejavu + Poppins
    ├── requirements.txt
    ├── alembic.ini
    ├── alembic/
    │   ├── env.py
    │   └── versions/                # Migration scripts
    └── app/
        ├── main.py                  # FastAPI bootstrap, routers, startup events
        ├── config.py                # Pydantic Settings (.env validator)
        ├── database.py              # Async SQLAlchemy engine & session factory
        ├── worker.py                # Background job poller & reaper loop
        ├── models/                  # SQLAlchemy ORM models (videos, clips, shorts, jobs, etc.)
        ├── schemas/                 # Pydantic request/response schemas
        ├── routers/                 # auth.py, settings.py, videos.py, clips.py, shorts.py, health.py
        ├── core/
        │   ├── security.py          # Argon2id, JWT encode/decode, get_current_session
        │   └── crypto.py            # AES-256-GCM settings encryption/decryption
        ├── services/
        │   ├── storage_service.py   # Path resolver, atomic writes, delete artifacts
        │   ├── ffmpeg_service.py    # ffprobe, extract_audio, generate_thumbnail, render_clip
        │   ├── whisper_service.py   # faster-whisper transcription & VAD
        │   ├── llm_service.py       # OpenAI-compatible client, prompt builder, validator
        │   ├── ass_service.py       # ASS generator, hex_to_ass color converter
        │   ├── gdrive_service.py    # Resumable chunk uploader
        │   └── pipeline.py          # Async job state transition coordinator
        └── utils/
            └── subprocess_utils.py  # Process runner with timeout & stderr capture
```

---

## 10. Panduan Implementasi Berfase untuk AI Coding Agent

Implementasi wajib dilakukan secara berurutan (*phase-by-phase*). Setiap fase harus diverifikasi melalui kriteria penerimaan sebelum melangkah ke fase berikutnya:

| Fase | Fokus Deliverable | Acceptance Test / Gate Check |
| :--- | :--- | :--- |
| **Fase 0: Infrastruktur** | `docker-compose.yml`, `.env.example`, `Dockerfile` Backend & Frontend. | `docker compose up -d` berhasil menjalankan ketiga container; `GET /api/health` mengembalikan `200 OK`. |
| **Fase 1: Data Layer** | Skema SQLAlchemy 2.0 async, setup Alembic, script migrasi initial. | `alembic upgrade head` sukses tanpa error; seluruh 8 tabel terbentuk dengan relasi FK dan indeks. |
| **Fase 2: Auth PIN** | `core/security.py`, `routers/auth.py`, middleware proteksi endpoint. | Setup PIN baru $\rightarrow$ Login dapat token $\rightarrow$ Akses route proteksi berhasil; Setup kedua kali $\rightarrow$ ditolak `409 Conflict`. |
| **Fase 3: Upload & Storage**| `routers/videos.py`, `services/storage_service.py`, thumbnail extraction. | Unggah video MP4 $\rightarrow$ berkas tersimpan di `storage/uploads/` dan thumbnail di `thumbnails/`; `DELETE` menghapus record dan berkas fisik. |
| **Fase 4: Pipeline Audio & Transkrip** | `ffmpeg_service.py`, `whisper_service.py`, `worker.py` (ekstraksi & transkripsi). | Video diproses $\rightarrow$ audio WAV 16kHz terbentuk $\rightarrow$ Whisper menghasilkan JSON dengan `words[]` $\rightarrow$ status `source_videos` berubah teratur. |
| **Fase 5: Analisis Highlight LLM** | `llm_service.py`, sanitasi JSON, fallback parsing, retry backoff. | Transkrip dikirim ke LLM $\rightarrow$ `clip_candidates` terisi 3–5 klip valid; jika LLM mengembalikan format rusak, retry berjalan 3x. |
| **Fase 6: Render Vertikal & ASS** | `ass_service.py`, konversi warna BGR, render FFmpeg dengan progress pipe. | Klip dirender ke 1080x1920 9:16 $\rightarrow$ subtitle karaoke terbakar dengan warna highlight presisi; progress ter-update di database. |
| **Fase 7: Ekspor Google Drive** | `gdrive_service.py`, settings Google Drive, resumable chunk uploader. | Uji koneksi folder sukses; render video di-upload ke Drive $\rightarrow$ tautan web view tersimpan di database. |
| **Fase 8: Frontend UI & Polishing** | Halaman dashboard, editor klip, modal settings, polling status TanStack. | Pengujian End-to-End di browser: Login $\rightarrow$ Upload $\rightarrow$ Review Klip $\rightarrow$ Atur Crop/Warna $\rightarrow$ Render $\rightarrow$ Unduh / Ekspor ke Drive. |

### Aturan Wajib untuk AI Agent:
1. **FFmpeg Subprocess**: Semua pemanggilan FFmpeg/FFprobe wajib dibungkus dalam `run_with_timeout()`. Jangan pernah membiarkan proses *hang* tanpa batas waktu. Jika gagal, simpan 500 karakter terakhir `stderr` ke kolom `error_message`.
2. **Klaim Antrean Atomik**: Worker wajib mengklaim job dari `app_jobs` secara atomik menggunakan:
   ```sql
   UPDATE app_jobs 
   SET status = 'RUNNING', started_at = NOW() 
   WHERE id = (
       SELECT id FROM (
           SELECT id FROM app_jobs 
           WHERE status = 'QUEUED' 
           ORDER BY created_at ASC 
           LIMIT 1 
           FOR UPDATE SKIP LOCKED
       ) AS next_job
   );
   ```
3. **Konversi Warna ASS**: Utilitas `hex_to_ass()` wajib diuji unit test dengan kasus uji `#FFCC00` menghasilkan `&H0000CCFF&`.

---

## 11. Matriks Edge Case & Error Handling

| # | Skenario Masalah | Perilaku Sistem yang Diharapkan |
| :---: | :--- | :--- |
| **1** | Berkas di-upload bukan video (misal file teks di-rename `.mp4`). | FFprobe gagal mendeteksi video stream $\rightarrow$ job `AUDIO_EXTRACT` ditandai `FAILED` dengan pesan *"Invalid video file or no video stream detected"*. |
| **2** | Berkas video tidak memiliki stream audio. | FFprobe mendeteksi tidak ada stream audio $\rightarrow$ job langsung ditandai `FAILED` dengan pesan *"No audio track present in uploaded file"*. |
| **3** | LLM endpoint down atau API Key salah. | Sistem melakukan retry 3x. Jika tetap gagal, status video tetap `READY` tanpa kandidat klip. UI menampilkan notifikasi peringatan dan tombol *"Analisis Ulang"*. |
| **4** | Respons LLM mengandung markdown fence atau teks di luar JSON. | Sanitizer melepaskan blok fence ` ```json ` dan mencari substring array JSON valid pertama `[...]`. Jika gagal, dianggap satu percobaan gagal. |
| **5** | LLM mengembalikan timestamp di luar batas durasi video. | Validator membuang segmen invalid. Jika seluruh segmen invalid, sistem memperlakukan sama seperti skenario kegagalan LLM. |
| **6** | Container backend terhenti / restart mendadak saat proses render. | Loop *Job Reaper* mendeteksi job `RUNNING` dengan `started_at` $>30$ menit yang lalu, mengembalikan statusnya ke `QUEUED` untuk dieksekusi ulang. |
| **7** | Disk penyimpanan host penuh saat proses render berlangsung. | FFmpeg keluar dengan error $\rightarrow$ job ditandai `FAILED`. Endpoint `/api/health` mendeteksi disk penuh (`storage_writable: false`) dan menampilkan banner peringatan di UI. |
| **8** | Token Google Drive expired di tengah proses upload berkas besar. | Refresh token dipanggil secara otomatis oleh client library dan upload dilanjutkan kembali dari chunk terakhir tanpa mengulang dari 0%. |
| **9** | Folder Google Drive belum di-share ke email Service Account. | Uji koneksi atau proses upload gagal dengan pesan edukatif: *"Pastikan folder Google Drive telah di-share ke email Service Account sebagai Editor"*. |
| **10**| Pengguna mengunggah dua berkas identik berturut-turut. | Sistem tetap mengizinkan dan men-generate `video_id` UUID baru untuk masing-masing berkas guna menjaga independensi state. |
| **11**| Dua render dipicu secara bersamaan untuk video yang sama. | Sistem mengizinkan selama clip ID berbeda. Concurrency dibatasi oleh `RENDER_CONCURRENCY` di mana job kedua akan menunggu di antrean. |
| **12**| Pengguna salah memasukkan PIN sebanyak 5 kali berturut-turut. | Sistem mengembalikan HTTP `429 Too Many Requests` dan memberlakukan jeda waktu (*cooldown*) selama 5 menit untuk IP klien tersebut. |

---

## 12. Acceptance Criteria (Definition of Done)

Proyek dinyatakan selesai dan siap diproduksi jika seluruh kriteria berikut terpenuhi:
- [x] **Docker Deployment**: Menjalankan `docker compose up -d` berhasil menginisialisasi ketiga service hingga berstatus *healthy* tanpa intervensi konfigurasi manual.
- [x] **First-Run Gatekeeper**: Saat database bersih, halaman Setup PIN muncul otomatis di frontend. Setelah setup berhasil, semua endpoint privat mengembalikan `401 Unauthorized` jika diakses tanpa token Bearer JWT.
- [x] **Integritas Upload**: Video 30–60 menit berhasil diunggah, thumbnail dihasilkan di `storage/thumbnails/`, dan metadata video tersimpan di tabel `source_videos`.
- [x] **Akurasi Transkripsi**: Transkripsi Whisper menghasilkan `transcripts/{video_id}.json` yang berisi segmen dan `words[]` dengan *word-level timestamps* yang presisi terhadap audio.
- [x] **Rekomendasi Klip AI**: LLM menghasilkan minimal 3–5 rekomendasi klip dengan durasi di rentang 10–90 detik, `hook_score` valid, dan tidak ada segmen yang saling tumpang tindih $>50\%$.
- [x] **Kualitas Render Vertikal**: Video hasil render memiliki resolusi presisi 1080x1920 (9:16), audio tersinkronisasi, dan subtitle karaoke menyala kata-per-kata dengan warna highlight yang akurat (verifikasi visual).
- [x] **Pemantauan Progress**: Persentase render dan upload ter-update secara real-time / ter-throttle di UI melalui mekanisme polling status.
- [x] **Google Drive Resilience**: Berkas hasil render berhasil diunggah ke Google Drive dan tautan web view yang dihasilkan dapat dibuka secara publik / pemilik akun.
- [x] **Isolasi Path Relatif**: Tidak ada satupun path absolut sistem operasi host yang tersimpan di kolom database.
- [x] **Enkripsi Kredensial**: Semua API Key dan file rahasia tersimpan dalam format terenkripsi AES-256-GCM di database.
- [x] **Pembersihan Bersih**: Menjalankan operasi `DELETE` pada video menghapus seluruh data relasional di database serta berkas fisik terkait di filesystem storage.
- [x] **Health Check & Recovery**: Endpoint `/api/health` dapat diakses publik dan melaporkan kondisi database, filesystem storage, dan ketersediaan FFmpeg.

---

## 13. Glossary (Daftar Istilah)

- **Shorts / Clip**: Video pendek berorientasi vertikal (rasio 9:16, 1080x1920) berdurasi 10–90 detik yang dipotong dari video sumber horizontal (16:9).
- **Hook Score**: Skor prediksi probabilitas viralitas konten (skala 0–100) yang dievaluasi oleh LLM berdasarkan kekuatan pembuka (*hook*) 3–5 detik pertama dan retensi penonton.
- **Word-level Timestamps**: Penanda waktu mulai (*start*) dan selesai (*end*) dengan presisi milidetik untuk setiap kata individual yang dihasilkan oleh model ASR Whisper.
- **Burn-in Subtitle (Hardsub)**: Subtitle yang dirender dan dikompresi langsung ke dalam piksel video (frame) menggunakan FFmpeg libass, sehingga teks menyatu permanen dengan video.
- **ASS (Advanced SubStation Alpha)**: Format file subtitle tingkat lanjut yang mendukung styling kompleks, font kustom, margin, posisi koordinat, dan tag efek animasi warna inline (karaoke style).
- **Karaoke Style**: Efek animasi teks subtitle di mana kata yang sedang diucapkan pembicara berubah warna (*highlight*) secara presisi mengikuti kata per kata.
- **Resumable Upload**: Metode pengunggahan berkas besar ke cloud storage (Google Drive API) secara berulang per bagian (*chunks*), yang dapat dilanjutkan kembali jika terjadi interupsi jaringan.
- **Job Reaper**: Background task periodik yang memonitor dan memulihkan antrean pekerjaan (*job queue*) dari status macet/orphan akibat worker crash atau restart container.
- **Local-First**: Pola arsitektur di mana seluruh pemrosesan utama (ekstraksi, transkripsi AI, penyimpanan file, rendering) berjalan sepenuhnya di infrastruktur lokal pengguna.

---

## 14. Lampiran Teknis

### Lampiran A: Pemetaan Respons Whisper ke Database

```text
faster-whisper transcribe()
├── info.language
│   └── Disimpan ke: source_videos.language (cth: 'id', 'en')
│
├── segments[]
│   ├── segment.text (digabungkan seluruhnya)
│   │   └── Disimpan ke: transcripts.full_text (LONGTEXT)
│   │
│   └── segment.start, segment.end, segment.words[]
│       └── Disimpan ke: storage/transcripts/{video_id}.json
```

### Lampiran B: Utilitas Konversi Warna ASS (`hex_to_ass`)

```python
def hex_to_ass(hex_color: str, alpha: int = 0x00) -> str:
    """
    Mengonversi format warna heksadesimal RGB (#RRGGBB) ke format ASS (&HAABBGGRR&).
    Format ASS membalik urutan Red dan Blue (BGR), bukan RGB!
    
    Contoh Kasus Uji:
    >>> hex_to_ass("#FFCC00")  # Kuning Emas (R=FF, G=CC, B=00)
    '&H0000CCFF&'
    >>> hex_to_ass("#FFFFFF")  # Putih
    '&H00FFFFFF&'
    """
    clean_hex = hex_color.lstrip("#")
    if len(clean_hex) != 6:
        raise ValueError(f"Invalid hex color format: {hex_color}")
        
    r = int(clean_hex[0:2], 16)
    g = int(clean_hex[2:4], 16)
    b = int(clean_hex[4:6], 16)
    
    return f"&H{alpha:02X}{b:02X}{g:02X}{r:02X}&"
```

### Lampiran C: Konfigurasi Kritis Dockerfile Backend

```dockerfile
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

# Install dependencies sistem, FFmpeg dengan libass, font cache, dan utilities
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    fonts-dejavu-core \
    fontconfig \
    curl \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Buat direktori font kustom dan salin font Poppins / Inter Bold
WORKDIR /usr/share/fonts/truetype/custom
RUN curl -fsSL -o Poppins-Bold.ttf https://github.com/google/fonts/raw/main/ofl/poppins/Poppins-Bold.ttf \
    && curl -fsSL -o Poppins-SemiBold.ttf https://github.com/google/fonts/raw/main/ofl/poppins/Poppins-SemiBold.ttf \
    && fc-cache -f -v

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
```

---

> **Status Dokumen**: Dokumen ini adalah sumber kebenaran tunggal (*Single Source of Truth*) untuk proyek `auto-shorts-local`. Jika terdapat inkonsistensi antara kode program dan spesifikasi ini, spesifikasi dalam PRD ini adalah acuan yang berlaku.
