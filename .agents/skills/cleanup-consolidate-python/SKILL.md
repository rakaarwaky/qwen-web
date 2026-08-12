---
name: cleanup-consolidate-python
description: "Find and remove dead code, unused files, stubs, thin wrappers, and duplicates across Python packages, then merge overlapping files into single cohesive modules."
metadata:
  tags:
    [
      python,
      cleanup,
      consolidation,
      bloat,
      stubs,
      thin-wrappers,
      dead-code,
      orphan,
      unused-files,
      merge,
      deduplication,
      single-file,
      ruff,
      vulture,
      black,
    ]
  triggers:
    - "cleanup python"
    - "clean bloat python"
    - "fix formatting python"
    - "remove unused imports python"
    - "remove stubs python"
    - "remove thin wrappers python"
    - "find unused files python"
    - "find dead code python"
    - "remove dead code python"
    - "cleanup module python"
    - "pep8 python"
    - "consolidate python"
    - "merge files python"
    - "combine modules python"
  dependencies: []
  related:
    - add-docs-python
    - create-capabilities-python
---

# cleanup-consolidate-python

## Purpose

Unified Python codebase cleanup skill combining **dead code removal** and **file consolidation**. First find and remove dead code, unused files, stubs, thin wrappers, and duplicates. Then detect overlapping files that share the same domain and merge them into single cohesive modules. The result is a cleaner codebase with fewer files, less bloat, and maximum signal-to-noise ratio.

**CRITICAL: Two-Phase Approach** — Phase 1 removes dead code. Phase 2 merges overlapping files. Never skip Phase 1 — consolidating files with dead code wastes effort.

---

## Rules

- **Never remove real logic** — only remove code not relevant to FRD scope
- **Always update `__all__`** — when removing functions/classes, remove from `__all__` too
- **Always update `__init__.py`** — when deleting modules, remove their imports/re-exports
- **Always run lint + tests after changes** — verify no breakage
- **Always snapshot before cleanup** — git commit or stash before any deletion
- **Respect `# noqa`** — developer explicitly suppressed a lint; investigate intent before removing
- **Respect `# type: ignore`** — may indicate intentional dynamic typing
- **Respect `# pragma: no cover`** — code intentionally excluded from coverage; investigate why
- **Respect decorator-registered code** — `@app.route`, `@pytest.fixture`, `@celery.task`, `@receiver` etc. are NOT dead code even if never directly called
- **Respect `if TYPE_CHECKING:` blocks** — these imports are used by type checkers, not at runtime
- **Respect `try/except ImportError` fallbacks** — conditional imports for optional dependencies
- **File with 0 inbound imports AND not an entry point** = likely unused (verify with multi-pattern check)
- **File with only re-exports in `__init__.py`** = evaluate whether re-export adds value
- **Single Responsibility** (consolidation): each file should have ONE clear purpose
- **Related classes/functions belong in the same file** (consolidation)

---

## When to Use

- After refactoring modules
- Before committing changes
- When user asks to clean bloat from a package
- After merging branches (accumulated dead code)
- Before release (final bloat + format pass)
- When cleaning up accumulated commented-out code
- When onboarding new developers (reduce noise)
- Files with scattered responsibilities
- Multiple small files that belong together
- After refactoring that split code across files

---

## The Fundamental Questions

### For Cleanup (Phase 1)

Before keeping any function, class, or file, ask:

> **"Why does this function/class/file need to exist?"**

| Answer | Verdict |
| ---------------------------------------------------------------------- | ------------------------------------------ |
| "Because it was always there" | **REMOVE** |
| "Because it might be useful someday" | **REMOVE** |
| "Because it handles edge cases we don't have" | **REMOVE** |
| "Because it's required by FRD" | **KEEP** |
| "Because it's called by a method required by FRD" | **KEEP** |
| "Because it's registered via decorator (route, fixture, task, signal)" | **KEEP** |
| "Because it's in `__all__` and consumed by downstream packages" | **KEEP** |
| "Because it's behind `if TYPE_CHECKING:` for type annotations" | **KEEP** |
| "Because it's a `try/except ImportError` fallback for optional dep" | **KEEP** (unless dep is confirmed removed) |
| "Because `importlib` loads it dynamically at runtime" | **KEEP** |
| "Because `conftest.py` or `pyproject.toml` entry_points reference it" | **KEEP** |
| "Because it's a Protocol / ABC that defines a contract" | **KEEP** |

### For Consolidation (Phase 2)

> **"Do these files serve the same purpose?"**

If yes → **Consolidate into single module**

---

## Phase 1: Dead Code Cleanup

### Detection Patterns: Function-Level Bloat

#### Stubs (Remove)

