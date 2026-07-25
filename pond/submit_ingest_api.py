from __future__ import annotations

import json
import logging
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field


LOGGER = logging.getLogger("pond.submit_ingest_api")

DEFAULT_DB_PATH = Path(__file__).resolve().parents[1] / "data" / "submissions.sqlite"
DB_PATH = Path(os.environ.get("POND_SUBMISSION_DB", str(DEFAULT_DB_PATH))).expanduser()
SHARED_SECRET = os.environ.get("POND_INGEST_SHARED_SECRET", "")

app = FastAPI(title="Pond Submit Ingest API")


class IngestPayload(BaseModel):
    submission_id: str = Field(..., alias="submissionId")
    submission_type: str = Field(..., alias="submissionType")
    value: str
    note: str | None = None
    nickname: str | None = None
    source_host: str | None = Field(default=None, alias="sourceHost")
    submitted_at: str | None = Field(default=None, alias="submittedAt")


def now_iso_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def payload_to_json(payload: IngestPayload) -> str:
    try:
        body = payload.model_dump(by_alias=True)
    except AttributeError:
        body = payload.dict(by_alias=True)
    return json.dumps(body, ensure_ascii=False)


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_schema() -> None:
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                submission_id TEXT NOT NULL UNIQUE,
                submission_type TEXT NOT NULL,
                value TEXT NOT NULL,
                note TEXT,
                nickname TEXT,
                source_host TEXT,
                submitted_at TEXT,
                received_at TEXT NOT NULL,
                raw_payload TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_submissions_received_at
            ON submissions(received_at)
            """
        )


@app.on_event("startup")
def on_startup() -> None:
    init_schema()
    LOGGER.info("submit_ingest_api startup db_path=%s", DB_PATH)


@app.get("/internal-api/health")
def internal_api_health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/health")
def api_health() -> dict[str, str]:
    return {"status": "ok"}


def validate_secret(header_secret: str | None) -> None:
    if not SHARED_SECRET:
        LOGGER.error("POND_INGEST_SHARED_SECRET is not configured")
        raise HTTPException(status_code=500, detail="Server ingest secret is not configured")

    if not header_secret:
        raise HTTPException(status_code=401, detail="Missing ingest secret")

    if header_secret != SHARED_SECRET:
        raise HTTPException(status_code=403, detail="Invalid ingest secret")


@app.post("/internal-api/ingest")
def post_internal_ingest(
    payload: IngestPayload,
    x_pond_secret: str | None = Header(default=None, alias="X-Pond-Secret"),
) -> JSONResponse:
    validate_secret(x_pond_secret)

    received_at = now_iso_utc()

    record: dict[str, Any] = {
        "submission_id": payload.submission_id,
        "submission_type": payload.submission_type,
        "value": payload.value,
        "note": payload.note,
        "nickname": payload.nickname,
        "source_host": payload.source_host,
        "submitted_at": payload.submitted_at,
        "received_at": received_at,
        "raw_payload": payload_to_json(payload),
    }

    with get_connection() as conn:
        try:
            cur = conn.execute(
                """
                INSERT INTO submissions (
                    submission_id,
                    submission_type,
                    value,
                    note,
                    nickname,
                    source_host,
                    submitted_at,
                    received_at,
                    raw_payload
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record["submission_id"],
                    record["submission_type"],
                    record["value"],
                    record["note"],
                    record["nickname"],
                    record["source_host"],
                    record["submitted_at"],
                    record["received_at"],
                    record["raw_payload"],
                ),
            )
            row_id = cur.lastrowid
            LOGGER.info(
                "ingest accepted submission_id=%s row_id=%s",
                record["submission_id"],
                row_id,
            )
            return JSONResponse(
                {
                    "ok": True,
                    "duplicate": False,
                    "submissionId": record["submission_id"],
                    "receivedAt": record["received_at"],
                    "id": row_id,
                }
            )
        except sqlite3.IntegrityError:
            existing = conn.execute(
                "SELECT id, received_at FROM submissions WHERE submission_id = ?",
                (record["submission_id"],),
            ).fetchone()
            LOGGER.info(
                "ingest duplicate submission_id=%s existing_id=%s",
                record["submission_id"],
                existing["id"] if existing else None,
            )
            return JSONResponse(
                {
                    "ok": True,
                    "duplicate": True,
                    "submissionId": record["submission_id"],
                    "receivedAt": existing["received_at"] if existing else received_at,
                    "id": existing["id"] if existing else None,
                }
            )


@app.post("/api/ingest")
def post_api_ingest(
    payload: IngestPayload,
    x_pond_secret: str | None = Header(default=None, alias="X-Pond-Secret"),
) -> JSONResponse:
    # Keep an alias endpoint for local/internal testing convenience.
    return post_internal_ingest(payload, x_pond_secret)
