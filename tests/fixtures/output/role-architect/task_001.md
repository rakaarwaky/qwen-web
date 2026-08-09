<!--
--- METADATA TRACEABILITY ---
Run ID           : 20260809_160916_24de12
Source File      : role-architect/todo/task_001.md
Processed At     : 2026-08-09T16:12:32.736080
Duration         : 195.85s
Input Characters : 3579
Output Characters: 9237
-----------------------------
-->

Plan: Auth — Architect
Environment constraint notice (transparency first): The role prerequisites — .agents/rules/RULES_AES.md, ARCHITECTURE.md, PRD.md, .agents/skills/, and <feature>/FRD.md — were not provided in this session; only task_001.md is available. Dedup commands (ls .agents/plans/..., gh pr list ...) cannot be executed here (no shell/GitHub access). All findings below are therefore treated as new. I also cannot write files from this environment, so the plan document is emitted in full below for saving to the required path. No code was executed.
Intended save path: .agents/plans/todo-auth-architect-20260809T000000Z.md
Dedup record: Dedup attempted, not executable in this environment → assumed 0 covered, 18 new.
Summary
task_001.md contains a single-file authentication module comprising three concerns: TokenFactory (HMAC-SHA256 token issue/validate — capabilities), UserRepository (in-memory credential store — data), and AuthService (login/logout/session validation — agent). The review surfaced 5 critical issues, including a non-loadable module (from future import annotations typo plus missing indentation throughout the file as provided), a guaranteed runtime crash in token creation (datetime.replace(second=now.second + ttl) overflows the 0–59 second range), an insecure fallback secret ("changeme"), unsalted SHA-256 password hashing, and a delimiter-injection flaw in the token body format. Secondary concerns cover dead issued_at data, unbounded in-memory state, concrete-class coupling without contracts, and hardcoded privilege grants on login. Proposed (non-executed) changes are provided for every finding.
Findings
Layer Boundaries
#
	
Severity
	
Issue
	
Location
	
Recommendation


B1
	
🟡 WARNING
	
Three distinct layers co-located in one file: data store, token capability, and service agent — violates SRP and 7-layer separation
	
task_001.md (whole file)
	
Split into auth/repository.py (data), auth/token.py (capabilities), auth/service.py (agent), composed at root


B2
	
🟡 WARNING
	
AuthService depends on concrete UserRepository / TokenFactory classes; no contract/protocol abstraction; dependency direction not invertible for tests
	
AuthService.__init__
	
Define UserRepositoryProtocol and TokenServiceProtocol (contract layer); depend on protocols


B3
	
🟢 INFO
	
TokenFactory.__init__ reads os.environ directly — hidden side effect in a capability constructor
	
TokenFactory.__init__
	
Inject secret via config at composition root; keep capability pure
Naming
#
	
Severity
	
Issue
	
Location
	
Recommendation


N1
	
🟢 INFO
	
TokenFactory both creates and validates tokens; "Factory" implies creation only
	
class TokenFactory
	
Rename to TokenService, or split into TokenIssuer / TokenValidator


N2
	
🟢 INFO
	
AuthService._sessions is an anonymous dict playing the role of a session store
	
AuthService.__init__
	
Extract named SessionStore collaborator to make the concept explicit and traceable
Capabilities
#
	
Severity
	
Issue
	
Location
	
Recommendation


C1
	
🔴 CRITICAL
	
from future import annotations is invalid (__future__ dunder missing) → ModuleNotFoundError on import
	
Line 1
	
Change to from __future__ import annotations


C2
	
🔴 CRITICAL
	
As provided, all class bodies/methods are at column 0 (no indentation) → file is unparseable and cannot be imported (possible transcription artifact, but must be verified)
	
Whole file
	
Restore correct indentation before any further review/CI


C3
	
🔴 CRITICAL
	
expires_at=now.replace(second=now.second + self.ttl_seconds) — second must be 0–59; with default ttl_seconds=3600 this always raises ValueError; create() can never succeed
	
TokenFactory.create
	
Use expires_at = now + timedelta(seconds=self.ttl_seconds)


C4
	
🔴 CRITICAL
	
Insecure fallback secret: os.environ.get("AUTH_SECRET", "changeme") fails open with a known default — forgeable tokens
	
TokenFactory.__init__
	
Fail fast: raise if neither arg nor env secret is present; never default


C5
	
🟡 WARNING
	
Passwords are stored/checked as unsalted SHA-256 — rainbow-table and brute-force vulnerable; not a password KDF
	
UserRepository.save / AuthService.login
	
Use a salted adaptive KDF (argon2/bcrypt/scrypt/PBKDF2); store salt+hash, verify via KDF API


C6
	
🟢 INFO
	
No token identifier (jti/nonce) — enables replay within TTL and prevents audit/revocation traceability
	
TokenFactory.create
	
Add random jti to signed body and to session records
Agent
#
	
Severity
	
Issue
	