```python
# ❌ Empty implementations providing no value
def process(self) -> None:
    pass

def get_value(self) -> str:
    return ""

def get_items(self) -> list:
    return []

def get_mapping(self) -> dict:
    return {}

def compute(self) -> None:
    ...

def transform(self, data):
    raise NotImplementedError  # with no subclass implementing it
```

**Exception — KEEP stubs when:**

- They are abstract methods in an ABC/Protocol with active subclasses implementing them
- They are placeholder for a confirmed next-sprint FRD item (add `# TODO(FRD-XXX): implement`)
- They are `__init__.py` package markers (empty file is valid)

#### Thin Wrappers (Remove)

```python
# ❌ Simple attribute return — direct access is simpler
def get_name(self) -> str:
    return self.name

# ❌ Simple comparison — trivially inlineable
def is_active(self) -> bool:
    return self.status == "active"

# ❌ Single-field delegation — no logic added
def get_id(self) -> int:
    return self._inner.id

# ❌ Trivial passthrough
def save(self, data):
    self.repository.save(data)
```

**Exception — KEEP thin wrappers when:**

- They are part of a public API / ABC / Protocol contract
- They add validation, logging, or transformation (not just passthrough)
- They are `@property` accessors that enforce encapsulation on a public class
- They exist solely to satisfy a framework interface (e.g., Django `get_queryset`)

#### Duplicate Functions (Remove)

Same logic in multiple modules — keep in the module that **owns the domain logic**.

```python
# ❌ In utils/helpers.py AND services/processor.py:
def clamp(value: float, min_val: float, max_val: float) -> float:
    return max(min_val, min(value, max_val))
# KEEP in utils/helpers.py (owns utility logic). Remove from services/.
```

**Detection:** Match on function body similarity, not just name. Two functions with different names but identical bodies are also duplicates.

#### Overengineered Patterns (Remove)

```python
# ❌ Metaclass registries, plugin discovery systems, circular dep detectors,
#    event buses, temporal enforcers — if NOT in MVP → REMOVE
```

**3-Point Decision Test — ALL must be true to remove:**

1. ✅ The pattern is **NOT referenced** in any FRD requirement document
2. ✅ Removing it does **NOT break** any existing test (`pytest` passes)
3. ✅ The pattern adds **>20 lines** of code for **<3 lines** of actual consumed logic

If **any** check fails → **KEEP** and add comment: `# REVIEW: candidate for removal post-MVP`

#### Commented-Out Code (Remove)

```python
# ❌ Dead code left as comments
# def old_process(self):
#     result = self.transform(data)
#     return result.validate()

# ❌ Commented imports
# import pandas as pd
# from old_module import legacy_func
```

**Exception — KEEP comments when:**

- They are explanatory documentation (`# This handles the edge case where...`)
- They are `# TODO`, `# FIXME`, `# HACK` with ticket references
- They are `# noqa`, `# type: ignore`, `# pragma: no cover` directives

#### Unused Variables (Remove)

```python
# ❌ Assigned but never read
result = compute_something()  # result never used after this line
_ = some_function()           # intentional discard — KEEP this pattern

# ❌ Loop variable never used
for item in items:  # item never referenced in loop body
    count += 1
# Fix: for _ in items:
```

### Detection Patterns: File-Level Orphans

#### Unused Modules

Files not imported by any other file in the package:

```
my_package/orphan_feature.py  # 0 inbound refs
```

#### Re-Export Only `__init__.py`

```python
# ❌ my_package/subpkg/__init__.py — just a passthrough
from my_package.subpkg.real_impl import MyClass
from my_package.subpkg.real_impl import my_func
# WHY: If no downstream code imports from this path, consolidate.
```

**Exception — KEEP re-exports when:**

- They form a deliberate public API surface (documented in README / used by downstream packages)
- They are referenced in `pyproject.toml` `[tool.setuptools.packages]` or `setup.py`
- Changing the import path would be a breaking change for consumers

#### Empty / Near-Empty Files

```python
# ❌ module with only a docstring and no code
"""This module handles X."""
# (nothing else)

# ❌ module with only imports and no definitions
import os
import sys
# (nothing else)
```

**Exception:** `__init__.py` files may legitimately be empty (package marker).

### AES Layer-Specific Orphan Detection (AES501–AES506)

After generic orphan detection, run layer-specific orphan checks using the `orphan-detector` tool:

```bash
# Run full orphan scan (detects AES501–AES506 layer violations)
cargo run --bin lint-arwaky-cli -- orphan <project-path> --format json
```

The tool builds a full import reachability graph and checks:

| Rule | Layer | Orphan If... | Severity |
|------|-------|-------------|----------|
| **AES501** | Taxonomy | No non-taxonomy file imports it | MEDIUM |
| **AES502** | Contract | No implementation (`class X(Protocol)`) exists, or no callers | MEDIUM |
| **AES503** | Capabilities | Not wired in any container and not reachable from entry points | HIGH |
| **AES504** | Utility | Imported only by other utility files (utility-only chain = dead) | MEDIUM |
| **AES505** | Agent | Not referenced by any surface, entry point, or container | **HIGH** |
| **AES506** | Surface | Not reachable in `Entry→Smart→Utility→Passive` chain | MEDIUM |

