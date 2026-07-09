#!/bin/bash
# run_prototype.sh - Run B2B Matching Prototype Server

# Move to the script's directory
CWD="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$CWD"

echo "================================================================="
echo "🚀 B2B Matching Prototype Starter"
echo "================================================================="

# Path to the virtual environment of the DiscordBot
VENV_PATH="/Users/lenhatminh/Downloads/DiscordBot/.venv"

if [ -d "$VENV_PATH" ]; then
    echo "📦 Activating python virtual environment..."
    source "$VENV_PATH/bin/activate"
else
    echo "⚠️  Could not find virtualenv at $VENV_PATH"
    echo "Attempting to use system python3..."
fi

# Ensure FastAPI and Uvicorn are installed
echo "⚡ Checking dependencies (fastapi, uvicorn)..."
python3 -m pip install fastapi uvicorn

echo "🔥 Starting FastAPI + Uvicorn server on http://127.0.0.1:8000 ..."
python3 app.py
