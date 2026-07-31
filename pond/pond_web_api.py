from __future__ import annotations

import csv
import hashlib
import hmac
import json
import os
import re
import secrets
import smtplib
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Query, Request
from pydantic import BaseModel
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles


REPO_ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = REPO_ROOT / "www-root"
USER_UPDATES_DIR = REPO_ROOT / "user-updates"
MEMBERMOJO_DIR = REPO_ROOT / "membermojo"
LOG_DIR = REPO_ROOT / "logs"
AUTH_DB_PATH = REPO_ROOT / "user-data" / "auth.sqlite"
LEGACY_AUTH_DB_PATH = REPO_ROOT / "data" / "auth.sqlite"
EMAIL_OUTBOX_PATH = LOG_DIR / "auth-email-outbox.log"
PUBLIC_BASE_URL = os.getenv("POND_PUBLIC_BASE_URL", "https://ponds.nsupdate.info").rstrip("/")
EMAIL_PASSWORD_FILE = Path(
    os.getenv("POND_EMAIL_PASSWORD_FILE", str(REPO_ROOT / "keys" / "gmail-hmpa-membership.txt"))
)
EMAIL_SMTP_HOST = os.getenv("POND_EMAIL_SMTP_HOST", "smtp.gmail.com")
EMAIL_SMTP_PORT = int(os.getenv("POND_EMAIL_SMTP_PORT", "587"))
EMAIL_SMTP_USERNAME = os.getenv("POND_EMAIL_SMTP_USERNAME", "hmpa.membership@gmail.com")
EMAIL_FROM_ADDRESS = os.getenv("POND_EMAIL_FROM", EMAIL_SMTP_USERNAME)

PASSWORD_ITERATIONS = 200_000
SESSION_TTL_SECONDS = 30 * 24 * 60 * 60
VERIFY_TTL_SECONDS = 24 * 60 * 60
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class RegisterEmailRequest(BaseModel):
    email: str
    password: str
    nickname: str | None = None


class RegisterNicknameRequest(BaseModel):
    nickname: str
    password: str
    isTestUser: bool = False


class LoginRequest(BaseModel):
    username: str
    password: str


class AddEmailRequest(BaseModel):
    authToken: str
    email: str


class UpdatePreferencesRequest(BaseModel):
    authToken: str
    showNicknameOnCharts: bool


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    return utc_now().isoformat()


def resolve_auth_db_path() -> Path:
    if AUTH_DB_PATH.exists() or not LEGACY_AUTH_DB_PATH.exists():
        return AUTH_DB_PATH

    AUTH_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    LEGACY_AUTH_DB_PATH.replace(AUTH_DB_PATH)
    return AUTH_DB_PATH


