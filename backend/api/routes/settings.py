"""
ViralClip AI — Settings API
POST /api/settings/cookies  — save YouTube cookies to server
GET  /api/settings/cookies  — check if cookies are saved
DELETE /api/settings/cookies — remove saved cookies
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from pathlib import Path
import os

router = APIRouter(prefix="/api/settings", tags=["settings"])

# Resolve persistent storage paths:
#   HF Spaces: /data/ is persistent across restarts (but /app/data/ is ephemeral)
#   Docker:    /app/data/ or ./data/ are used
#   Local:     ./data/ or ./cookies.txt in working dir
_HF_PERSISTENT = "/data/cookies.txt"
_HF_EPHEMERAL = "/app/data/cookies.txt"
_YT_DLP_ENV_VAR = os.environ.get("YT_DLP_COOKIES_FILE", "")

# Choose path: prefer env var > HF persistent > HF ephemeral
COOKIES_PATH = Path(
    _YT_DLP_ENV_VAR if _YT_DLP_ENV_VAR else
    (_HF_PERSISTENT if os.path.isdir("/data") else _HF_EPHEMERAL)
)

_PO_ENV_VAR = os.environ.get("YT_DLP_PO_TOKEN_FILE", "")
PO_TOKEN_PATH = Path(
    _PO_ENV_VAR if _PO_ENV_VAR else
    ("/data/po_token.txt" if os.path.isdir("/data") else "/app/data/po_token.txt")
)


class CookiesPayload(BaseModel):
    cookies: str


class PoTokenPayload(BaseModel):
    po_token: str


@router.get("/cookies")
def get_cookies_status():
    exists = COOKIES_PATH.exists() and COOKIES_PATH.stat().st_size > 100
    return {
        "saved": exists,
        "source": "user" if exists else None,
        "size_bytes": COOKIES_PATH.stat().st_size if exists else 0,
    }


@router.post("/cookies")
def save_cookies(payload: CookiesPayload):
    cookies_text = (payload.cookies or "").strip()
    if len(cookies_text) < 50 or ("# Netscape" not in cookies_text and ".youtube.com" not in cookies_text):
        raise HTTPException(status_code=400, detail="Invalid cookies format. Paste Netscape cookies.txt content.")
    try:
        COOKIES_PATH.parent.mkdir(parents=True, exist_ok=True)
        COOKIES_PATH.write_text(cookies_text, encoding="utf-8")
        return {"success": True, "saved": True, "message": "Cookies saved. All future jobs will use them automatically."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/cookies")
def delete_cookies():
    try:
        if COOKIES_PATH.exists():
            COOKIES_PATH.unlink()
        return {"success": True, "deleted": True, "message": "Cookies deleted."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/potoken")
def get_po_token_status():
    exists = PO_TOKEN_PATH.exists() and PO_TOKEN_PATH.stat().st_size > 20
    return {
        "saved": exists,
        "source": "user" if exists else None,
        "size_bytes": PO_TOKEN_PATH.stat().st_size if exists else 0,
    }


@router.post("/potoken")
def save_po_token(payload: PoTokenPayload):
    po_token = (payload.po_token or "").strip()
    if len(po_token) < 20:
        raise HTTPException(status_code=400, detail="Invalid PO Token. Paste the full token value.")
    try:
        PO_TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
        PO_TOKEN_PATH.write_text(po_token, encoding="utf-8")
        return {"success": True, "saved": True, "message": "PO Token saved. YouTube downloads will use it automatically."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/potoken")
def delete_po_token():
    try:
        if PO_TOKEN_PATH.exists():
            PO_TOKEN_PATH.unlink()
        return {"success": True, "deleted": True, "message": "PO Token deleted."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/groq-status")
def get_groq_status():
    """Returns whether Groq rate limit was hit recently and estimated reset."""
    import time
    from core.analyzer import LAST_GROQ_RATE_LIMIT
    if not LAST_GROQ_RATE_LIMIT:
        return {"rate_limited": False, "message": "Groq AI operational"}
    
    elapsed = time.time() - LAST_GROQ_RATE_LIMIT.get("timestamp", 0)
    # Consider rate limit active for 15 minutes after last occurrence unless reset
    if elapsed > 900:
        return {"rate_limited": False, "message": "Groq AI operational (previous rate limit expired)"}

    return {
        "rate_limited": True,
        "model": LAST_GROQ_RATE_LIMIT.get("model"),
        "reset_in": LAST_GROQ_RATE_LIMIT.get("reset_in", "a few minutes"),
        "error": LAST_GROQ_RATE_LIMIT.get("error"),
        "elapsed_seconds": int(elapsed),
        "message": f"Groq AI Rate Limit Active ({LAST_GROQ_RATE_LIMIT.get('model')}). Fallback visual engine automatically engaged. Resets in {LAST_GROQ_RATE_LIMIT.get('reset_in', 'a few minutes')}."
    }


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
