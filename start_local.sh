#!/bin/bash
# ==============================================================
# AutoShorts Local - Launcher Script
# ==============================================================
set -e

echo "🚀 Memulai AutoShorts Local (Backend + Frontend)..."

# Ensure storage directories exist
mkdir -p storage/uploads storage/audio storage/transcripts storage/subtitles storage/thumbnails storage/exports storage/tts storage/credentials

# Check Python and Node
command -v python3 >/dev/null 2>&1 || { echo "❌ Python 3 tidak ditemukan!"; exit 1; }
command -v ffmpeg >/dev/null 2>&1 || { echo "❌ FFmpeg tidak ditemukan!"; exit 1; }
command -v npm >/dev/null 2>&1 || { echo "❌ npm tidak ditemukan!"; exit 1; }

# Trap to kill child processes on Ctrl+C or EXIT
trap 'kill $(jobs -p) 2>/dev/null || true' EXIT

# Automatically free ports 8000 and 3000 if occupied by old sessions
if lsof -ti :8000 >/dev/null 2>&1; then
  echo "⚠️ Port 8000 sedang aktif. Menghentikan proses lama..."
  kill -9 $(lsof -ti :8000) 2>/dev/null || true
  sleep 1
fi

if lsof -ti :3000 >/dev/null 2>&1; then
  echo "⚠️ Port 3000 sedang aktif. Menghentikan proses lama..."
  kill -9 $(lsof -ti :3000) 2>/dev/null || true
  sleep 1
fi

echo "🔹 Menjalankan Backend FastAPI pada http://localhost:8000..."
PYTHONPATH=backend python3 -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

echo "🔹 Menjalankan Frontend Vite pada http://localhost:3000..."
cd frontend
npm run dev -- --host 0.0.0.0 --port 3000 &
FRONTEND_PID=$!

cd ..

echo ""
echo "=============================================================="
echo "✨ AutoShorts Local siap digunakan!"
echo "👉 Buka Web UI: http://localhost:3000"
echo "👉 Dokumentasi API: http://localhost:8000/docs"
echo "👉 Health check: http://localhost:8000/api/health"
echo "=============================================================="
echo "Tekan Ctrl+C untuk menghentikan server."

wait