### Exceptions (NEVER Remove Without Explicit Approval)

| File / Pattern | Reason |
| ------------------------------------------------------------------------------ | ------------------------------------------------------------------ |
| `__init__.py` | Package marker (may be empty by design) |
| `__main__.py` | Entry point for `python -m package` |
| `conftest.py` | pytest fixture discovery (not imported directly) |
| `setup.py` / `pyproject.toml` | Build / packaging config |
| `py.typed` | PEP 561 marker for typed packages |
| Protocol / ABC classes | Define contracts for subclasses |
| `if TYPE_CHECKING:` imports | Used by type checkers, invisible at runtime |
| `try/except ImportError` blocks | Optional dependency fallbacks |
| Decorator-registered functions | `@app.route`, `@pytest.fixture`, `@celery.task`, `@receiver`, etc. |
| `importlib`-loaded modules | Dynamically imported at runtime |
| `# noqa` / `# type: ignore` items | Developer explicitly suppressed — investigate intent |
| `# pragma: no cover` items | Intentionally excluded from coverage — investigate why |
| Entry points in `pyproject.toml` `[project.scripts]` / `[project.entry-points]` | Referenced by packaging, not by Python imports |
| Migration files (Django, Alembic) | Must be preserved for migration history |
| `__version__`, `__author__` dunder assignments | May be read by packaging tools |

### Phase 1 Workflow

#### Step 1.1: Safety Snapshot

```bash
# ALWAYS do this first — non-negotiable
git add -A && git commit -m "pre-cleanup snapshot: <package>" --allow-empty
git checkout -b cleanup/<package>-$(date +%Y%m%d)
```

If anything goes wrong:

```bash
git checkout main
git branch -D cleanup/<package>-$(date +%Y%m%d)
# Or restore specific files:
git checkout HEAD~1 -- <package>/<file>.py
```

#### Step 1.2: Read Requirements

Read the FRD / requirements document to understand MVP scope. List all required modules, classes, functions, and behaviors. Identify:

- Entry points (`pyproject.toml` scripts, `__main__.py`)
- Public API surface (`__all__`, documented imports)
- Framework registrations (routes, fixtures, tasks, signals)
- Optional dependency features

#### Step 1.3: Run Primary Detection (Tooling)

Use Python-native tooling FIRST — it understands the language semantics:

```bash
# Primary: ruff (replaces flake8, isort, pycodestyle, pycln, pyupgrade)
# Lint + unused imports + import sorting in one pass
ruff check <package>/ --select F,E,W,I --fix --unsafe-fixes 2>&1 | tee /tmp/ruff_report.txt

# Dead code detection (unused functions, classes, variables, attributes)
vulture <package>/ --min-confidence 80 --exclude "venv,.venv,__pycache__" 2>&1 | tee /tmp/vulture_report.txt

# Format check (do NOT auto-fix yet — review first)
black --check --diff <package>/ --line-length 88 2>&1 | tee /tmp/black_report.txt

# Type check (reveals unreachable code, unused ignores)
mypy <package>/ --warn-unused-ignores --warn-unreachable 2>&1 | tee /tmp/mypy_report.txt
# OR: pyright <package>/ 2>&1 | tee /tmp/pyright_report.txt

# Test compilation (catches test-only references)
pytest <package>/ --collect-only -q 2>&1 | tee /tmp/pytest_collect.txt
```

#### Step 1.4: Run Secondary Detection (File-Level Scan)

Multi-pattern scan for files not referenced anywhere:

```bash
#!/usr/bin/env bash
# find_unused_files.sh — comprehensive orphan detection for Python
PKG_DIR="<package>"

for f in $(find "$PKG_DIR" -name "*.py" -not -path "*/venv/*" -not -path "*/__pycache__/*"); do
  name=$(basename "$f" .py)
  rel_path="${f#$PKG_DIR/}"
  module_path=$(echo "$rel_path" | sed 's|/|.|g; s|\.py$||')

  # Skip protected files
  [[ "$name" =~ ^(__init__|__main__|conftest|setup)$ ]] && continue
  [[ "$name" =~ ^py$ ]] && continue  # py.typed

  refs=0

  # 1. Direct imports: "import name" or "from name import" or "from pkg.name import"
  refs=$((refs + $(grep -rnE "(import\s+${name}|from\s+.*\b${name}\b\s+import)" "$PKG_DIR" \
    --include="*.py" | grep -v "^$f:" | grep -v "__pycache__" | wc -l)))

  # 2. importlib dynamic imports: importlib.import_module("pkg.name")
  refs=$((refs + $(grep -rnE "import_module\s*\(\s*['\"].*${name}" "$PKG_DIR" \
    --include="*.py" | grep -v "^$f:" | wc -l)))

  # 3. __init__.py re-exports
  refs=$((refs + $(grep -rnE "\b${name}\b" "$PKG_DIR"/*/__init__.py 2>/dev/null \
    | grep -v "^$f:" | wc -l)))

  # 4. Entry points in pyproject.toml / setup.py / setup.cfg
  refs=$((refs + $(grep -rnE "\b${name}\b|\b${module_path}\b" \
    pyproject.toml setup.py setup.cfg 2>/dev/null | wc -l)))

  # 5. conftest.py references (fixtures, plugins)
  refs=$((refs + $(grep -rnE "\b${name}\b" "$PKG_DIR"/**/conftest.py 2>/dev/null \
    | grep -v "^$f:" | wc -l)))

  # 6. String references (dynamic loading, config files)
  refs=$((refs + $(grep -rnE "['\"]${module_path}['\"]|['\"]${name}['\"]" "$PKG_DIR" \
    --include="*.py" --include="*.toml" --include="*.cfg" --include="*.ini" --include="*.yaml" --include="*.yml" \
    | grep -v "^$f:" | wc -l)))

  # 7. Test files referencing this module
  refs=$((refs + $(grep -rnE "\b${name}\b" tests/ 2>/dev/null | wc -l)))

  if [ "$refs" -eq 0 ]; then
    echo "UNUSED: $f (0 references across all patterns)"
  fi
done
```

#### Step 1.5: Detect Function-Level Bloat

```bash
# Find stubs (functions with pass, ..., empty return, raise NotImplementedError)
grep -rnP "def\s+\w+\([^)]*\)[^:]*:\s*$" -A1 "$PKG_DIR" --include="*.py" | \
  grep -E "(pass$|\.\.\.$|return None$|return \[\]$|return \{\}$|return \"\"$|raise NotImplementedError)" | head -40

# Find thin wrappers (single-return-statement functions)
grep -rnP "def\s+\w+\(self[^)]*\)[^:]*:\s*$" -A1 "$PKG_DIR" --include="*.py" | \
  grep -E "return self\.\w+$|return self\._\w+$" | head -30

# Find duplicate function names across files
grep -rn "^\s*def " "$PKG_DIR" --include="*.py" | \
  sed 's/.*def \([a-z_0-9]*\).*/\1/' | sort | uniq -d | while read dup; do
    echo "DUPLICATE: $dup"
    grep -rn "def ${dup}" "$PKG_DIR" --include="*.py"
    echo "---"
  done

# Find commented-out code blocks (2+ consecutive commented lines with code patterns)
grep -rn "^#\s*\(def \|class \|import \|from \|return \|if \|for \|while \)" "$PKG_DIR" --include="*.py" | head -30

# Find # noqa items (INVESTIGATE, don't auto-remove)
grep -rn "# noqa" "$PKG_DIR" --include="*.py" | head -20

# Find # type: ignore items (INVESTIGATE)
grep -rn "# type: ignore" "$PKG_DIR" --include="*.py" | head -20

# Find # pragma: no cover items (INVESTIGATE)
grep -rn "# pragma: no cover" "$PKG_DIR" --include="*.py" | head -20

# Find decorator-registered functions (DO NOT REMOVE)
grep -rnB1 "^\s*def " "$PKG_DIR" --include="*.py" | \
  grep -E "@(app\.|router\.|pytest\.fixture|celery|receiver|register|hook)" | head -20
```

#### Step 1.6: Analyze and Categorize

For each flagged item, apply **The Fundamental Question**. Categorize findings:

| Category | What It Is | Action | Confidence |
| ---------------------------- | ---------------------------------------------------------------- | ---------------------------------- | --------------- |
| **Stubs** | `pass`, `...`, empty return, `NotImplementedError` (no subclass) | Remove | High |
| **Thin Wrappers** | Single `return self.x`, trivial passthrough | Remove (unless API/ABC/property) | High |
| **Duplicates** | Same logic in multiple files | Keep in owning module, remove rest | High |
| **Overengineered** | Patterns failing 3-point test | Remove | Medium — verify |
| **Unused Imports** | `import X` never referenced | Remove (ruff --fix) | High |
| **Unused Variables** | Assigned but never read | Remove or rename to `_` | High |
| **Commented Code** | `# def old_func():` blocks | Remove | High |
| **Unused Files** | 0 inbound refs (all patterns checked) | Delete | High |
| **Re-export Only** | `__init__.py` with only passthrough imports | Consolidate | Medium |
| **Maybe Unused** | 0 direct refs but string/dynamic reference possible | Manual review | Low — verify |
| **`# noqa` items** | Lint explicitly suppressed | Investigate intent | Low — ask |
| **Decorator-registered** | `@app.route`, `@pytest.fixture`, etc. | **KEEP** | N/A |
| **`TYPE_CHECKING` imports** | Type-checker-only imports | **KEEP** | N/A |
| **`try/except ImportError`** | Optional dep fallbacks | **KEEP** unless dep removed | N/A |