@contextmanager
def get_db() -> Any:
    db_path = resolve_auth_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_auth_db() -> None:
    with get_db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                nickname TEXT,
                email TEXT,
                email_verified INTEGER NOT NULL DEFAULT 0,
                is_member INTEGER NOT NULL DEFAULT 0,
                show_nickname_on_charts INTEGER NOT NULL DEFAULT 0,
                is_test_user INTEGER NOT NULL DEFAULT 0,
                member_checked_at TEXT,
                password_salt TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE UNIQUE INDEX IF NOT EXISTS idx_users_lower_nickname
            ON users (lower(nickname));

            CREATE UNIQUE INDEX IF NOT EXISTS idx_users_lower_email
            ON users (lower(email));

            CREATE TABLE IF NOT EXISTS auth_sessions (
                token TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id)
            );

            CREATE INDEX IF NOT EXISTS idx_auth_sessions_user_id
            ON auth_sessions (user_id);

            CREATE TABLE IF NOT EXISTS email_verification_tokens (
                token TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                email TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                used_at TEXT,
                FOREIGN KEY(user_id) REFERENCES users(id)
            );
            """
        )

        user_columns = {
            str(row["name"])
            for row in conn.execute("PRAGMA table_info(users)").fetchall()
        }
        if "show_nickname_on_charts" not in user_columns:
            conn.execute(
                "ALTER TABLE users ADD COLUMN show_nickname_on_charts INTEGER NOT NULL DEFAULT 0"
            )
        if "is_test_user" not in user_columns:
            conn.execute(
                "ALTER TABLE users ADD COLUMN is_test_user INTEGER NOT NULL DEFAULT 0"
            )


def normalize_email(value: str) -> str:
    return value.strip().lower()


def normalize_username(value: str) -> str:
    return value.strip().lower()


def normalize_nickname(value: str) -> str:
    return value.strip()


def validate_email_or_400(value: str) -> str:
    email = normalize_email(value)
    if not EMAIL_RE.match(email):
        raise HTTPException(status_code=400, detail="Invalid email address")
    return email


def validate_password_or_400(password: str) -> None:
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")


def validate_nickname_or_400(nickname: str) -> str:
    cleaned = normalize_nickname(nickname)
    if len(cleaned) < 3:
        raise HTTPException(status_code=400, detail="Nickname must be at least 3 characters")
    return cleaned


def hash_password(password: str, salt_hex: str | None = None) -> tuple[str, str]:
    salt = bytes.fromhex(salt_hex) if salt_hex else secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PASSWORD_ITERATIONS,
    )
    return salt.hex(), digest.hex()


def verify_password(password: str, salt_hex: str, digest_hex: str) -> bool:
    _, actual_digest_hex = hash_password(password, salt_hex=salt_hex)
    return hmac.compare_digest(actual_digest_hex, digest_hex)


def latest_membermojo_file() -> Path | None:
    files = sorted(MEMBERMOJO_DIR.glob("membermojo-*.csv"), key=lambda p: p.stat().st_mtime)
    return files[-1] if files else None


def load_membermojo_emails() -> tuple[set[str], str | None]:
    csv_path = latest_membermojo_file()
    if csv_path is None:
        return set(), None

    emails: set[str] = set()
    with csv_path.open("r", encoding="utf-8", errors="replace", newline="") as fp:
        reader = csv.DictReader(fp)
        for row in reader:
            email_value = None
            for key in ("Email", "email", "Email address", "email address"):
                if key in row and row[key]:
                    email_value = row[key]
                    break
            if email_value:
                emails.add(normalize_email(email_value))
    return emails, csv_path.name


def is_member_email(email: str) -> tuple[bool, str | None]:
    member_emails, filename = load_membermojo_emails()
    return normalize_email(email) in member_emails, filename


def write_email_outbox(email: str, subject: str, body: str) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    stamp = utc_now_iso()
    with EMAIL_OUTBOX_PATH.open("a", encoding="utf-8") as fp:
        fp.write(f"[{stamp}] TO={email} SUBJECT={subject}\n")
        fp.write(body.strip() + "\n\n")


def email_delivery_enabled() -> bool:
    raw_enabled = os.getenv("POND_EMAIL_ENABLED")
    if raw_enabled is None:
        return EMAIL_PASSWORD_FILE.exists()
    return raw_enabled.strip().lower() in {"1", "true", "yes", "on"}


def load_email_password() -> str | None:
    try:
        password = EMAIL_PASSWORD_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return password or None


def send_email_via_smtp(email: str, subject: str, body: str, password: str) -> None:
    msg = EmailMessage()
    msg["From"] = EMAIL_FROM_ADDRESS
    msg["To"] = email
    msg["Subject"] = subject
    msg.set_content(body)

    with smtplib.SMTP(EMAIL_SMTP_HOST, EMAIL_SMTP_PORT, timeout=20) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.ehlo()
        smtp.login(EMAIL_SMTP_USERNAME, password)
        smtp.send_message(msg)


def deliver_email(email: str, subject: str, body: str) -> None:
    email = (email or "").strip()
    if not email:
        return

    # Always keep an outbox copy for audit and troubleshooting.
    write_email_outbox(email=email, subject=subject, body=body)

    if not email_delivery_enabled():
        return

    password = load_email_password()
    if password is None:
        write_email_outbox(
            email=email,
            subject="SMTP delivery skipped",
            body=(
                "Email delivery is enabled but no app password was found.\n"
                f"Expected file: {EMAIL_PASSWORD_FILE}"
            ),
        )
        return

    try:
        send_email_via_smtp(email=email, subject=subject, body=body, password=password)
    except Exception as exc:
        # Keep user flows resilient; outbox retains the message for replay.
        write_email_outbox(
            email=email,
            subject="SMTP delivery failed",
            body=f"Error: {exc}",
        )


def create_verification_token(conn: sqlite3.Connection, user_id: int, email: str) -> str:
    token = secrets.token_urlsafe(32)
    created_at = utc_now()
    expires_at = datetime.fromtimestamp(created_at.timestamp() + VERIFY_TTL_SECONDS, tz=timezone.utc)
    conn.execute(
        """
        INSERT INTO email_verification_tokens (token, user_id, email, created_at, expires_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (token, user_id, normalize_email(email), created_at.isoformat(), expires_at.isoformat()),
    )
    return token


