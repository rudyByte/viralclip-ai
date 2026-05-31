# ViralClip AI — Phase 4 Setup & Testing Guide

## What Phase 4 Added

| Feature | Detail |
|---------|--------|
| **Persistent Queue Worker** | Background loop in `main.py` polls the DB every 3s and launches jobs up to the concurrency limit |
| **Batch URL Import** | Paste multiple YouTube URLs (comma or newline-separated) in the Create page to queue them all in one click |
| **Queue Position Badge** | Dashboard shows each queued job's position (Pos #1, #2…) in the pending queue |
| **DB-based Status Guard** | `DELETE /api/video/{id}` now checks live DB status instead of an in-memory set |

---

## Prerequisites

### Backend dependencies
```bash
cd backend
pip install -r requirements.txt
```

### Environment file
```bash
cp .env.example .env
# Then open .env and fill in:
# GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxx
```

> You can get a **free** Groq API key at https://console.groq.com

---

## Starting the Application (Local Dev)

### 1. Start the Backend
```bash
cd backend
uvicorn main:app --reload --port 8000
```

Expected startup logs:
```
INFO  ViralClip AI starting up...
INFO  Database initialized
INFO  Persistent queue worker loop started.
INFO  Uvicorn running on http://0.0.0.0:8000
```

### 2. Start the Frontend
Open a second terminal:
```bash
cd frontend
npm run dev
```

Open **http://localhost:3000** in your browser.

---

## Testing Phase 4 Features

### Test 1 — Single URL Processing
1. Click **Create New Short** on the Dashboard.
2. Paste one YouTube URL: `https://www.youtube.com/watch?v=dQw4w9WgXcQ`
3. Keep default settings and click **Generate Clips**.
4. ✅ You should be redirected to `/results/<job_id>` and see the progress terminal updating.

### Test 2 — Batch URL Processing
1. Click **Create New Short**.
2. In the URL textarea, paste **3 URLs** on separate lines:
   ```
   https://www.youtube.com/watch?v=URL1
   https://www.youtube.com/watch?v=URL2
   https://www.youtube.com/watch?v=URL3
   ```
3. Click **Generate Clips**.
4. ✅ Toast should say "Successfully queued 3 video clip jobs." and redirect to the first job.
5. ✅ Navigate to Dashboard — all 3 jobs should show with **Queued (Pos #1 / #2 / #3)** badges.
6. ✅ After ~3s, the queue worker picks up Job #1 and starts processing. The status badge updates to the active step.

### Test 3 — Queue Ordering
1. Queue 3 videos while none are processing.
2. ✅ The backend worker should process them strictly in submission order (oldest first).

### Test 4 — Concurrency Limit
1. Set `MAX_CONCURRENT_JOBS=1` in your `.env` (default).
2. Queue 3 jobs.
3. ✅ Only 1 job should transition to `downloading` at a time. The other 2 remain `queued`.

### Test 5 — Delete Queued Job
1. Queue a job.
2. Before it starts, click the 🗑️ Trash button on the Dashboard.
3. ✅ Job should be deleted cleanly.
4. Try deleting an **actively running** job — ✅ should get a `409` error.

### Test 6 — API Health Check
```bash
curl http://localhost:8000/health
```
Expected response:
```json
{"status": "ok", "app": "ViralClip AI", "version": "1.0.0", "groq_configured": true, ...}
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `GROQ_API_KEY not set` | Add key to `backend/.env` and restart uvicorn |
| `faster-whisper` model slow first run | Model downloads to `models/` on first use, subsequent runs are cached |
| `ffmpeg not found` | Install FFmpeg and ensure it's on system PATH |
| Port 8000 already in use | Change `APP_PORT` in `.env` or kill the existing process |