#### Step 1.7: Report Phase 1

Generate a per-file report:

```markdown
## Cleanup Report: <package>

### Summary

- Files scanned: X
- Functions/classes analyzed: Y
- Items flagged for removal: Z
- Estimated lines removed: N
- Formatting fixes pending: M

### Per-File Findings

#### `services/processor.py`

| Item                     | Type           | Lines | Verdict | Reason                      |
| ------------------------ | -------------- | ----- | ------- | --------------------------- |
| `get_name()`             | Thin wrapper   | 2     | REMOVE  | Direct `self.name` access   |
| `clamp()`                | Duplicate      | 3     | REMOVE  | Owned by `utils/helpers.py` |
| `process()`              | Real logic     | 22    | KEEP    | Required by FRD-012         |
| `import pandas`          | Unused import  | 1     | REMOVE  | Never referenced            |
| `# def old_transform():` | Commented code | 8     | REMOVE  | Dead comment block          |

#### `orphan_feature.py`

| Item        | Type        | Lines | Verdict | Reason                                            |
| ----------- | ----------- | ----- | ------- | ------------------------------------------------- |
| Entire file | Unused file | 87    | DELETE  | 0 inbound refs, not in entry_points, not in tests |

#### `services/api_routes.py`

| Item                    | Type                 | Lines | Verdict | Reason                      |
| ----------------------- | -------------------- | ----- | ------- | --------------------------- |
| `@app.route("/health")` | Decorator-registered | 5     | KEEP    | Flask route — not dead code |

### Items Requiring Manual Review

- `utils/legacy.py` — `# noqa` on 3 items. Developer intent unclear.
- `plugins/experimental.py` — Loaded via `importlib` in config-driven path. Verify if config still active.
- `compat/py38_shim.py` — `try/except ImportError` fallback. Is Python 3.8 still supported?

### Formatting Fixes (auto-applied by ruff/black)

- 14 unused imports removed
- 6 import order violations fixed
- 23 lines exceeding 88 chars reformatted
```

#### Step 1.8: Get Approval for Phase 1

Present report to user. Get **explicit per-file approval** before making changes.

For "Maybe Unused", `# noqa`, decorator-registered, and `TYPE_CHECKING` items, require **explicit confirmation** — do not batch-remove.

#### Step 1.9: Execute Phase 1 Cleanup

```bash
# === Auto-fixable (safe, tool-driven) ===

# Remove unused imports + fix import ordering + PEP 8 lint fixes
ruff check <package>/ --select F,E,W,I --fix --unsafe-fixes

# Format code
black <package>/ --line-length 88

# === Manual removals (after approval) ===

# Remove unused file(s)
rm <package>/orphan_feature.py

# Update __init__.py — remove imports/re-exports of deleted module
# Update __all__ — remove names of deleted functions/classes
# Update pyproject.toml / setup.py if entry_points reference deleted module
```

#### Step 1.10: Verify Phase 1

```bash
# Lint clean (ruff replaces flake8 + isort + pycodestyle + pycln)
ruff check <package>/ --select F,E,W,I 2>&1 | grep -v "All checks passed"

# Format clean
black --check <package>/ --line-length 88

# Type check (if project uses mypy/pyright)
mypy <package>/ --warn-unused-ignores --warn-unreachable 2>&1 | grep -E "error:"

# Tests pass
pytest <package>/ -x -q 2>&1 | tail -5

# Test collection (catches broken imports in test files)
pytest <package>/ --collect-only -q 2>&1 | grep -E "ERROR|error"

# Check downstream packages / full project
pytest --co -q 2>&1 | grep -E "ERROR"  # full project collection

# Verify no broken imports
python -c "import <package>" 2>&1
```

---

## Phase 2: File Consolidation

### Detection Patterns: Same-Purpose Files (Merge)

```python
parser.py
parser_utils.py
parser_helpers.py
# All parse-related → merge into parser.py
```

### Detection Patterns: Same-Domain Files (Merge)

```python
validators_email.py
validators_phone.py
validators_url.py
# All validate inputs → merge into validators.py
```

### Detection Patterns: Split Functionality (Merge)

```python
services/user_creator.py
services/user_updater.py
services/user_deleter.py
# All handle user CRUD → merge into services/user_service.py
```

### The Consolidation Pattern

#### Before Merge (Two Files)

