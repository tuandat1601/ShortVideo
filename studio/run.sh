#!/usr/bin/env bash
set -e
DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$DIR"
source long-tieng/.venv/bin/activate
echo "🚀 Shorts Studio chạy tại: http://127.0.0.1:8765"
uvicorn studio.api.main:app --host 127.0.0.1 --port 8765
