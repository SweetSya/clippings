# AutoShorts Local (`auto-shorts-local`)
### Local AI Video Clipper & Shorts Generator with Text-to-Speech

Sistem pembuat video pendek vertikal (*TikTok*, *Instagram Reels*, *YouTube Shorts*) dari video panjang berbasis AI yang berjalan sepenuhnya secara lokal di mesin pengguna (*Local-First*). Dilengkapi dengan transkripsi **Whisper lokal**, deteksi klip viral via **LLM**, hardsub **karaoke animated subtitle (FFmpeg + ASS)**, studio **Text-to-Speech (TTS)**, dan sinkronisasi ekspor ke **Google Drive** dengan proteksi anti-double upload.

Antarmuka web dirancang mengikuti panduan desain visual **Ember Studio** (`design.md`) dengan palet warna Terracotta (`#C2410C`), Amber (`#F59E0B`), tipografi *Playfair Display* & *Source Sans 3*, serta tata letak responsif.

---

## 🌟 Fitur Utama

1. **Upload & Local Storage**:
   - Menerima video mentah (`.mp4`, `.mkv`, `.mov`, `.avi`, `.webm`) hingga ukuran 2GB.
   - Menyimpan seluruh berkas di storage lokal (`./storage/uploads/`).
   - Ekstraksi frame poster thumbnail otomatis (`./storage/thumbnails/`).
2. **Audio & Transkripsi Whisper Lokal**:
   - Ekstraksi audio PCM 16kHz mono (`./storage/audio/`).
   - Transkripsi kata-per-kata menggunakan engine **faster-whisper** dengan *Voice Activity Detection (VAD)*.
   - Menghasilkan word-level timestamps untuk animasi subtitle.
3. **Deteksi Momen Viral (AI Highlights)**:
   - Menganalisis transkrip dengan custom LLM endpoint (*OpenAI-compatible*).
   - Fitur fallback heuristik cerdas tanpa perlu memasukkan API key.
   - Evaluasi skor viralitas (*hook score* 0–100) dan eliminasi klip tumpang tindih (>50%).
4. **Editor Klip & Render Vertikal 9:16**:
   - Kustomisasi framing: *Center Crop* atau *Manual Shift Offset X*.
   - Kustomisasi subtitle: Pilihan font, ukuran, warna dasar, dan warna highlight kata aktif karaoke.
   - Utilitas konversi warna **BGR ASS** (`&HAABBGGRR&`) yang akurat.
   - Rendering video vertikal 1080x1920 H.264/AAC via FFmpeg dengan live progress bar.
5. **Ekspor Google Drive (Anti-Double Upload)**:
   - Integrasi Google Drive API v3 (Service Account atau OAuth2).
   - Upload berkas berukuran besar secara resumable chunk.
   - **Proteksi Anti-Double Upload**: Sistem mendeteksi jika klip telah berhasil diunggah (`is_drive_uploaded = True`), mencegah terjadinya file duplikat di Google Drive.
6. **Text-to-Speech (TTS) Studio**:
   - Pembuatan narasi suara AI lokal secara instan menggunakan `edge-tts`.
   - Pilihan suara alami Bahasa Indonesia (*Ardi, Gadis*) dan Bahasa Inggris (*Christopher, Jenny*).
   - Penyetelan kecepatan (*rate*) dan nada (*pitch*).
   - Pemutar audio terintegrasi dan riwayat narasi suara.
7. **PIN Gatekeeper & Keamanan**:
   - Akses antarmuka dikunci dengan 4–8 digit PIN numerik.
   - Hashing dengan algoritma **Argon2id** dan proteksi sesi menggunakan **JWT HS256**.
   - Enkripsi kredensial sensitif di database menggunakan **AES-256-GCM**.
   - Brute-force guard: 5 kali salah berturut-turut memicu cooldown 5 menit.

---

## 📂 Struktur Direktori

```text
.
├── .env.example              # Template variabel lingkungan
├── .env                      # Konfigurasi aktif (terisi default siap pakai)
├── docker-compose.yml        # Orchestration multi-container (MySQL, FastAPI, Nginx)
├── start_local.sh            # Script cepat untuk menjalankan backend & frontend
├── design.md                 # Ember Studio Design System guideline
├── prd/
│   ├── PRD.md                # Dokumen Spesifikasi Produk (PRD v2.1.0)
│   └── README.md             # Ringkasan navigasi PRD
├── storage/                  # Bind-mount penyimpanan berkas lokal
│   ├── uploads/              # Video mentah asli
│   ├── audio/                # Audio 16kHz WAV
│   ├── transcripts/          # Berkas transcript JSON Whisper
│   ├── subtitles/            # Subtitle ASS karaoke per klip
│   ├── thumbnails/           # Poster frame JPEG
│   ├── exports/              # Video shorts 9:16 hasil render
│   ├── tts/                  # Audio narasi Text-to-Speech MP3
│   └── credentials/          # Token dan kredensial OAuth
├── backend/                  # FastAPI Application
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── alembic.ini
│   ├── app/                  # Kode sumber backend
│   └── tests/                # Suite pengujian unit & integrasi
└── frontend/                 # React 18 + Vite + Tailwind CSS SPA
    ├── Dockerfile
    ├── nginx.conf
    ├── package.json
    └── src/                  # Kode sumber antarmuka pengguna
```

---

## 🚀 Cara Menjalankan

### Cara 1: Menjalankan Secara Lokal (Paling Cepat & Ringan)

Sistem telah dikonfigurasi untuk langsung berjalan dengan SQLite asinkron tanpa konfigurasi rumit:

```bash
# 1. Jalankan script launcher
./start_local.sh
```

Akses aplikasi pada:
- **Web Frontend**: [http://localhost:3000](http://localhost:3000)
- **API Swagger Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Health Check**: [http://localhost:8000/api/health](http://localhost:8000/api/health)

Pada saat pertama kali dibuka, sistem akan meminta Anda membuat 4–8 digit PIN untuk mengunci instance lokal Anda.

---

### Cara 2: Menjalankan Menggunakan Docker Compose (MySQL 8.0)

Jika ingin menjalankan seluruh stack (Database MySQL 8.0 + Backend FastAPI + Frontend Nginx) dalam container:

```bash
# 1. Ubah DATABASE_URL pada .env menjadi MySQL
# DATABASE_URL=mysql+asyncmy://autoshorts:autoshorts_secure_password@db-mysql:3306/autoshorts

# 2. Jalankan container
docker compose up -d
```

---

## 🧪 Hasil Pengujian (Automated Testing)

Seluruh pengujian unit dan integrasi telah lulus 100%:

```bash
PYTHONPATH=backend python3 -m pytest backend/tests -v
```

Hasil pengujian:
```text
backend/tests/test_api.py::test_health_endpoint PASSED                   [ 12%]
backend/tests/test_api.py::test_auth_flow PASSED                         [ 25%]
backend/tests/test_api.py::test_tts_endpoints PASSED                     [ 37%]
backend/tests/test_pipeline.py::test_full_pipeline_flow PASSED           [ 50%]
backend/tests/test_security.py::test_hex_to_ass_color_conversion PASSED  [ 62%]
backend/tests/test_security.py::test_argon2id_pin_hashing PASSED         [ 75%]
backend/tests/test_security.py::test_jwt_access_token PASSED             [ 87%]
backend/tests/test_security.py::test_aes_gcm_encryption PASSED           [100%]

============================== 8 passed in 4.09s ===============================
```