```
my_package/services/user_creator.py
  - class UserCreator
  - Methods: create, validate_input

my_package/services/user_validator.py
  - class UserValidator
  - Methods: validate_email, validate_name
```

#### After Merge (One File)

```python
"""User service — handles creation, validation, and management."""

from my_package.shared import UserVO


class UserValidator:
    """Validates user data before persistence."""

    def validate_email(self, email: str) -> bool:
        # merged logic from UserValidator
        ...

    def validate_name(self, name: str) -> bool:
        # merged logic from UserValidator
        ...


class UserCreator:
    """Creates new user accounts."""

    def __init__(self, validator: UserValidator):
        self._validator = validator

    def create(self, data: dict) -> UserVO:
        # merged logic from UserCreator
        ...

    def validate_input(self, data: dict) -> bool:
        # merged logic from UserCreator
        ...
```

### Phase 2 Workflow

#### Step 2.1: Analyze File Responsibilities

Read files and identify related functionality:

```bash
# List classes/functions in files
grep -rn "^class \|^def " modules/*/src/ | sort
```

#### Step 2.2: Identify Consolidation Candidates

Files that should be merged:

- Multiple files with related classes (e.g., `parser.py`, `parser_utils.py`)
- Files that only import from each other
- Split functionality across multiple small files

#### Step 2.3: Pick Target File

Select the file with the most logic (most lines, most methods, most classes) as the merge target.

#### Step 2.4: Merge Related Code

Move classes/functions to target file:

```python
# Before: parser.py and parser_utils.py
# After: Single parser.py with all related code
```

**Merge carefully**: If both files define the same class/function name, keep only one (prefer the more complete version).

#### Step 2.5: Update Imports

Fix all imports across the codebase:

```bash
# Find files importing from removed modules
grep -rn "from parser_utils import" modules/
```

#### Step 2.6: Update `__init__.py` and `__all__`

```python
# Update __init__.py — remove imports of deleted module
# Update __all__ — remove names of deleted classes/functions
```

#### Step 2.7: Delete Source File(s)

Remove the file(s) whose functionality was merged:

```bash
rm my_package/services/user_validator.py
```

#### Step 2.8: Verify Phase 2

```bash
python -c "import <module>"
pytest modules/ -v
```

---

## Final Verification (Both Phases)

```bash
# Lint clean
ruff check <package>/ --select F,E,W,I 2>&1 | grep -v "All checks passed"

# Format clean
black --check <package>/ --line-length 88

# Type check
mypy <package>/ --warn-unused-ignores --warn-unreachable 2>&1 | grep -E "error:"

# Tests pass
pytest <package>/ -x -q 2>&1 | tail -5

# Verify no broken imports
python -c "import <package>" 2>&1
```

---

## Commit

```bash
git add -A
git commit -m "cleanup(<package>): remove N dead items + merge M files (K lines)

Removed:
- X stubs
- Y thin wrappers
- Z duplicate functions
- W unused files
- V unused imports
- U commented-out code blocks

Consolidated:
- A files merged into B files

Formatted: black + ruff (line-length 88)
All pytest / ruff / mypy passing."
```

---

## Verification Checklist

### Phase 1: Dead Code Cleanup

- [ ] Git snapshot created before any changes
- [ ] Working on dedicated cleanup branch
- [ ] FRD / requirements read and MVP scope understood
- [ ] `ruff check` run as primary lint/import detection
- [ ] `vulture` run for dead code detection
- [ ] File-level scan uses multi-pattern detection (import, importlib, `__init__.py`, entry_points, conftest, string refs, tests)
- [ ] Each function evaluated against Fundamental Question
- [ ] Decorator-registered functions NOT removed
- [ ] `if TYPE_CHECKING:` imports NOT removed
- [ ] `try/except ImportError` fallbacks NOT removed (unless dep confirmed gone)
- [ ] `# noqa` / `# type: ignore` / `# pragma: no cover` items investigated, not auto-removed
- [ ] `importlib` dynamic imports checked
- [ ] `conftest.py` and `pyproject.toml` entry_points checked
- [ ] Report generated showing keep/remove per file with reasons
- [ ] Approval received before making changes
- [ ] `__all__` updated when functions/classes removed
- [ ] `__init__.py` updated when modules deleted
- [ ] `ruff check <package>/` passes clean
- [ ] `black --check <package>/` passes clean
- [ ] `pytest <package>/` passes
- [ ] `python -c "import <package>"` succeeds

### Phase 2: File Consolidation

- [ ] Files analyzed and consolidation candidates identified
- [ ] Target file selected (most logic)
- [ ] Related classes/functions merged into single file
- [ ] All imports updated to reflect new structure
- [ ] `__init__.py` exports consolidated module correctly
- [ ] Source file(s) deleted
- [ ] `python -c "import <module>"` succeeds
- [ ] `pytest modules/ -v` passes

