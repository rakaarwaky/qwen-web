# AES Migration Guide — Python (v1.1.0)

> Skill-driven migration workflow for Python projects to AES architecture.
> Each phase delegates to a dedicated skill in `.agents/skills/`.

See [ARCHITECTURE.md](ARCHITECTURE.md) for layer rules and
[README.md](README.md) for project usage.

---

## Table of Contents

- [AES Dependency Model](#aes-dependency-model)
- [Workspace Structure](#workspace-structure)
- [Prerequisites](#prerequisites)
- [Phase 0: Audit & Config Setup](#phase-0-audit--config-setup)
- [Phase 1: Taxonomy Layer](#phase-1-taxonomy-layer)
- [Phase 2: Contract Layer](#phase-2-contract-layer)
- [Phase 3: Utility Layer](#phase-3-utility-layer)
- [Phase 4: Capabilities Layer](#phase-4-capabilities-layer)
- [Phase 5: Agent Layer](#phase-5-agent-layer)
- [Phase 6: Surface Layer](#phase-6-surface-layer)
- [Phase 7: Root Layer](#phase-7-root-layer)
- [Phase 8: Verify & CI Gate](#phase-8-verify--ci-gate)
- [Import Rules Quick Reference](#import-rules-quick-reference)
- [Supplementary Skills](#supplementary-skills-post-migration)
- [File Naming Reference](#file-naming-reference)
- [Troubleshooting](#troubleshooting)

---

## AES Dependency Model

AES uses **dependency injection** as the inter-layer wiring mechanism.
Layers do not import each other directly — they import from **contract**
and receive dependencies via constructor injection:

```
                    ┌──────────────────────────────────┐
                    │             root                  │
                    │  (DI wiring — wires everything)   │
                    └──────┬───────────────────────────┘
                           │
              ┌────────────┼─────────────┐
              ▼            ▼             ▼
         ┌────────┐  ┌─────────┐  ┌──────────────┐
         │surface │  │  agent  │  │ capabilities │
         └───┬────┘  └────┬────┘  └──────┬───────┘
             │            │              │
             ▼            ▼              ▼
        ┌──────────────────────────────────────────┐
        │      contract (protocol / aggregate)      │
        └──────────────────┬───────────────────────┘
                           ▼
                  ┌──────────────────┐
                  │    taxonomy       │
                  └──────────────────┘

         utility ←── flexible, imports taxonomy only
```

**Key principles:**

- Agent does **not** import capabilities — it receives them via constructor injection.
- Surface does **not** import agent — it receives the orchestrator via constructor injection.
- Capabilities **implements** protocol ABCs. Agent **implements** aggregate ABCs.
- Utility is flexible — imports taxonomy only, imported by capabilities/agent/surface.
- Python DI pattern: pass ABC instances via `__init__` constructor parameters.
- All import rules are enforced by `lint-arwaky-cli` (AES201–AES205).

---

## Workspace Structure

```
project-root/
├── pyproject.toml           ← workspace root config
├── lint_arwaky.config.yaml  ← AES config (created in Phase 0)
├── modules/
│   ├── shared/              ← shared taxonomy + contract + utility types
│   │   ├── pyproject.toml
│   │   └── src/
│   │       ├── __init__.py
│   │       ├── common/          ← truly shared across ALL features
│   │       │   └── __init__.py
│   │       └── <feature>/       ← shared types per feature domain
│   │           ├── __init__.py
│   │           ├── taxonomy_<concept>_vo.py
│   │           ├── taxonomy_<concept>_error.py
│   │           ├── taxonomy_<concept>_constant.py
│   │           ├── contract_<concept>_protocol.py
│   │           ├── contract_<concept>_aggregate.py
│   │           └── utility_<concept>_<role>.py
│   │
│   ├── <feature>/           ← feature module
│   │   ├── pyproject.toml
│   │   └── src/
│   │       ├── __init__.py
│   │       ├── capabilities_<concept>_<role>.py
│   │       ├── agent_<concept>_orchestrator.py
│   │       ├── surface_<concept>_<role>.py
│   │       └── root_<concept>_container.py
│   │
│   └── root_<name>_entry.py   ← entry point (file inside modules/)
│
└── tests/
```

**Key rules:**

- All 7 layers coexist in each feature slice.
- Taxonomy, contracts, and utilities live under `modules/shared/src/<feature>/`.
- Capabilities, agent, surface, and root live in the feature module.
- Entry points (`root_*_entry.py`) live directly under `modules/` (file, NOT directory).
- `modules/shared/src/common/` holds types shared across ALL features.
- Every package directory must have `__init__.py` (barrel file — skipped by lint).

---

## Prerequisites

```bash
# Install lint-arwaky
pip install lint-arwaky-cli

# Verify installation
lint-arwaky-cli version
# Expected: Lint Arwaky v1.1.0

# Install external linters (optional, for external lint checks)
pip install ruff mypy bandit
lint-arwaky-cli install
```

---

## Phase 0: Audit & Config Setup

> **Skill:** `lint-arwaky-python` — load for audit commands and violation analysis.

### Step 1: Initialize Config

```bash
cd your-project/
lint-arwaky-cli init
```

This creates `lint_arwaky.config.yaml` with default AES rules.

### Step 2: Run Initial Audit

```bash
lint-arwaky-cli scan .
```

### Step 3: Assess Migration Scope


| Violations | Strategy                                                    |
| ------------ | ------------------------------------------------------------- |
| < 10       | Full migration in one session                               |
| 10–50     | Phased migration (Phase 1 → 8)                             |
| > 50       | Start with taxonomy only (Phase 1), re-audit, then continue |

### Step 4: Count Files

```bash
find modules -name "*.py" | grep -v __init__ | grep -v __pycache__ | wc -l
```

---

## Phase 1: Taxonomy Layer

> **Skill:** `create-taxonomy-python` — load for VOs, errors, constants, entities, events.

Define Value Objects, Errors, Events, and Constants under
`modules/shared/src/<feature>/`.

### Steps

1. Identify domain types:
   ```bash
   grep -rn "^class " modules/*/src/ | grep -v test | grep -v __init__
   ```
2. Load `create-taxonomy-python` skill.
3. Create taxonomy files following skill templates.
4. Register in domain `__init__.py`.
5. Verify: `python -c "from modules.shared.src.<feature> import *"`.

### Example

```python
# modules/shared/src/user/taxonomy_user_vo.py
"""User domain value objects."""

from dataclasses import dataclass


@dataclass(frozen=True)
class UserId:
    """User identifier value object."""

    value: str

    def __post_init__(self) -> None:
        if not self.value:
            raise ValueError("UserId cannot be empty")


@dataclass(frozen=True)
class Email:
    """Email value object."""

    value: str

    def __post_init__(self) -> None:
        if "@" not in self.value:
            raise ValueError(f"Invalid email: {self.value}")
```

```python
# modules/shared/src/user/taxonomy_user_error.py
"""User domain errors."""


class UserError(Exception):
    """Base error for user domain."""


class UserNotFoundError(UserError):
    """Raised when a user is not found."""

    def __init__(self, user_id: "UserId") -> None:
        super().__init__(f"User not found: {user_id.value}")
```

```python
# modules/shared/src/user/taxonomy_user_constant.py
"""User domain constants."""

MAX_USERNAME_LENGTH: int = 128
MIN_PASSWORD_LENGTH: int = 8
DEFAULT_PAGE_SIZE: int = 50
```

### Rules Enforced

- **AES101**: Filename must be `taxonomy_<concept>_<suffix>.py` (snake_case, 3+ words).
- **AES102**: Suffix must be `vo`, `entity`, `error`, `event`, or `constant`.
- **AES401**: No raw primitives (`str`, `int`, `float`, `bool`, `list`, `dict`) in type annotations — wrap in VOs.
- **AES401**: `_constant` files must contain only module-level assignments — no `class`, no `def`.

---

## Phase 2: Contract Layer

> **Skill:** `create-contract-python` — load for protocol and aggregate ABCs.

Contracts define public interfaces (Protocols and Aggregates) using
`abc.ABC` without exposing implementation.

### Steps

1. Load `create-contract-python` skill.
2. Create protocol ABCs (inbound/outbound) under `modules/shared/src/<feature>/`.
3. Create aggregate facade ABCs under `modules/shared/src/<feature>/`.
4. Register in domain `__init__.py`.
5. Verify: `python -c "from modules.shared.src.<feature> import *"`.

### Example

```python
# modules/shared/src/user/contract_user_protocol.py
"""User repository protocol contract."""

from abc import ABC, abstractmethod
from typing import Optional

from modules.shared.src.user.taxonomy_user_vo import UserId, Email, User
from modules.shared.src.user.taxonomy_user_error import UserError


class IUserRepositoryProtocol(ABC):
    """Protocol for user repository operations.
    Implemented by capabilities layer.
    """

    @abstractmethod
    def find_by_id(self, user_id: UserId) -> Optional[User]: ...

    @abstractmethod
    def find_by_email(self, email: Email) -> Optional[User]: ...

    @abstractmethod
    def save(self, user: User) -> None: ...
```

```python
# modules/shared/src/user/contract_user_aggregate.py
"""User aggregate facade contract."""

from abc import ABC, abstractmethod

from modules.shared.src.user.taxonomy_user_vo import UserId, UserResponse
from modules.shared.src.user.taxonomy_user_error import UserError


class IUserAggregate(ABC):
    """Aggregate facade for user operations.
    Implemented by agent layer.
    """

    @abstractmethod
    def get_user(self, user_id: UserId) -> UserResponse: ...

    @abstractmethod
    def register_user(self, command: "RegisterCommand") -> UserResponse: ...
```

### Rules Enforced

- **AES102**: Suffix must be `protocol` or `aggregate`.
- **AES402**: No raw primitives in method signatures — use VOs.
- **AES201**: Protocol must not import aggregate. Aggregate may import protocol.

---

## Phase 3: Utility Layer

> **Skill:** `create-utility-python` — load for stateless standalone functions.

Utility contains low-level technical mechanics — **stateless standalone
functions only**. No classes.

### Steps

1. Identify reusable stateless functions across modules.
2. Load `create-utility-python` skill.
3. Create utility files under `modules/shared/src/<feature>/`.
4. Register in domain `__init__.py`.
5. Verify: `python -c "from modules.shared.src.<feature> import *"`.

### Example

```python
# modules/shared/src/user/utility_user_validator.py
"""User validation utilities. Stateless functions only — no classes."""

import re

from modules.shared.src.user.taxonomy_user_vo import Email


def validate_email(email: Email) -> bool:
    """Validate email format."""
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email.value))


def normalize_email(email: Email) -> Email:
    """Normalize email to lowercase."""
    return Email(value=email.value.lower())


def generate_user_id() -> str:
    """Generate a UUID-based user identifier."""
    import uuid

    return str(uuid.uuid4())
```

### Rules Enforced

- **AES102**: Suffix is flexible, but forbidden suffixes apply (`vo`, `entity`, `protocol`, `aggregate`, etc.).
- **AES404**: No `class` definitions. `def` (functions) are allowed and expected.
- **AES201**: Utility may import taxonomy only. Must not import contract, capabilities, agent, surface.

---

## Phase 4: Capabilities Layer

> **Skill:** `create-capabilities-python` — load for business logic and external adaptation.

Capabilities contain concrete behavior implementations. They **implement
protocol ABCs** defined in the contract layer via inheritance.

### Steps

1. Load `create-capabilities-python` skill.
2. Create business logic capabilities (inherit protocol ABCs).
3. Create external adaptation capabilities (repositories, clients).
4. Verify: `python -c "from modules.<feature>.src.capabilities_<name> import *"`.

### Example

```python
# modules/user/src/capabilities_user_repository.py
"""User repository capability — implements IUserRepositoryProtocol."""

from typing import Optional

from modules.shared.src.user.contract_user_protocol import IUserRepositoryProtocol
from modules.shared.src.user.taxonomy_user_vo import UserId, Email, User
from modules.shared.src.user.taxonomy_user_error import UserNotFoundError


class UserRepository(IUserRepositoryProtocol):
    """Concrete user repository backed by database."""

    def __init__(self, db_connection: "DatabaseConnection") -> None:
        self._db = db_connection

    def find_by_id(self, user_id: UserId) -> Optional[User]:
        row = self._db.query("SELECT * FROM users WHERE id = %s", user_id.value)
        if row is None:
            return None
        return User.from_row(row)

    def find_by_email(self, email: Email) -> Optional[User]:
        row = self._db.query("SELECT * FROM users WHERE email = %s", email.value)
        if row is None:
            return None
        return User.from_row(row)

    def save(self, user: User) -> None:
        self._db.execute(
            "INSERT INTO users (id, email, name) VALUES (%s, %s, %s)",
            user.id.value,
            user.email.value,
            user.name.value,
        )
```

### Rules Enforced

- **AES102**: Suffix is flexible (forbidden: `vo`, `entity`, `protocol`, `aggregate`, `utility`).
- **AES201**: Capabilities may import taxonomy, contract, utility. Must not import agent, surface, other capabilities.
- **AES202**: Must import taxonomy and contract(protocol).
- **AES403**: At least 1 class must inherit a protocol ABC. Max 3 class definitions per file.
- **AES201 purpose**: contract(protocol) imports must be used for class inheritance (`implement`), not just function calls.

---

## Phase 5: Agent Layer

> **Skill:** `create-agent-python` — load for orchestration logic.

Orchestrates sequential execution, branching, looping, and error handling.
**Implements aggregate ABCs** defined in the contract layer.

### Steps

1. Load `create-agent-python` skill.
2. Create orchestrator class inheriting aggregate ABC.
3. Inject protocol dependencies via constructor.
4. Verify: `python -c "from modules.<feature>.src.agent_<name> import *"`.

### Example

```python
# modules/user/src/agent_user_orchestrator.py
"""User orchestrator — implements IUserAggregate."""

from modules.shared.src.user.contract_user_aggregate import IUserAggregate
from modules.shared.src.user.contract_user_protocol import IUserRepositoryProtocol
from modules.shared.src.user.taxonomy_user_vo import UserId, UserResponse
from modules.shared.src.user.taxonomy_user_error import UserNotFoundError


class UserOrchestrator(IUserAggregate):
    """Orchestrates user operations via injected repository."""

    def __init__(self, repository: IUserRepositoryProtocol) -> None:
        self._repository = repository

    def get_user(self, user_id: UserId) -> UserResponse:
        user = self._repository.find_by_id(user_id)
        if user is None:
            raise UserNotFoundError(user_id)
        return UserResponse.from_user(user)

    def register_user(self, command: "RegisterCommand") -> UserResponse:
        # orchestration: validate → check duplicate → save → return
        existing = self._repository.find_by_email(command.email)
        if existing is not None:
            raise UserAlreadyExistsError(command.email)
        user = User.create(command)
        self._repository.save(user)
        return UserResponse.from_user(user)
```

### Rules Enforced

- **AES102**: Suffix must be `orchestrator`.
- **AES201**: Agent may import taxonomy, contract(aggregate), contract(protocol), utility. Must not import capabilities, surface.
- **AES202**: Must import taxonomy and contract(aggregate).
- **AES405**: At least 1 class must inherit an aggregate ABC. Max 3 class definitions.
- **AES201 purpose**: contract(aggregate) imports must be used for class inheritance (`implement`).

---

## Phase 6: Surface Layer

> **Skill:** `create-surface-python` — load for user-facing input translation.

Translates user-facing inputs into actions, delegating to the Agent
orchestrator via aggregate ABC.

### Surface Classification


| Category    | Suffixes                                      | Rules                                                                                                 |
| ------------- | ----------------------------------------------- | ------------------------------------------------------------------------------------------------------- |
| **Smart**   | `_command`, `_controller`, `_page`, `_router` | May contain orchestration logic. Global limit: 15 functions.                                          |
| **Utility** | `_hook`, `_store`, `_action`, `_screen`       | Supports smart surfaces. Max 10 methods, 80 lines/method, 3 nesting depth, 3 control-flow statements. |
| **Passive** | `_component`, `_view`, `_layout`, others      | Presentation only. Same limits as Utility.                                                            |

### Steps

1. Load `create-surface-python` skill.
2. Create surface classes (commands, handlers, endpoints).
3. Inject aggregate ABC via constructor.
4. Verify: `python -c "from modules.<feature>.src.surface_<name> import *"`.

### Example

```python
# modules/user/src/surface_user_command.py
"""User command surface — delegates to aggregate."""

from modules.shared.src.user.contract_user_aggregate import IUserAggregate
from modules.shared.src.user.taxonomy_user_vo import UserId, UserResponse


class GetUserCommand:
    """Command to retrieve a user by ID."""

    def __init__(self, aggregate: IUserAggregate) -> None:
        self._aggregate = aggregate

    def execute(self, user_id: UserId) -> UserResponse:
        return self._aggregate.get_user(user_id)
```

### Rules Enforced

- **AES102**: Suffix must be in the surface allow-list.
- **AES201**: Surface(command) may import taxonomy, contract(aggregate), utility. Must not import agent, capabilities, contract(protocol).
- **AES406**: Function count, method count, method length, nesting depth, and control-flow limits apply per surface category.
- **AES201 purpose**: contract(aggregate) imports must be used for method calls (`call`), not class inheritance.

---

## Phase 7: Root Layer

> **Skill:** `create-root-python` — load for DI container and entry point wiring.

Wires concrete implementations to contracts and bootstraps the system.
Root is the **only layer** allowed to import all other layers.

### Steps

1. Load `create-root-python` skill.
2. Create DI container wiring: capabilities → orchestrator → surface.
3. Create entry point at `modules/root_<name>_entry.py`.
4. Verify: `python -c "from modules.root_<name>_entry import main"`.

### Example

```python
# modules/user/src/root_user_container.py
"""User DI container — wires all layers."""

from modules.shared.src.user.contract_user_protocol import IUserRepositoryProtocol
from modules.shared.src.user.contract_user_aggregate import IUserAggregate
from modules.user.src.capabilities_user_repository import UserRepository
from modules.user.src.agent_user_orchestrator import UserOrchestrator
from modules.user.src.surface_user_command import GetUserCommand


class UserContainer:
    """DI container for user feature."""

    def __init__(self, db_connection: "DatabaseConnection") -> None:
        # Wire: capabilities → agent → surface
        repository: IUserRepositoryProtocol = UserRepository(db_connection)
        orchestrator: IUserAggregate = UserOrchestrator(repository)
        self.get_user_command = GetUserCommand(orchestrator)
```

```python
# modules/root_app_entry.py
"""Application entry point."""

from modules.user.src.root_user_container import UserContainer


def main() -> None:
    db = create_database_connection()
    container = UserContainer(db)
    # start application...


if __name__ == "__main__":
    main()
```

### Rules Enforced

- **AES102**: Suffix must be `entry` or `container`.
- **AES201**: Root may import all layers. No forbidden imports.
- Root layer files are **skipped** by role-rules (AES401–406) and orphan-detector.

---

## Phase 8: Verify & CI Gate

> **Skill:** `build-verify-all` — load for final build verification.

### Step 1: Full AES Scan

```bash
lint-arwaky-cli scan .
```

**Target: 0 violations.**

### Step 2: Run Tests

```bash
pytest
```

### Step 3: External Lint

```bash
ruff check .
ruff format --check .
mypy modules/
bandit -r modules/
```

### Step 4: CI Gate

```bash
lint-arwaky-cli ci . --threshold 0
```

**Exit code 0** = all checks pass. **Exit code 1** = violations found.

### Step 5: External Lint via Lint Arwaky (optional)

```bash
lint-arwaky-cli external .
```

---

## Import Rules Quick Reference


| Source Layer   | May Import                             | Must NOT Import                                       |
| ---------------- | ---------------------------------------- | ------------------------------------------------------- |
| `taxonomy`     | taxonomy                               | contract, utility, capabilities, agent, surface, root |
| `contract`     | taxonomy, contract                     | utility, capabilities, agent, surface, root           |
| `utility`      | taxonomy                               | contract, capabilities, agent, surface, root          |
| `capabilities` | taxonomy, contract, utility            | capabilities, agent, surface, root                    |
| `agent`        | taxonomy, contract, utility            | capabilities, surface, root                           |
| `surface`      | taxonomy, contract(aggregate), utility | agent, capabilities, contract(protocol), root         |
| `root`         | ALL layers                             | —                                                    |

**Purpose enforcement** (AES201 sub-check):


| Import                             | Expected Purpose                 |
| ------------------------------------ | ---------------------------------- |
| capabilities → contract(protocol) | `implement` (class inherits ABC) |
| agent → contract(aggregate)       | `implement` (class inherits ABC) |
| surface → contract(aggregate)     | `call` (method invocation)       |
| capabilities → utility            | `call` (function invocation)     |
| agent → utility                   | `call` (function invocation)     |

---

## Supplementary Skills (Post-Migration)


| Skill                        | When to Use                                                                    |
| ------------------------------ | -------------------------------------------------------------------------------- |
| `add-docs-python`            | Add docstrings, type hints after migration                                     |
| `fix-bypass-python`          | Remove`# type: ignore`, `# noqa`, `raise NotImplementedError`, `FIXME`, `HACK` |
| `cleanup-consolidate-python` | Remove dead code, merge duplicates                                             |
| `create-test-python`         | Generate test suites                                                           |

---

## File Naming Reference


| Layer        | Pattern                              | Allowed Suffixes                                                                                              |
| -------------- | -------------------------------------- | --------------------------------------------------------------------------------------------------------------- |
| taxonomy     | `taxonomy_<concept>_<suffix>.py`     | `vo`, `entity`, `error`, `event`, `constant`                                                                  |
| contract     | `contract_<concept>_<suffix>.py`     | `protocol`, `aggregate`                                                                                       |
| utility      | `utility_<concept>_<suffix>.py`      | flexible (forbidden:`vo`, `entity`, `protocol`, `aggregate`)                                                  |
| capabilities | `capabilities_<concept>_<suffix>.py` | flexible (forbidden:`vo`, `entity`, `protocol`, `aggregate`, `utility`)                                       |
| agent        | `agent_<concept>_orchestrator.py`    | `orchestrator`                                                                                                |
| surface      | `surface_<concept>_<suffix>.py`      | `command`, `controller`, `page`, `router`, `hook`, `store`, `action`, `screen`, `component`, `view`, `layout` |
| root         | `root_<concept>_<suffix>.py`         | `entry`, `container`                                                                                          |

---

## Troubleshooting

### Common Violations and Fixes


| Code        | Violation                                               | Fix                                                     |
| ------------- | --------------------------------------------------------- | --------------------------------------------------------- |
| AES101      | Filename not snake_case or < 3 words                    | Rename to`prefix_concept_suffix.py`                     |
| AES102      | Wrong suffix for layer                                  | Change suffix to match layer's allow-list               |
| AES201      | Forbidden cross-layer import                            | Route through contract layer; use constructor injection |
| AES202      | Missing mandatory import                                | Add required taxonomy/contract import                   |
| AES203      | Unused import                                           | Remove the import                                       |
| AES204      | Dummy function (`_use_*`, `dummy_*`)                    | Remove dummy function and the import it fakes           |
| AES205      | Circular dependency                                     | Break cycle via contract layer abstraction              |
| AES301      | File > 1000 lines                                       | Split into smaller files                                |
| AES304      | `# type: ignore`, `# noqa`, `raise NotImplementedError` | Fix the type error; implement the method                |
| AES401      | Raw primitive in taxonomy                               | Wrap in Value Object (`@dataclass(frozen=True)`)        |
| AES403      | Capability missing protocol inheritance                 | Add`class Foo(IProtocol)`                               |
| AES404      | Class in utility file                                   | Move class to taxonomy; keep only`def` functions        |
| AES405      | Agent missing aggregate inheritance                     | Add`class Foo(IAggregate)`                              |
| AES406      | Too many functions in surface                           | Split into smaller surface files                        |
| AES501–506 | Orphan file                                             | Wire into container or remove                           |

### Parse Errors

If `lint-arwaky-cli` reports `PARSE_WARN` for a file, the file has a syntax
error that prevents AST parsing. Fix the syntax error first, then re-scan.

### Config Not Found

If no config file is found, lint-arwaky uses embedded defaults. Run
`lint-arwaky-cli init` to create an explicit config file.

### Python-Specific: Relative Imports

AES Python projects use **absolute imports** from the `modules` root:

```python
# ✅ Correct — absolute import
from modules.shared.src.user.taxonomy_user_vo import UserId

# ❌ Wrong — relative import (breaks orphan detection)
from ..shared.src.user.taxonomy_user_vo import UserId
```

See [ARCHITECTURE.md](ARCHITECTURE.md) §12 for the full violation code reference.

---

## Reference

- Architecture: [ARCHITECTURE.md](ARCHITECTURE.md)
- CLI Reference: [README.md](README.md)
- PRD: [PRD.md](PRD.md)
- Test Plan: [TEST_PLAN.md](TEST_PLAN.md)
- Rust Migration Guide: [MIGRATION_RUST.md](MIGRATION_RUST.md)
