#!/bin/bash
set -e

echo "=== Installing Python dependencies ==="
pip install -r requirements.txt --quiet

echo "=== Building React frontend ==="
cd frontend
npm install --silent
npm run build
cd ..

echo "=== Starting News Aggregator ==="
uvicorn backend.main:app --host 0.0.0.0 --port 8000