### Final

- [ ] Committed with descriptive message

---

## Quick Reference Commands

```bash
# === PHASE 1: PRIMARY DETECTION ===
ruff check <package>/ --select F,E,W,I --fix --unsafe-fixes   # lint + imports + format
vulture <package>/ --min-confidence 80                          # dead code
black --check --diff <package>/ --line-length 88                # format check

# === PHASE 1: FILE-LEVEL ORPHAN SCAN ===
# (Use the full script from Step 1.4 above)

# === PHASE 1: FUNCTION-LEVEL BLOAT ===
# Stubs:
grep -rnP "def\s+\w+\([^)]*\)[^:]*:\s*$" -A1 <package>/ --include="*.py" | \
  grep -E "(pass$|\.\.\.$|return None$|return \[\]$|return \"\"$)"

# Thin wrappers:
grep -rnP "def\s+\w+\(self[^)]*\)[^:]*:\s*$" -A1 <package>/ --include="*.py" | \
  grep -E "return self\.\w+$"

# Duplicates:
grep -rn "def " <package>/ --include="*.py" | \
  sed 's/.*def \([a-z_0-9]*\).*/\1/' | sort | uniq -d

# Commented-out code:
grep -rn "^#\s*\(def \|class \|import \|from \|return \)" <package>/ --include="*.py"

# Decorator-registered (DO NOT REMOVE):
grep -rnB1 "def " <package>/ --include="*.py" | \
  grep -E "@(app\.|router\.|pytest|celery|receiver|register)"

# noqa / type: ignore / pragma (INVESTIGATE):
grep -rn "# noqa\|# type: ignore\|# pragma: no cover" <package>/ --include="*.py"

# === PHASE 2: OVERLAP DETECTION ===
grep -rn "^class \|^def " modules/*/src/ | sort
grep -rn "^from \. import \|^import \." modules/*/src/__init__.py

# === FORMATTING ===
ruff check <package>/ --select I --fix     # sort imports
black <package>/ --line-length 88           # format
ruff check <package>/ --select E,W --fix   # PEP 8 fixes

# === VERIFICATION ===
ruff check <package>/ --select F,E,W,I     # lint clean
black --check <package>/ --line-length 88   # format clean
pytest <package>/ -x -q                     # tests pass
python -c "import <package>"                # import works
mypy <package>/ --warn-unreachable          # types clean (if applicable)

# === ROLLBACK ===
git checkout HEAD~1 -- <package>/<file>.py  # restore one file
git reset --hard HEAD~1                      # nuclear option
```

---

## Common Mistakes (AVOID)

| Mistake | Why It's Dangerous | Prevention |
| -------------------------------------------- | ---------------------------------------------------- | ------------------------------------------------------- |
| Removing real MVP logic | Breaks required functionality | Fundamental Question + FRD cross-reference |
| Removing decorator-registered functions | Breaks routes, fixtures, tasks, signal handlers | Grep for decorators before removing any function |
| Removing `if TYPE_CHECKING:` imports | Breaks mypy/pyright type checking | Exception list; never auto-remove |
| Removing `try/except ImportError` fallbacks | Breaks optional dependency support | Check `pyproject.toml` `[project.optional-dependencies]` |
| Forgetting to update `__all__` | `from pkg import *` breaks; public API inconsistency | Always edit `__all__` when removing exports |
| Forgetting to update `__init__.py` | `ImportError` at runtime | Always edit `__init__.py` when deleting modules |
| Deleting `conftest.py` | Breaks all pytest fixtures in that directory | Exception list; never auto-remove |
| Deleting migration files | Breaks migration history (Django/Alembic) | Exception list; never auto-remove |
| Removing `# noqa` items without investigating | Developer suppressed a false positive intentionally | Investigate git blame / ask author |
| Removing `importlib`-loaded modules | Runtime `ModuleNotFoundError` | Check for `import_module()` string references |
| Skipping `--all` / full test run | Misses breakage in conditional code paths | Run `pytest` full suite, not just changed files |
| Batch-removing "Maybe Unused" items | Dynamic imports or string refs may reference them | Require manual review + explicit approval |
| Keeping commented-out code "for reference" | Noise; git history preserves old code | Remove; use `git log` to recover if needed |
| Mixing import groups | PEP 8 / isort violation | ruff `--select I --fix` handles automatically |
| Ignoring line length | Black reformats unexpectedly in CI | Run `black` as part of cleanup, not just check |
| Skipping git snapshot | Cannot rollback if cleanup breaks something | Step 1.1 is non-negotiable |
| Consolidating files with dead code | Wastes effort merging code that should be deleted | Always run Phase 1 before Phase 2 |
| Forgetting to update `__init__.py` after merge | `ImportError` at runtime | Grep for old module names after merge |
| Leaving orphan references after merge | Runtime errors from stale imports | Grep for old class/function names after merge |