Location
	
Recommendation


A1
	
🟡 WARNING
	
login hardcodes full privileges {"read", "write"} for every authenticated user — privilege grant is not derived from user roles
	
AuthService.login
	
Resolve scopes from the user record/policy; default to least privilege ({"read"})


A2
	
🟡 WARNING
	
AuthService aggregates session lifecycle management inside the agent instead of delegating to a collaborator
	
AuthService._sessions, logout, validate
	
Inject a SessionStore dependency; keep agent orchestration-only
Orphan
#
	
Severity
	
Issue
	
Location
	
Recommendation


O1
	
🟡 WARNING
	
TokenPayload.issued_at is never serialized into the token; validate fabricates issued_at=epoch(0) — dead/misleading field breaks contract symmetry between create/validate
	
TokenPayload, create, validate
	
Either include iat in the signed body, or remove issued_at from the payload contract
Scalability
#
	
Severity
	
Issue
	
Location
	
Recommendation


S1
	
🟡 WARNING
	
_db and _sessions are unbounded in-memory dicts — no eviction, no persistence, no sharing across replicas; memory grows with every login
	
UserRepository._db, AuthService._sessions
	
Introduce TTL-based eviction / pluggable store interface (e.g., Redis-backed) behind the protocol layer


S2
	
🟢 INFO
	
REQUIRED_SCOPES is a module-level global constant
	
Top-level
	
Make scope policy injectable/configurable per deployment
Data Flow
#
	
Severity
	
Issue
	
Location
	
Recommendation


D1
	
🔴 CRITICAL
	
Token body uses | as delimiter but user_id is never validated/escaped — a sub containing | corrupts parsing (split("|") yields ≠4 parts) and enables field-injection into the signed string
	
create / validate
	
Reject | (and empty) in user_id at creation, or switch to a canonical encoding (JSON + base64url) before signing


D2
	
🟡 WARNING
	
validate returns a payload whose issued_at is fabricated (epoch 0), so downstream consumers silently receive incorrect data
	
TokenFactory.validate
	
Return true iat (see O1) or model it as Optional[datetime] = None
Violations
RULES_AES.md (101–506) is not accessible in this environment, so no rule IDs can be cited. Violations against general AES principles: layer co-location (B1), dependency on concrete implementations (B2), insecure defaults / weak credential hashing (C4, C5), unparseable module (C1, C2), broken data contract (O1, D2).
Action Items
P0 🔴 Fix __future__ import and restore indentation so the module loads (C1, C2)
P0 🔴 Replace datetime.replace(...) expiry computation with timedelta (C3)
P0 🔴 Remove "changeme" fallback; fail fast without secret (C4)
P0 🔴 Validate/escape user_id against delimiter injection (D1)
P1 🟡 Replace SHA-256 with salted adaptive password KDF (C5)
P1 🟡 Derive scopes from user policy instead of hardcoded {"read","write"} (A1)
P1 🟡 Serialize iat or remove it; fix fabricated issued_at (O1, D2)
P1 🟡 Split monolith into repository / token / service modules behind protocols (B1, B2)
P1 🟡 Add eviction/backing store for sessions (S1); extract SessionStore (A2, N2)
P2 🟢 Rename/split TokenFactory (N1); inject secret and scope config (B3, S2); add jti (C6)
Propose Change
All changes below are proposals only — nothing executed. Grouped by file.
File: task_001.md → proposed split
1. auth/token.py (capabilities) — fixes C1, C3, C4, D1, O1, C6:
python
1
2
3
4
5
6
7
8
9
10
11
12
13
14
15
16
17
18
19
20
21
22
23
24
25
26
27
28
29
30
31
32
33
from __future__ import annotations  # C1: was "from future import annotations"
import hashlib, hmac, os, secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional
REQUIRED_SCOPES = {"read", "write"}
@dataclass(frozen=True)
class TokenPayload:
    sub: str
    scopes: frozenset[str]
    issued_at: datetime
    expires_at: datetime
class TokenService:  # N1: renamed from TokenFactory (creates AND validates)
    """Issues and validates HMAC-SHA256 signed tokens."""
    def __init__(self, secret: str | None = None, ttl_seconds: int = 3600) -> None:
        secret = secret or os.environ.get("AUTH_SECRET")
        if not secret:  # C4: fail fast, no "changeme" fallback
            raise RuntimeError("A token-signing secret is required (arg or AUTH_SECRET)")
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        self.secret = secret.encode()
        self.ttl_seconds = ttl_seconds
    def create(self, user_id: str, scopes: Optional[set[str]] = None) -> str:
        if not user_id or "|" in user_id:  # D1: delimiter injection guard
            raise ValueError("user_id must be non-empty and must not contain '|'")
        scopes = scopes or {"read"}
        if not REQUIRED_SCOPES.issuperset(scopes):
            raise ValueError(f"scopes must be subset of {REQUIRED_SCOPES}")