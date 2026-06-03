"""
ViralClip AI — Settings API
POST /api/settings/cookies  — save YouTube cookies to server
GET  /api/settings/cookies  — check if cookies are saved
DELETE /api/settings/cookies — remove saved cookies
"""
from fastapi import APIRouter
from pydantic import BaseModel
from pathlib import Path
import os

router = APIRouter(prefix="/api/settings", tags=["settings"])

COOKIES_PATH = Path(os.environ.get("YT_DLP_COOKIES_FILE", "/app/data/cookies.txt"))


class CookiesPayload(BaseModel):
    cookies: str


@router.get("/cookies")
def get_cookies_status():
    exists = COOKIES_PATH.exists() and COOKIES_PATH.stat().st_size > 100
    return {"saved": exists, "path": str(COOKIES_PATH) if exists else None}


@router.post("/cookies")
def save_cookies(payload: CookiesPayload):
    if not payload.cookies or len(payload.cookies.strip()) < 50:
        return {"success": False, "error": "Cookies text too short or empty"}
    try:
        COOKIES_PATH.parent.mkdir(parents=True, exist_ok=True)
        COOKIES_PATH.write_text(payload.cookies.strip(), encoding="utf-8")
        return {"success": True, "message": "Cookies saved. All future jobs will use them automatically."}
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.delete("/cookies")
def delete_cookies():
    try:
        if COOKIES_PATH.exists():
            COOKIES_PATH.unlink()
        return {"success": True, "message": "Cookies deleted."}
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/logs")
def get_logs():
    log_file = "/app/data/backend.log"
    if os.path.exists(log_file):
        try:
            with open(log_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
            return {"success": True, "logs": "".join(lines[-300:])}
        except Exception as e:
            return {"success": False, "error": str(e)}
    return {"success": False, "error": f"Log file not found at {log_file}"}


@router.get("/test-curl-cffi")
def test_curl_cffi():
    try:
        import curl_cffi
        from curl_cffi import requests as c_requests
        r = c_requests.get("https://www.youtube.com", impersonate="chrome")
        
        import yt_dlp
        targets = []
        available_targets = []
        
        try:
            # List all targets in yt-dlp network module
            from yt_dlp.networking.impersonate import IMPERSONATE_TARGETS
            targets = list(IMPERSONATE_TARGETS.keys())
            
            # Check availability of specific browsers
            from yt_dlp.networking.impersonate import get_impersonate_target
            for t in ["chrome", "firefox", "safari", "edge"]:
                try:
                    if get_impersonate_target(t) is not None:
                        available_targets.append(t)
                except Exception as ex:
                    available_targets.append(f"{t}: Error({ex})")
        except Exception as e:
            targets = [f"Import error: {e}"]
            
        return {
            "success": True, 
            "message": "curl_cffi loaded and executed successfully", 
            "status_code": r.status_code,
            "curl_cffi_version": getattr(curl_cffi, "__version__", "unknown"),
            "yt_dlp_version": yt_dlp.__version__,
            "targets": targets,
            "available_targets": available_targets
        }
    except Exception as e:
        import traceback
        return {
            "success": False, 
            "error": str(e), 
            "traceback": traceback.format_exc()
        }
