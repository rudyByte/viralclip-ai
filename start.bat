@echo off
SETLOCAL EnableDelayedExpansion

echo ========================================================
echo          🎬 Starting ViralClip AI Orchestrator 🎬        
echo ========================================================
echo.

:: Verify Docker is active
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Docker is not running or not installed!
    echo Please make sure Docker Desktop is open and active before running this command.
    echo.
    pause
    exit /b 1
)

:: Prepare environment variables file if missing
if not exist "backend\.env" (
    echo [INFO] backend/.env file not found. Copying from backend/.env.example...
    copy "backend\.env.example" "backend\.env" >nul
    echo [WARNING] A new backend/.env file has been created.
    echo.
    echo Please open "backend/.env" in your editor and insert your GROQ_API_KEY.
    echo without a valid GROQ_API_KEY, video transcription and clips generation will fail.
    echo.
)

:: Start the multi-container stack
echo [INFO] Building and starting services with Docker Compose...
echo.
docker-compose up --build

ENDLOCAL
