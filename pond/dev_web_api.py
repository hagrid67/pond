from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles


REPO_ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = REPO_ROOT / "www-root"
USER_UPDATES_DIR = REPO_ROOT / "user-updates"

app = FastAPI(title="Pond Dev Web API")


@app.get("/api/health")
def api_health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/pondupdate")
def post_pond_update(payload: dict[str, Any]) -> JSONResponse:
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Expected JSON object payload")

    now_utc = datetime.now(timezone.utc)
    now_iso = now_utc.isoformat()
    record_id = str(uuid.uuid4())
    record = {
        "id": record_id,
        "receivedAt": now_iso,
        "payload": payload,
    }

    updates_jsonl = USER_UPDATES_DIR / f"user-updates-{now_utc:%y%m%d}.jsonl"
    USER_UPDATES_DIR.mkdir(parents=True, exist_ok=True)
    with updates_jsonl.open("a", encoding="utf-8") as fp:
        fp.write(json.dumps(record, ensure_ascii=False) + "\n")

    return JSONResponse(
        {
            "ok": True,
            "id": record_id,
            "receivedAt": now_iso,
        }
    )


if not STATIC_DIR.exists():
    raise RuntimeError(f"Static directory does not exist: {STATIC_DIR}")

# Mounted last so API routes under /api/* are matched first.
app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
