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
    """Creates and validates HMAC-SHA256 signed tokens."""

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
    """In-memory user store with password-hash lookup."""

    def __init__(self) -> None:
        self._db: dict[str, str] = {}

    def save(self, username: str, password_hash: str) -> None:
        if not username or not password_hash:
            raise ValueError("username and password_hash are required")
        self._db[username] = password_hash

    def find_by_username(self, username: str) -> str | None:
        return self._db.get(username)


class AuthService:
    """Login / logout / session validation."""

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