---

## Decision Flowchart

```
START
│
├─ PHASE 1: DEAD CODE CLEANUP
│  │
│  ├─ Item flagged for removal
│  │  │
│  │  ├─ Is it in the Exceptions list?
│  │  │  (__init__.py, conftest.py, py.typed, migrations, Protocol/ABC, etc.)
│  │  │  └─ YES → KEEP (stop)
│  │  │
│  │  ├─ Is it decorator-registered?
│  │  │  (@app.route, @pytest.fixture, @celery.task, @receiver, etc.)
│  │  │  └─ YES → KEEP (stop)
│  │  │
│  │  ├─ Is it inside `if TYPE_CHECKING:` or `try/except ImportError`?
│  │  │  └─ YES → KEEP unless dep/feature confirmed removed (stop)
│  │  │
│  │  ├─ Does it have `# noqa` / `# type: ignore` / `# pragma: no cover`?
│  │  │  └─ YES → Investigate intent. Ask author. Do NOT auto-remove. (stop)
│  │  │
│  │  ├─ Is it referenced by importlib / string-based dynamic loading?
│  │  │  └─ YES → KEEP (stop)
│  │  │
│  │  ├─ Is it referenced by entry_points / pyproject.toml / conftest?
│  │  │  └─ YES → KEEP (stop)
│  │  │
│  │  ├─ Apply Fundamental Question:
│  │  │  ├─ "Required by FRD?" → KEEP
│  │  │  ├─ "Called by FRD-required method?" → KEEP
│  │  │  ├─ "Always there / might be useful / edge case?" → REMOVE
│  │  │  └─ Unclear? → Flag for manual review (do NOT auto-remove)
│  │  │
│  │  ├─ If Overengineered pattern:
│  │  │  └─ Pass 3-point test? → REMOVE. Fail any point? → KEEP + comment.
│  │  │
│  │  ├─ If formatting issue (unused import, line length, import order):
│  │  │  └─ Auto-fix with ruff/black (no approval needed for format-only changes)
│  │  │
│  │  └─ Execute removal → Update __all__ → Update __init__.py → Verify
│  │
│  └─ Phase 1 Complete → Proceed to Phase 2
│
├─ PHASE 2: FILE CONSOLIDATION
│  │
│  ├─ Do files serve the same purpose / share the same domain?
│  │  └─ NO → Skip consolidation for these files
│  │
│  ├─ YES → Consolidate into single module:
│  │  ├─ Pick target (most logic)
│  │  ├─ Merge classes/functions
│  │  ├─ Update all imports
│  │  ├─ Update __init__.py and __all__
│  │  ├─ Delete source file(s)
│  │  └─ Verify compilation
│  │
│  └─ Phase 2 Complete → Final Verification
│
└─ FINAL VERIFICATION
   ├─ ruff check
   ├─ black --check
   ├─ mypy (if applicable)
   ├─ pytest
   ├─ python -c "import <package>"
   └─ Commit with descriptive message
```

---

## Dry-Run Mode

When user requests `--dry-run` or says "just show me what you'd remove":

1. Run Phase 1 Steps 1.1–1.6 (detection + analysis)
2. Run Phase 2 Step 2.1–2.2 (overlap detection)
3. Generate the full report (Phase 1 Step 1.7 + Phase 2 findings)
4. **Do NOT execute any deletions, edits, or format changes**
5. Present report and wait for explicit approval to proceed

This is the **default mode** for first-time runs on a package.

---

## Tool Reference

| Tool | Replaces | Purpose |
| ----------------------- | ------------------------------------------------------- | ---------------------------------------------------------------------- |
| `ruff` | flake8, isort, pycodestyle, pycln, pyupgrade, autoflake | Lint, import sorting, unused import removal, PEP 8 |
| `black` | autopep8, yapf | Code formatting (line length, spacing, quotes) |
| `vulture` | (no equivalent) | Dead code detection (unused functions, classes, variables, attributes) |
| `mypy` / `pyright` | (no equivalent) | Type checking; reveals unreachable code, unused `# type: ignore` |
| `pytest --collect-only` | (no equivalent) | Verifies all test files can be imported (catches broken refs) |
| `coverage` | (no equivalent) | Identifies code never executed (supplement to vulture) |

**Recommended `pyproject.toml` config:**

```toml
[tool.ruff]
line-length = 88
select = ["F", "E", "W", "I", "UP"]
ignore = ["E501"]  # black handles line length

[tool.ruff.isort]
known-first-party = ["<package>"]

[tool.black]
line-length = 88

[tool.vulture]
min_confidence = 80
exclude = ["venv", ".venv", "__pycache__", "migrations"]

[tool.mypy]
warn_unused_ignores = true
warn_unreachable = true
```
