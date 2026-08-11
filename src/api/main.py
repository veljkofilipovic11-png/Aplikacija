from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from config import settings
from src.api.auth import create_token, require_auth, verify_password
from src.pipeline import run_pipeline
from src.storage import db

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).resolve().parent.parent.parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    if not settings.DASHBOARD_PASSWORD or not settings.DASHBOARD_SECRET_KEY:
        logger.warning(
            "DASHBOARD_PASSWORD i/ili DASHBOARD_SECRET_KEY nisu podeseni u .env - "
            "prijava na dashboard ce biti odbijena dok se ne podese."
        )
    yield


app = FastAPI(title="Furnicom Procurement Tracker", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


class LoginRequest(BaseModel):
    password: str


@app.post("/api/login")
def login(body: LoginRequest):
    if not verify_password(body.password):
        raise HTTPException(status_code=401, detail="Pogresna lozinka")
    return {"token": create_token()}


@app.get("/api/tenders", dependencies=[Depends(require_auth)])
def api_list_tenders(min_score: int | None = None, limit: int = 100):
    return db.list_tenders(limit=limit, min_score=min_score)


@app.get("/api/tenders/{tender_id}", dependencies=[Depends(require_auth)])
def api_get_tender(tender_id: str):
    tender = db.get_tender(tender_id)
    if not tender:
        raise HTTPException(status_code=404, detail="Tender nije pronadjen")
    return tender


class SettingsUpdate(BaseModel):
    cpv_codes: dict[str, str] | None = None
    relevance_threshold: int | None = None
    paused: bool | None = None


@app.get("/api/settings", dependencies=[Depends(require_auth)])
def api_get_settings():
    return db.get_app_settings()


@app.put("/api/settings", dependencies=[Depends(require_auth)])
def api_update_settings(body: SettingsUpdate):
    db.update_app_settings(
        cpv_codes=body.cpv_codes,
        relevance_threshold=body.relevance_threshold,
        paused=body.paused,
    )
    return db.get_app_settings()


@app.get("/api/status", dependencies=[Depends(require_auth)])
def api_status():
    return {
        "last_run": db.get_last_run(),
        "is_running": db.is_run_in_progress(),
        "tender_count": db.count_tenders(),
    }


def _run_pipeline_job() -> None:
    try:
        run_pipeline()
    except Exception:
        logger.exception("Pokretanje pretrage iz dashboard-a nije uspelo")


@app.post("/api/run", dependencies=[Depends(require_auth)])
def api_trigger_run(background_tasks: BackgroundTasks):
    if db.is_run_in_progress():
        raise HTTPException(status_code=409, detail="Pretraga je vec u toku")
    background_tasks.add_task(_run_pipeline_job)
    return {"started": True}