def issue_auth_session(conn: sqlite3.Connection, user_id: int) -> tuple[str, str]:
    token = secrets.token_urlsafe(32)
    created_at = utc_now()
    expires_at = datetime.fromtimestamp(created_at.timestamp() + SESSION_TTL_SECONDS, tz=timezone.utc)
    conn.execute(
        """
        INSERT INTO auth_sessions (token, user_id, created_at, expires_at)
        VALUES (?, ?, ?, ?)
        """,
        (token, user_id, created_at.isoformat(), expires_at.isoformat()),
    )
    return token, expires_at.isoformat()


def get_user_by_token(conn: sqlite3.Connection, auth_token: str) -> sqlite3.Row:
    row = conn.execute(
        """
        SELECT u.*
        FROM auth_sessions s
        JOIN users u ON u.id = s.user_id
        WHERE s.token = ?
        """,
        (auth_token,),
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=401, detail="Invalid auth token")

    session = conn.execute(
        "SELECT expires_at FROM auth_sessions WHERE token = ?",
        (auth_token,),
    ).fetchone()
    if session is None:
        raise HTTPException(status_code=401, detail="Invalid auth token")

    if datetime.fromisoformat(session["expires_at"]) < utc_now():
        conn.execute("DELETE FROM auth_sessions WHERE token = ?", (auth_token,))
        raise HTTPException(status_code=401, detail="Auth token expired")
    return row


def request_public_base_url(request: Request | None) -> str:
    if request is None:
        return PUBLIC_BASE_URL

    origin = request.headers.get("origin", "").strip()
    if origin:
        parsed = urlsplit(origin)
        if parsed.scheme in {"http", "https"} and parsed.netloc:
            return f"{parsed.scheme}://{parsed.netloc}"

    forwarded_proto = request.headers.get("x-forwarded-proto", "").split(",")[0].strip().lower()
    forwarded_host = request.headers.get("x-forwarded-host", "").split(",")[0].strip()
    host = forwarded_host or request.headers.get("host", "").strip()

    if host and forwarded_proto in {"http", "https"}:
        return f"{forwarded_proto}://{host}"

    if host:
        scheme = request.url.scheme if request.url.scheme in {"http", "https"} else "https"
        return f"{scheme}://{host}"

    return PUBLIC_BASE_URL


def build_verification_link(token: str, request: Request | None = None) -> str:
    base_url = request_public_base_url(request)
    return f"{base_url}/auth-verify.html?token={token}"

app = FastAPI(title="Pond Dev Web API")


@app.on_event("startup")
def on_startup() -> None:
    init_auth_db()


@app.get("/api/health")
def api_health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/auth/register-email")
def register_email(payload: RegisterEmailRequest, request: Request = None) -> JSONResponse:
    email = validate_email_or_400(payload.email)
    validate_password_or_400(payload.password)
    nickname = validate_nickname_or_400(payload.nickname) if payload.nickname else None
    username = email

    with get_db() as conn:
        existing = conn.execute("SELECT id FROM users WHERE lower(username) = ?", (username,)).fetchone()
        if existing is not None:
            raise HTTPException(status_code=409, detail="Email already registered")

        if nickname:
            nick_conflict = conn.execute(
                "SELECT id FROM users WHERE lower(nickname) = lower(?)",
                (nickname,),
            ).fetchone()
            if nick_conflict is not None:
                raise HTTPException(status_code=409, detail="Nickname already in use")

        is_member, member_source_file = is_member_email(email)
        now_iso = utc_now_iso()
        salt_hex, digest_hex = hash_password(payload.password)
        cursor = conn.execute(
            """
            INSERT INTO users (
                username,
                nickname,
                email,
                email_verified,
                is_member,
                show_nickname_on_charts,
                is_test_user,
                member_checked_at,
                password_salt,
                password_hash,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, 0, ?, 0, 0, ?, ?, ?, ?, ?)
            """,
            (
                username,
                nickname,
                email,
                1 if is_member else 0,
                now_iso,
                salt_hex,
                digest_hex,
                now_iso,
                now_iso,
            ),
        )

        user_id = int(cursor.lastrowid)
        token = create_verification_token(conn, user_id=user_id, email=email)
        verification_link = build_verification_link(token, request=request)

    deliver_email(
        email=email,
        subject="Confirm your pond account",
        body=(
            "Welcome to pond status updates.\n\n"
            f"Please confirm your email by opening:\n{verification_link}\n\n"
            "If you did not request this account, you can ignore this message."
        ),
    )

    return JSONResponse(
        {
            "ok": True,
            "message": "Registration created. Check email for verification link.",
            "email": email,
            "isMember": is_member,
            "memberSource": member_source_file,
        }
    )


