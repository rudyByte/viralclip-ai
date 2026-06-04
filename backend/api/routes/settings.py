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

COOKIES_PATH = Path(os.environ.get("YT_DLP_COOKIES_FILE", "/app/data/cookies.txt"))
PO_TOKEN_PATH = Path(os.environ.get("YT_DLP_PO_TOKEN_FILE", "/app/data/po_token.txt"))


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
