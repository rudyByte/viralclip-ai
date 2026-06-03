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


@router.get("/test-impersonate")
def test_impersonate():
    try:
        import yt_dlp
        import yt_dlp.networking.impersonate as imp_mod
        
        # Subclasses
        subclasses = []
        try:
            import yt_dlp.networking._curlcffi as curl_mod
            subclasses = [cls.__name__ for cls in imp_mod.ImpersonateRequestHandler.__subclasses__()]
            supported = list(getattr(curl_mod.CurlCFFIRH, "_SUPPORTED_IMPERSONATE_TARGET_MAP", {}).keys())
        except Exception as e:
            subclasses = ["error: " + str(e)]
            supported = []
            
        import curl_cffi
        return {
            "success": True,
            "subclasses": subclasses,
            "supported_targets": [str(t) for t in supported],
            "curl_cffi_version": getattr(curl_cffi, "__version__", None),
            "yt_dlp_version": getattr(yt_dlp.version, "__version__", None)
        }
    except Exception as e:
        import traceback
        return {"success": False, "error": str(e), "traceback": traceback.format_exc()}
