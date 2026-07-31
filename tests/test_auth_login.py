from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import pytest
from fastapi import HTTPException

from pond import pond_web_api as api


TEST_EMAIL = "farm.camera.tcl@gmail.com"


def _email_with_tag(base_email: str, tag: str) -> str:
    local_part, domain = base_email.split("@", 1)
    return f"{local_part}+{tag}@{domain}"


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
    monkeypatch.setattr(api, "PUBLIC_BASE_URL", "http://localhost:8000")

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
    assert body["user"]["showNicknameOnCharts"] is False
    assert body["user"]["isTestUser"] is False

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
    older.write_text(f"Email\n{_email_with_tag(TEST_EMAIL, 'old')}\n", encoding="utf-8")

    latest = membermojo_dir / "membermojo-260729.csv"
    latest.write_text(f"Email\n{TEST_EMAIL}\n", encoding="utf-8")

    older_stat = older.stat()
    latest_stat = latest.stat()
    os.utime(older, (older_stat.st_atime, older_stat.st_mtime - 120))
    os.utime(latest, (latest_stat.st_atime, latest_stat.st_mtime + 120))

    response = api.register_email(
        api.RegisterEmailRequest(
            email=TEST_EMAIL,
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
    verify_email = _email_with_tag(TEST_EMAIL, "verify")
    api.register_email(
        api.RegisterEmailRequest(
            email=verify_email,
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

    login_response = api.login(api.LoginRequest(username=verify_email, password="demo-pass-123"))
    login_body = _decode_json_response(login_response)
    assert login_body["user"]["emailVerified"] is True


def test_verified_nickname_account_can_login_with_email(auth_env) -> None:
    api.register_nickname(api.RegisterNicknameRequest(nickname="email-login-user", password="demo-pass-123"))

    nickname_login = _decode_json_response(
        api.login(api.LoginRequest(username="email-login-user", password="demo-pass-123"))
    )
    token = str(nickname_login["authToken"])

    login_email = _email_with_tag(TEST_EMAIL, "login")
    add_email_response = api.add_email(
        api.AddEmailRequest(authToken=token, email=login_email)
    )
    add_email_body = _decode_json_response(add_email_response)
    assert add_email_response.status_code == 200
    assert add_email_body["ok"] is True

    with api.get_db() as conn:
        row = conn.execute(
            "SELECT token FROM email_verification_tokens ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        assert row is not None

    verify_response = api.verify_email(token=row["token"])
    verify_body = _decode_json_response(verify_response)
    assert verify_response.status_code == 200
    assert verify_body["ok"] is True

    email_login_response = api.login(
        api.LoginRequest(username=login_email, password="demo-pass-123")
    )
    email_login_body = _decode_json_response(email_login_response)

    assert email_login_response.status_code == 200
    assert email_login_body["ok"] is True
    assert email_login_body["user"]["username"] == "email-login-user"
    assert email_login_body["user"]["nickname"] == "email-login-user"
    assert email_login_body["user"]["email"] == login_email
    assert email_login_body["user"]["emailVerified"] is True


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
    assert auth_body["submittedBy"]["nickname"] is None
    assert auth_body["submittedBy"]["showNicknameOnCharts"] is False
    assert auth_body["submittedBy"]["isTestUser"] is False

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


def test_preference_update_is_persisted_and_reflected_in_me_and_submission(auth_env) -> None:
    api.register_nickname(api.RegisterNicknameRequest(nickname="chart-user", password="demo-pass-123"))
    login_body = _decode_json_response(api.login(api.LoginRequest(username="chart-user", password="demo-pass-123")))

    token = str(login_body["authToken"])

    me_before = _decode_json_response(api.auth_me(authToken=token))
    assert me_before["user"]["showNicknameOnCharts"] is False
    assert me_before["user"]["isTestUser"] is False

    pref_response = api.auth_preferences(
        api.UpdatePreferencesRequest(authToken=token, showNicknameOnCharts=True)
    )
    pref_body = _decode_json_response(pref_response)
    assert pref_response.status_code == 200
    assert pref_body["ok"] is True
    assert pref_body["user"]["showNicknameOnCharts"] is True

    me_after = _decode_json_response(api.auth_me(authToken=token))
    assert me_after["user"]["showNicknameOnCharts"] is True
    assert me_after["user"]["isTestUser"] is False

    submit = api.post_pond_update(
        {
            "type": "pond-update",
            "authToken": token,
            "queue": {"index": 3, "label": "10"},
        }
    )
    submit_body = _decode_json_response(submit)
    assert submit.status_code == 200
    assert submit_body["authenticated"] is True
    assert submit_body["submittedBy"]["nickname"] == "chart-user"
    assert submit_body["submittedBy"]["showNicknameOnCharts"] is True
    assert submit_body["submittedBy"]["isTestUser"] is False


def test_register_test_user_sets_flag_and_submission_metadata(auth_env) -> None:
    api.register_nickname(
        api.RegisterNicknameRequest(
            nickname="joe-test",
            password="demo-pass-123",
            isTestUser=True,
        )
    )

    login_body = _decode_json_response(api.login(api.LoginRequest(username="joe-test", password="demo-pass-123")))
    assert login_body["user"]["isTestUser"] is True

    submit = api.post_pond_update(
        {
            "type": "pond-update",
            "authToken": login_body["authToken"],
            "queue": {"index": 2, "label": "5"},
        }
    )
    submit_body = _decode_json_response(submit)
    assert submit.status_code == 200
    assert submit_body["submittedBy"]["isTestUser"] is True


def test_test_user_can_submit_historical_update(auth_env) -> None:
    api.register_nickname(
        api.RegisterNicknameRequest(
            nickname="backfill-test",
            password="demo-pass-123",
            isTestUser=True,
        )
    )
    login_body = _decode_json_response(
        api.login(api.LoginRequest(username="backfill-test", password="demo-pass-123"))
    )
    historical_timestamp = "2026-07-29T12:34:56+00:00"

    response = api.post_pond_update(
        {
            "type": "pond-update",
            "authToken": login_body["authToken"],
            "testMeta": {
                "isTestSubmission": True,
                "historicalTimestamp": historical_timestamp,
            },
        }
    )
    body = _decode_json_response(response)

    second_response = api.post_pond_update(
        {
            "type": "pond-update",
            "authToken": login_body["authToken"],
            "testMeta": {
                "isTestSubmission": True,
                "historicalTimestamp": historical_timestamp,
            },
        }
    )

    assert body["receivedAt"] == historical_timestamp
    assert second_response.status_code == 200
    output_path = auth_env["updates_dir"] / "user-updates-260729.jsonl"
    stored = [json.loads(line) for line in output_path.read_text(encoding="utf-8").splitlines()]
    assert len(stored) == 2
    assert all(record["receivedAt"] == historical_timestamp for record in stored)


def test_normal_user_cannot_submit_historical_update(auth_env) -> None:
    api.register_nickname(
        api.RegisterNicknameRequest(nickname="normal-user", password="demo-pass-123")
    )
    login_body = _decode_json_response(
        api.login(api.LoginRequest(username="normal-user", password="demo-pass-123"))
    )
    historical_timestamp = "2020-01-01T00:00:00+00:00"

    response = api.post_pond_update(
        {
            "type": "pond-update",
            "authToken": login_body["authToken"],
            "testMeta": {
                "isTestSubmission": True,
                "historicalTimestamp": historical_timestamp,
            },
        }
    )
    body = _decode_json_response(response)

    assert body["receivedAt"] != historical_timestamp