@app.post("/api/auth/register-nickname")
def register_nickname(payload: RegisterNicknameRequest) -> JSONResponse:
    nickname = validate_nickname_or_400(payload.nickname)
    validate_password_or_400(payload.password)
    username = normalize_username(nickname)

    with get_db() as conn:
        existing = conn.execute("SELECT id FROM users WHERE lower(username) = ?", (username,)).fetchone()
        if existing is not None:
            raise HTTPException(status_code=409, detail="Nickname already registered")

        nick_conflict = conn.execute(
            "SELECT id FROM users WHERE lower(nickname) = lower(?)",
            (nickname,),
        ).fetchone()
        if nick_conflict is not None:
            raise HTTPException(status_code=409, detail="Nickname already in use")

        now_iso = utc_now_iso()
        salt_hex, digest_hex = hash_password(payload.password)
        conn.execute(
            """
            INSERT INTO users (
                username,
                nickname,
                email,
                email_verified,
                is_member,
                show_nickname_on_charts,
                is_test_user,
                member_checked_at,
                password_salt,
                password_hash,
                created_at,
                updated_at
            ) VALUES (?, ?, NULL, 0, 0, 0, ?, ?, ?, ?, ?, ?)
            """,
            (
                username,
                nickname,
                1 if payload.isTestUser else 0,
                now_iso,
                salt_hex,
                digest_hex,
                now_iso,
                now_iso,
            ),
        )

    return JSONResponse({"ok": True, "message": "Nickname account created"})


@app.post("/api/auth/login")
def login(payload: LoginRequest) -> JSONResponse:
    username = normalize_username(payload.username)
    with get_db() as conn:
        user = conn.execute(
            """
            SELECT *
            FROM users
            WHERE lower(username) = ?
               OR lower(COALESCE(email, '')) = ?
               OR lower(COALESCE(nickname, '')) = ?
            LIMIT 1
            """,
            (username, username, username),
        ).fetchone()

        if user is None or not verify_password(payload.password, user["password_salt"], user["password_hash"]):
            raise HTTPException(status_code=401, detail="Invalid username or password")

        token, expires_at = issue_auth_session(conn, user_id=int(user["id"]))

    return JSONResponse(
        {
            "ok": True,
            "authToken": token,
            "expiresAt": expires_at,
            "user": {
                "username": user["username"],
                "nickname": user["nickname"],
                "email": user["email"],
                "emailVerified": bool(user["email_verified"]),
                "isMember": bool(user["is_member"]),
                "showNicknameOnCharts": bool(user["show_nickname_on_charts"]),
                "isTestUser": bool(user["is_test_user"]),
            },
        }
    )


@app.post("/api/auth/add-email")
def add_email(payload: AddEmailRequest, request: Request = None) -> JSONResponse:
    email = validate_email_or_400(payload.email)

    with get_db() as conn:
        user = get_user_by_token(conn, payload.authToken)

        existing = conn.execute(
            "SELECT id FROM users WHERE lower(email) = ? AND id != ?",
            (email, user["id"]),
        ).fetchone()
        if existing is not None:
            raise HTTPException(status_code=409, detail="Email already used by another account")

        is_member, member_source_file = is_member_email(email)
        now_iso = utc_now_iso()
        conn.execute(
            """
            UPDATE users
            SET email = ?,
                email_verified = 0,
                is_member = ?,
                member_checked_at = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (email, 1 if is_member else 0, now_iso, now_iso, user["id"]),
        )

        token = create_verification_token(conn, user_id=int(user["id"]), email=email)
        verification_link = build_verification_link(token, request=request)

    deliver_email(
        email=email,
        subject="Confirm your pond account email",
        body=(
            "Please confirm your email by opening:\n"
            f"{verification_link}\n\n"
            "If you did not request this change, ignore this message."
        ),
    )

    return JSONResponse(
        {
            "ok": True,
            "message": "Verification email queued",
            "isMember": is_member,
            "memberSource": member_source_file,
        }
    )


@app.get("/api/auth/verify-email")
def verify_email(token: str = Query(..., min_length=20)) -> JSONResponse:
    with get_db() as conn:
        row = conn.execute(
            """
            SELECT *
            FROM email_verification_tokens
            WHERE token = ?
            """,
            (token,),
        ).fetchone()

        if row is None:
            raise HTTPException(status_code=400, detail="Invalid verification token")

        if row["used_at"]:
            raise HTTPException(status_code=400, detail="Verification token already used")

        if datetime.fromisoformat(row["expires_at"]) < utc_now():
            raise HTTPException(status_code=400, detail="Verification token expired")

        now_iso = utc_now_iso()
        is_member, member_source_file = is_member_email(row["email"])
        conn.execute(
            """
            UPDATE users
            SET email = ?,
                email_verified = 1,
                is_member = ?,
                member_checked_at = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                normalize_email(row["email"]),
                1 if is_member else 0,
                now_iso,
                now_iso,
                row["user_id"],
            ),
        )
        conn.execute(
            "UPDATE email_verification_tokens SET used_at = ? WHERE token = ?",
            (now_iso, token),
        )

    return JSONResponse(
        {
            "ok": True,
            "message": "Email verified",
            "isMember": is_member,
            "memberSource": member_source_file,
        }
    )


