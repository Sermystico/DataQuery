#!/bin/sh
set -e

echo "Starting DataQuery Backend Entrypoint..."
python scripts/init_db.py

echo "Launching Uvicorn ASGI Server..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
