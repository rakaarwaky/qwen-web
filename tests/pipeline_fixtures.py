"""Pipeline fixture helpers and golden task state management for tests."""

from __future__ import annotations

import shutil
import time
from pathlib import Path

_MIN_RUN_INTERVAL_SECS = 2.0

GOLDEN_TASKS: dict[str, str] = {
    "role-architect": """\
from __future__ import annotations

import hashlib
import hmac
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional


REQUIRED_SCOPES = {"read", "write"}


@dataclass(frozen=True)
class TokenPayload:
    sub: str
    scopes: frozenset[str]
    issued_at: datetime
    expires_at: datetime


class TokenFactory:
    \"\"\"Creates and validates HMAC-SHA256 signed tokens.\"\"\"

    def __init__(self, secret: str | None = None, ttl_seconds: int = 3600) -> None:
        self.secret = (secret or os.environ.get("AUTH_SECRET", "changeme")).encode()
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        self.ttl_seconds = ttl_seconds

    def create(self, user_id: str, scopes: Optional[set[str]] = None) -> str:
        scopes = scopes or {"read"}
        if not REQUIRED_SCOPES.issuperset(scopes):
            raise ValueError(f"scopes must be subset of {REQUIRED_SCOPES}")
        now = datetime.now(timezone.utc)
        payload = TokenPayload(
            sub=user_id,
            scopes=frozenset(scopes),
            issued_at=now,
            expires_at=now.replace(second=now.second + self.ttl_seconds),
        )
        body = f"{payload.sub}|{','.join(sorted(payload.scopes))}|{int(payload.expires_at.timestamp())}"
        sig = hmac.new(self.secret, body.encode(), hashlib.sha256).hexdigest()
        return f"{body}|{sig}"

    def validate(self, token: str) -> TokenPayload | None:
        try:
            sub, scope_str, exp_ts, sig = token.split("|")
        except ValueError:
            return None
        expected = hmac.new(
            self.secret, f"{sub}|{scope_str}|{exp_ts}".encode(), hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(expected, sig):
            return None
        exp = datetime.fromtimestamp(int(exp_ts), tz=timezone.utc)
        if datetime.now(timezone.utc) > exp:
            return None
        return TokenPayload(
            sub=sub,
            scopes=frozenset(scope_str.split(",")) if scope_str else frozenset(),
            issued_at=datetime.fromtimestamp(0, tz=timezone.utc),
            expires_at=exp,
        )


class UserRepository:
    \"\"\"In-memory user store with password-hash lookup.\"\"\"

    def __init__(self) -> None:
        self._db: dict[str, str] = {}

    def save(self, username: str, password_hash: str) -> None:
        if not username or not password_hash:
            raise ValueError("username and password_hash are required")
        self._db[username] = password_hash

    def find_by_username(self, username: str) -> str | None:
        return self._db.get(username)


class AuthService:
    \"\"\"Login / logout / session validation.\"\"\"

    def __init__(self, repo: UserRepository, tokens: TokenFactory) -> None:
        self.repo = repo
        self.tokens = tokens
        self._sessions: dict[str, str] = {}

    def login(self, username: str, password: str) -> str | None:
        stored = self.repo.find_by_username(username)
        if stored is None:
            return None
        entered_hash = hashlib.sha256(password.encode()).hexdigest()
        if not hmac.compare_digest(stored, entered_hash):
            return None
        token = self.tokens.create(username)
        self._sessions[username] = token
        return token

    def validate_session(self, username: str, token: str) -> bool:
        if self._sessions.get(username) != token:
            return False
        payload = self.tokens.validate(token)
        return payload is not None and payload.sub == username

    def logout(self, username: str) -> None:
        self._sessions.pop(username, None)
""",
    "role-business-analyst": """\
# Business Requirements: Notification Service

## User Story
As a registered user, I want to receive real-time notifications for critical system events.

## Acceptance Criteria
- Email notification sent within 30 seconds of trigger.
- User can opt-out via preference settings.
- Retry up to 3 times on delivery failure.
""",
    "role-tech-lead": """\
# Tech Lead Review: Authentication Module

## Key Concerns
1. HMAC secret defaults to 'changeme' — must require environment override in production.
2. In-memory UserRepository lacks persistent database adapter.
3. Add rate limiting to AuthService.login to prevent brute-force attacks.
""",
}


def restore_fixture_state(fixture_root: Path, force: bool = False) -> None:
    """Restores tests/fixtures/ to pristine state if run threshold elapsed."""
    ts_file = fixture_root / ".last_run_ts"
    now = time.time()

    if not force and ts_file.exists():
        try:
            last_run = float(ts_file.read_text(encoding="utf-8").strip())
            if now - last_run < _MIN_RUN_INTERVAL_SECS:
                print(
                    f"\n\U0001f504  [FIXTURE RESET] Light restore (last run {now - last_run:.1f}s ago — output preserved)"
                )
                _restore_todo_files(fixture_root)
                return
        except ValueError:
            pass

    print("\n\U0001f504  [FIXTURE RESET] Full restore to pristine state...")
    _clean_output_dirs(fixture_root)
    _restore_todo_files(fixture_root)
    ts_file.write_text(str(now), encoding="utf-8")


def _clean_output_dirs(fixture_root: Path) -> None:
    output_dir = fixture_root / "output"
    if output_dir.exists():
        for out_sub in output_dir.iterdir():
            if out_sub.is_dir():
                shutil.rmtree(out_sub, ignore_errors=True)
            elif out_sub.is_file() and out_sub.name != ".gitkeep":
                out_sub.unlink(missing_ok=True)

    log_dir = fixture_root / "log"
    if log_dir.exists():
        for log_file in log_dir.glob("*"):
            if log_file.is_file() and log_file.name != ".gitkeep":
                log_file.unlink(missing_ok=True)


def _restore_todo_files(fixture_root: Path) -> None:
    input_dir = fixture_root / "input"
    for role, content in GOLDEN_TASKS.items():
        role_dir = input_dir / role
        role_dir.mkdir(parents=True, exist_ok=True)

        for sub in ("done", "failed", ".processing"):
            sub_dir = role_dir / sub
            if sub_dir.exists():
                shutil.rmtree(sub_dir, ignore_errors=True)

        todo_dir = role_dir / "todo"
        todo_dir.mkdir(parents=True, exist_ok=True)
        task_file = todo_dir / "task_001.md"
        if not task_file.exists() or task_file.read_text(encoding="utf-8").strip() != content.strip():
            task_file.write_text(content, encoding="utf-8")
