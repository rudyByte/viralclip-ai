# 🎬 ViralClip AI

> A modern, open-source alternative to OpusClip and Vidyo.ai. Automatically scrape, transcribe, analyze, and generate highly viral shorts/clips from long-form YouTube videos, powered by **FastAPI**, **React (Vite + Tailwind)**, **Groq**, and **Whisper**.

---

## 🌟 Key Features

- **Sequential DB-backed Queue Worker:** Robust background task queue in FastAPI polls the SQLite database every 3 seconds to execute transcription and clipping pipelines sequentially.
- **Batch Video Importing:** Process multiple long-form video URLs (YouTube, etc.) in a single batch submission.
- **Real-Time Progress Streaming:** Dashboard updates in real time using HTML5 WebSockets, with dynamic visual queue position badges showing exactly where a job is in the pipeline.
- **Automatic Hourly Housekeeping:** A built-in cleanup scheduler runs every hour inside the FastAPI background lifecycle to prune temporary files older than 24 hours.
- **High-Fidelity Captions:** Supports dynamic captions styles including **Hormozi**, **Gadzhi**, **Ali Abdaal**, and **MrBeast**.
- **Interactive Clips Generator:** Choose from trending gameplay backgrounds (GTA V, Subway Surfers, Minecraft, Temple Run) to boost viewer retention.
- **Production-Ready Docker Orchestration:** Multi-stage Nginx-served Vite build frontend paired with a streamlined FastAPI backend image.

---

## 🛠️ Technology Stack

- **Backend:** Python 3.11, FastAPI, SQLAlchemy, SQLite (via `aiosqlite`), `faster-whisper`, `yt-dlp`, OpenCV, MoviePy, and Uvicorn.
- **Frontend:** React, Vite, TailwindCSS, Framer Motion, Radix UI, Recharts, and Axios.
- **Web Server:** Production-optimized Nginx serving static assets and proxying API/WebSockets traffic to the backend container.
- **Deployment:** Docker & Docker Compose.

---

## 🚀 Quick Start (Dockerized)

Ensure you have [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed on your machine.

### 1. Configure Secrets
Create a `.env` file inside the `backend/` directory (or use `backend/.env.example` as a template) and add your Groq API key:
```env
GROQ_API_KEY=gsk_your_groq_api_key_here
```

### 2. Start the Multi-Container Application
From the project root directory, run:
```bash
docker-compose up --build -d
```

This will automatically:
1. Spin up the **FastAPI Backend** on port `8000`.
2. Build the **Vite React Frontend** and serve it via **Nginx** on port `3000`.
3. Set up named volumes for persistent database storage (`viralclip.db`), media exports, temp files, gameplay templates, and Whisper models.

### 3. Verify Services
- **Web Application:** Open [http://localhost:3000](http://localhost:3000) in your browser.
- **FastAPI API Documentation:** Access interactive Swagger docs at [http://localhost:8000/docs](http://localhost:8000/docs).
- **Backend Health Check:** Ping the health check endpoint at [http://localhost:8000/health](http://localhost:8000/health).

---

## 🏗️ Manual Local Setup (Alternative)

If you wish to run the services outside Docker for local development:

### Backend Setup
1. Navigate to `/backend`:
   ```bash
   cd backend
   ```
2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   # On Windows:
   .\venv\Scripts\activate
   # On Linux/macOS:
   source venv/bin/activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Start the FastAPI server:
   ```bash
   python main.py
   ```

### Frontend Setup
1. Navigate to `/frontend`:
   ```bash
   cd ../frontend
   ```
2. Install npm packages:
   ```bash
   npm install
   ```
3. Run the development server (runs on port `3000` with hot reload):
   ```bash
   npm run dev
   ```

---

## 🧹 Automated Housekeeping

No manual disk space management required! The application executes a background garbage collection loop every hour. 
Any generated temporary video tracks, audio extractions, or intermediary assets in the `temp/` folder older than **24 hours** are automatically purged.

---

## 📂 Repository Structure

```
viralclip-ai/
├── backend/                  # FastAPI Application
│   ├── api/                  # Routes (Clips, Videos, WebSocket streams)
│   ├── core/                 # AI & Video Editing Pipelines
│   ├── database.py           # SQLAlchemy & SQLite DB Definitions
│   ├── main.py               # Main Entrypoint & Background Tasks
│   ├── config.py             # Pydantic Settings management
│   ├── requirements.txt      # Python Dependencies
│   └── Dockerfile            # Optimized Backend Image Specification
│
├── frontend/                 # React Application
│   ├── src/                  # Component and State definitions
│   ├── nginx.conf            # Nginx Reverse Proxy routing
│   ├── vite.config.js        # Vite config & dev API proxier
│   └── Dockerfile            # Multi-stage production Nginx deployment
│
└── docker-compose.yml        # Multi-container service orchestrator
```

---

## 📝 License

This project is open-source and available under the [MIT License](LICENSE).
