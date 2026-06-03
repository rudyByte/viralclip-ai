---
title: ViralClip AI Backend
emoji: 🎬
colorFrom: indigo
colorTo: pink
sdk: docker
app_port: 7860
pinned: false
---

# ViralClip AI — Cloud Backend Service

This is the backend service for **ViralClip AI**, configured to run seamlessly as a free Hugging Face Space Docker container.

## Environment Variables Configuration

Make sure to set the following secrets in your Hugging Face Space Settings:
- `GROQ_API_KEY`: Your Groq Cloud API key.
- `GROQ_DETECTION_MODEL`: `llama-3.1-8b-instant` (default)
- `GROQ_HOOK_MODEL`: `llama-3.3-70b-versatile` (default)
