#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

echo "========================================================"
echo "         🎬 Starting ViralClip AI Orchestrator 🎬        "
echo "========================================================"
echo

# Verify Docker is active
if ! docker info >/dev/null 2>&1; then
    echo "[ERROR] Docker is not running or not installed!"
    echo "Please make sure Docker Desktop is open and active before running this command."
    echo
    exit 1
fi

# Prepare environment variables file if missing
if [ ! -f "backend/.env" ]; then
    echo "[INFO] backend/.env file not found. Copying from backend/.env.example..."
    cp backend/.env.example backend/.env
    echo "[WARNING] A new backend/.env file has been created."
    echo "Please open 'backend/.env' in your editor and insert your GROQ_API_KEY."
    echo "Without a valid GROQ_API_KEY, video transcription and clips generation will fail."
    echo
fi

# Start the multi-container stack
echo "[INFO] Building and starting services with Docker Compose..."
echo
docker-compose up --build