@app.get("/api/auth/me")
def auth_me(authToken: str = Query(..., min_length=20)) -> JSONResponse:
    with get_db() as conn:
        user = get_user_by_token(conn, authToken)
        return JSONResponse(
            {
                "ok": True,
                "user": {
                    "username": user["username"],
                    "nickname": user["nickname"],
                    "email": user["email"],
                    "emailVerified": bool(user["email_verified"]),
                    "isMember": bool(user["is_member"]),
                    "showNicknameOnCharts": bool(user["show_nickname_on_charts"]),
                    "isTestUser": bool(user["is_test_user"]),
                    "memberCheckedAt": user["member_checked_at"],
                },
            }
        )


@app.post("/api/auth/preferences")
def auth_preferences(payload: UpdatePreferencesRequest) -> JSONResponse:
    with get_db() as conn:
        user = get_user_by_token(conn, payload.authToken)
        now_iso = utc_now_iso()
        conn.execute(
            """
            UPDATE users
            SET show_nickname_on_charts = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (1 if payload.showNicknameOnCharts else 0, now_iso, user["id"]),
        )

        refreshed = conn.execute(
            "SELECT * FROM users WHERE id = ?",
            (user["id"],),
        ).fetchone()

    if refreshed is None:
        raise HTTPException(status_code=500, detail="Could not load updated user")

    return JSONResponse(
        {
            "ok": True,
            "user": {
                "username": refreshed["username"],
                "nickname": refreshed["nickname"],
                "email": refreshed["email"],
                "emailVerified": bool(refreshed["email_verified"]),
                "isMember": bool(refreshed["is_member"]),
                "showNicknameOnCharts": bool(refreshed["show_nickname_on_charts"]),
                "isTestUser": bool(refreshed["is_test_user"]),
            },
        }
    )


@app.post("/api/pondupdate")
def post_pond_update(payload: dict[str, Any]) -> JSONResponse:
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Expected JSON object payload")

    payload_to_store = dict(payload)
    auth_token_value = payload_to_store.pop("authToken", None)

    authenticated_user: dict[str, Any] | None = None
    if isinstance(auth_token_value, str) and auth_token_value.strip():
        with get_db() as conn:
            try:
                user = get_user_by_token(conn, auth_token_value.strip())
                show_nickname = bool(user["show_nickname_on_charts"])
                authenticated_user = {
                    "userId": int(user["id"]),
                    "username": user["username"],
                    "nickname": user["nickname"] if show_nickname else None,
                    "showNicknameOnCharts": show_nickname,
                    "isTestUser": bool(user["is_test_user"]),
                    "emailVerified": bool(user["email_verified"]),
                    "isMember": bool(user["is_member"]),
                }
            except HTTPException:
                # Keep anonymous updates low-friction even if a stale token is present.
                authenticated_user = None

    now_utc = datetime.now(timezone.utc)
    now_iso = now_utc.isoformat()
    record_id = str(uuid.uuid4())
    record = {
        "id": record_id,
        "receivedAt": now_iso,
        "payload": payload_to_store,
    }
    if authenticated_user is not None:
        record["submittedBy"] = authenticated_user

    updates_jsonl = USER_UPDATES_DIR / f"user-updates-{now_utc:%y%m%d}.jsonl"
    USER_UPDATES_DIR.mkdir(parents=True, exist_ok=True)
    with updates_jsonl.open("a", encoding="utf-8") as fp:
        fp.write(json.dumps(record, ensure_ascii=False) + "\n")

    return JSONResponse(
        {
            "ok": True,
            "id": record_id,
            "receivedAt": now_iso,
            "authenticated": authenticated_user is not None,
            "submittedBy": authenticated_user,
        }
    )


if not STATIC_DIR.exists():
    raise RuntimeError(f"Static directory does not exist: {STATIC_DIR}")

# Mounted last so API routes under /api/* are matched first.
app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
