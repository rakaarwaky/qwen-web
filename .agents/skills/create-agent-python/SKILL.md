---
name: create-agent-python
description: "Create and validate Python agent layer files following AES rules: orchestration-only, zero I/O, zero business logic, zero domain computation, 3-block structure, max 3 types per file, aggregate ABC contracts, DI for service dependencies, and shared VOs for domain data."
metadata:
  tags: [python, aes, agent, aggregate, structure, 3-block-structure, di, orchestration, vo]
  triggers:
    - "create agent python"
    - "add agent python"
    - "fix agent structure python"
    - "create aggregate python"
    - "agent missing aggregate python"
    - "validate agent logic python"
    - "check agent python"
    - "audit agent python"
  dependencies: []
  related:
    - create-capabilities-python
    - create-taxonomy-python
    - create-contract-python
---

# create-agent-python

Agent = orchestration only. No I/O, no business logic, no domain computation, no local domain data.

**Allowed imports:** `shared/*` — taxonomy VOs, constants, aggregate ABCs, protocol ABCs, utility functions.
**Forbidden imports:** `capabilities_*`, `agent_*`, `surface_*`.

**Allowed ops:** `for`/`while`/`async for`, `if/else`/`match`, `try/except`/`raise`, `asyncio.wait_for`, collecting results into shared VOs.
**Forbidden ops:** `open()`, `Path()`, `os.*`, `requests.*`, `httpx.*`, `sqlite3.*`, `asyncpg.*`, stdout/stderr write, env mutation, global state mutation.

## 3-Block Structure

```text
# Block 1: Class Definition & Constructor
# Block 2: Aggregate Method Implementation
# Block 3: Dunder Methods, Factories, Helpers
```

Method placement:

```text
Module-level def?                    → EXTRACT to *_utility.py
@abstractmethod in aggregate ABC?    → Block 2
Dunder / factory @classmethod?       → Block 3
@staticmethod pure + no class dep?   → EXTRACT to *_utility.py
Private helper (uses self)?          → Block 3
```

## Helper vs Utility

Keep in Block 3 if ANY: uses `self`, coupled to this class, factory, agent-specific logic, single-use.
Extract to utility only if ALL: no `self`/`cls`, pure, no side effects, domain-agnostic, reusable.
I/O: stateless + I/O + domain-agnostic = taxonomy utility. Stateless + I/O + domain-specific = capabilities.

## Computation, Errors, VOs

**Computation forbidden:** arithmetic, totals, averages, `.reduce`/`.fold`, parsing, normalization. Allowed: iteration to call deps, routing results, propagating errors.

**Error rules:**
- Rule 1: Never silently discard — no `checker.check() or ""`.
- Rule 2: Analysis orchestration → return `list[<ResultVO>]`, catch per-item into VO.
- Rule 3: Execution orchestration → return `Result[...]`.
- Rule 4: Delegate I/O errors to capabilities — agent only wraps into VO.

**VO rules:** `str`/`int`/`float` forbidden for domain fields/contracts. `bool` for semantic toggles only.

## Templates

```python
from shared.<domain>.taxonomy_<name>_vo import <VO>
from shared.<domain>.contract_<name>_aggregate import I<Name>Aggregate


# ─── Block 1: Class Definition & Constructor ──────────────
class Agent<Name>:
    def __init__(self, aggregate: I<Name>Aggregate) -> None:
        self._aggregate = aggregate

    # ─── Block 2: Aggregate Method Implementation ─────────
    def execute(self, request: <RequestVO>) -> list[<ResultVO>]:
        # orchestration only — delegate to aggregate
        results = self._aggregate.process(request)
        return results

    # ─── Block 3: Dunder Methods, Factories & Helpers ─────
    def __repr__(self) -> str:
        return "Agent<Name>()"

    @classmethod
    def create_default(cls) -> "Agent<Name>":
        return cls()
```
## Workflow

1. Confirm orchestration only — computation → capabilities, domain data → taxonomy.
2. Agent class inherits aggregate ABC? If no → create `contract_<name>_aggregate.py`.
3. Enforce 3-Block.
4. ≥1 aggregate ABC, ≤3 classes, DI via protocols, shared VOs.
5. No forbidden imports, no I/O, no computation.
6. No silent errors, no raw primitives in contracts, no magic constants.
7. `python -c "import <module>"`.

## Checklist

- [ ] Block 1 → 2 → 3 order followed.
- [ ] Block 2: ONLY aggregate ABC method implementations.
- [ ] Block 3: dunders, factories, private helpers.
- [ ] ≥1 class inherits aggregate ABC; ≤3 total classes.
- [ ] No local domain data; DI via protocol interfaces; shared VOs.
- [ ] Zero I/O, zero business logic, zero domain computation.
- [ ] No forbidden imports.
- [ ] Aggregate registered in shared `__init__.py`.
- [ ] `python -c "import <module>"` passes.
