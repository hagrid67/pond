from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import pytest
from fastapi import HTTPException

from pond import dev_web_api as api


def _decode_json_response(response) -> dict[str, object]:
    return json.loads(response.body.decode("utf-8"))


@pytest.fixture
def auth_env(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    logs_dir = tmp_path / "logs"
    updates_dir = tmp_path / "user-updates"
    membermojo_dir = tmp_path / "membermojo"

    monkeypatch.setattr(api, "AUTH_DB_PATH", data_dir / "auth.sqlite")
    monkeypatch.setattr(api, "LOG_DIR", logs_dir)
    monkeypatch.setattr(api, "EMAIL_OUTBOX_PATH", logs_dir / "auth-email-outbox.log")
    monkeypatch.setattr(api, "USER_UPDATES_DIR", updates_dir)
    monkeypatch.setattr(api, "MEMBERMOJO_DIR", membermojo_dir)
    monkeypatch.setattr(api, "PUBLIC_BASE_URL", "https://ponds.nsupdate.info")

    api.init_auth_db()
    return {
        "data_dir": data_dir,
        "logs_dir": logs_dir,
        "updates_dir": updates_dir,
        "membermojo_dir": membermojo_dir,
    }


def test_register_nickname_and_login_issues_month_session(auth_env) -> None:
    api.register_nickname(api.RegisterNicknameRequest(nickname="alpha-user", password="demo-pass-123"))

    response = api.login(api.LoginRequest(username="alpha-user", password="demo-pass-123"))
    body = _decode_json_response(response)

    assert response.status_code == 200
    assert body["ok"] is True
    assert isinstance(body["authToken"], str)
    assert len(body["authToken"]) >= 20

    expires_at = datetime.fromisoformat(str(body["expiresAt"]))
    now = datetime.now(timezone.utc)
    ttl_seconds = (expires_at - now).total_seconds()
    assert 29 * 24 * 3600 <= ttl_seconds <= 31 * 24 * 3600


def test_login_rejects_wrong_password(auth_env) -> None:
    api.register_nickname(api.RegisterNicknameRequest(nickname="beta-user", password="demo-pass-123"))

    with pytest.raises(HTTPException) as exc:
        api.login(api.LoginRequest(username="beta-user", password="wrong-pass"))

    assert exc.value.status_code == 401


def test_register_email_marks_member_from_latest_membermojo_file(auth_env) -> None:
    membermojo_dir = auth_env["membermojo_dir"]
    membermojo_dir.mkdir(parents=True, exist_ok=True)

    older = membermojo_dir / "membermojo-260101.csv"
    older.write_text("Email\nold@example.org\n", encoding="utf-8")

    latest = membermojo_dir / "membermojo-260729.csv"
    latest.write_text("Email\nmember@example.org\n", encoding="utf-8")

    older_stat = older.stat()
    latest_stat = latest.stat()
    os.utime(older, (older_stat.st_atime, older_stat.st_mtime - 120))
    os.utime(latest, (latest_stat.st_atime, latest_stat.st_mtime + 120))

    response = api.register_email(
        api.RegisterEmailRequest(
            email="member@example.org",
            password="demo-pass-123",
            nickname="member-user",
        )
    )
    body = _decode_json_response(response)

    assert response.status_code == 200
    assert body["ok"] is True
    assert body["isMember"] is True
    assert body["memberSource"] == "membermojo-260729.csv"


def test_email_verification_flow_sets_verified_flag(auth_env) -> None:
    api.register_email(
        api.RegisterEmailRequest(
            email="verifyme@example.org",
            password="demo-pass-123",
            nickname="verify-user",
        )
    )

    with api.get_db() as conn:
        row = conn.execute(
            "SELECT token FROM email_verification_tokens ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        assert row is not None
        token = row["token"]

    verify_response = api.verify_email(token=token)
    verify_body = _decode_json_response(verify_response)
    assert verify_response.status_code == 200
    assert verify_body["ok"] is True

    login_response = api.login(api.LoginRequest(username="verifyme@example.org", password="demo-pass-123"))
    login_body = _decode_json_response(login_response)
    assert login_body["user"]["emailVerified"] is True


def test_submit_endpoint_accepts_authenticated_and_anonymous(auth_env) -> None:
    api.register_nickname(api.RegisterNicknameRequest(nickname="submit-user", password="demo-pass-123"))
    login_body = _decode_json_response(api.login(api.LoginRequest(username="submit-user", password="demo-pass-123")))

    auth_submit = api.post_pond_update(
        {
            "type": "pond-update",
            "authToken": login_body["authToken"],
            "queue": {"index": 2, "label": "5"},
        }
    )
    auth_body = _decode_json_response(auth_submit)
    assert auth_submit.status_code == 200
    assert auth_body["authenticated"] is True
    assert auth_body["submittedBy"]["username"] == "submit-user"

    anon_submit = api.post_pond_update(
        {
            "type": "pond-update",
            "queue": {"index": 1, "label": "no queue"},
        }
    )
    anon_body = _decode_json_response(anon_submit)
    assert anon_submit.status_code == 200
    assert anon_body["authenticated"] is False
    assert anon_body["submittedBy"] is None
