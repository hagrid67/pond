#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_AUTH_DB_PATH = REPO_ROOT / "data" / "auth.sqlite"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Pond user admin CLI")
    parser.add_argument(
        "--db-path",
        default=str(DEFAULT_AUTH_DB_PATH),
        help=f"Path to auth sqlite database (default: {DEFAULT_AUTH_DB_PATH})",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all registered users (nickname, email, isVerified, member, isTestUser).",
    )
    parser.add_argument(
        "--delete-user",
        default=None,
        help="Delete a user by username, nickname, or email (case-insensitive).",
    )
    return parser.parse_args()


def as_bool_text(value: object) -> str:
    return "Y" if bool(value) else "-"


def list_users(db_path: Path) -> int:
    if not db_path.exists():
        raise SystemExit(f"Auth DB not found: {db_path}")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT
                COALESCE(nickname, '') AS nickname,
                COALESCE(email, '') AS email,
                email_verified,
                is_member,
                is_test_user
            FROM users
            ORDER BY lower(COALESCE(nickname, email, '')), id
            """
        ).fetchall()
    finally:
        conn.close()

    headers = ["nickname", "email", "isVerified", "member", "isTestUser"]
    body: list[list[str]] = []
    for row in rows:
        body.append(
            [
                str(row["nickname"]),
                str(row["email"]),
                as_bool_text(row["email_verified"]),
                as_bool_text(row["is_member"]),
                as_bool_text(row["is_test_user"]),
            ]
        )

    if not body:
        print("No users found.")
        return 0

    widths = [len(col) for col in headers]
    for record in body:
        for idx, value in enumerate(record):
            widths[idx] = max(widths[idx], len(value))

    def fmt(record: list[str]) -> str:
        return "  ".join(value.ljust(widths[idx]) for idx, value in enumerate(record))

    print(fmt(headers))
    print(fmt(["-" * w for w in widths]))
    for record in body:
        print(fmt(record))

    return 0


def delete_user(db_path: Path, user_key: str) -> int:
    if not db_path.exists():
        raise SystemExit(f"Auth DB not found: {db_path}")

    key = user_key.strip().lower()
    if not key:
        raise SystemExit("--delete-user requires a non-empty value")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        user = conn.execute(
            """
            SELECT id, username, nickname, email
            FROM users
            WHERE lower(username) = ?
               OR lower(COALESCE(nickname, '')) = ?
               OR lower(COALESCE(email, '')) = ?
            ORDER BY id
            LIMIT 1
            """,
            (key, key, key),
        ).fetchone()

        if user is None:
            print(f"No matching user found for: {user_key}")
            return 1

        user_id = int(user["id"])

        conn.execute("DELETE FROM auth_sessions WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM email_verification_tokens WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
    finally:
        conn.close()

    print(
        "Deleted user: "
        f"id={user_id} "
        f"username={user['username']} "
        f"nickname={user['nickname'] or ''} "
        f"email={user['email'] or ''}"
    )
    return 0


def main() -> int:
    args = parse_args()
    db_path = Path(args.db_path)

    if args.delete_user:
        return delete_user(db_path, args.delete_user)

    if args.list:
        return list_users(db_path)

    print("No action selected. Use --list.")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
