# Qwen Web Automation CLI — Project Context

## Overview

**Qwen AI Web Automation CLI** is a production-grade Python automation pipeline and MCP (Model Context Protocol) server that automates **chat.qwen.ai** prompt processing. It sends Markdown prompt files or direct text strings to Qwen AI, waits for responses, extracts output, and saves results locally — **no API key required**.

The project is currently undergoing an **AES (Agentic Engineering System) migration**, refactoring the codebase into a strict 7-layer architecture pattern designed for AI-agent-safe modification.

---

## Architecture: AES 7-Layer Pattern

### Layer Hierarchy (Bottom-Up Dependencies)

```
taxonomy → utility / contract → capabilities → agent → surface → root
```

Each layer has explicit import rules enforced by `lint-arwaky-cli`:

| Layer | Purpose | Allowed Imports | Forbidden Imports |
|-------|---------|-----------------|-------------------|
| **Taxonomy** | Stable domain language (VOs, entities, errors, constants) | Taxonomy only | Everything else |
| **Utility** | Reusable stateless functions (path ops, text parsing) | Taxonomy only | Contract, Capabilities, Agent, Surface, Root |
| **Contract** | Public interfaces (protocol ABCs, aggregate facades) | Taxonomy, Contract | Agent, Surface, Capabilities, Root |
| **Capabilities** | Business logic + external adaptation | Taxonomy, Contract, Utility | Agent, Surface, Root, other Capabilities |
| **Agent** | Orchestration only — coordinates capabilities via protocols | Taxonomy, Contract, Utility | Capabilities (direct), Surface, Root |
| **Surface** | User-facing boundary (CLI commands, MCP tools) | Taxonomy, Contract Aggregate, Utility | Agent, Capabilities, Root |
| **Root** | Composition & wiring (DI container, entry points) | All layers | None |

### File Naming Convention

`{layer}_{concern}_{role}.{ext}` — e.g. `capabilities_browser_adapter.py`, `agent_core_orchestrator.py`

---

## Workspace Structure

```
modules/                          ← Workspace members
├── shared/src/                   ← Shared taxonomy + contract + utility
│   ├── taxonomy_*.py             ← VOs, entities, errors, constants
│   ├── contract_*.py             ← Protocol ABCs, aggregate facades
│   └── utility_*.py              ← Stateless helper functions
├── core/src/                     ← Core feature module
│   ├── agent_core_orchestrator.py
│   ├── capabilities_*.py         ← 12 capability implementations
│   └── ...
├── cli/src/                      ← CLI surface commands
│   ├── surface_cli_*.py          ← init, run, login, interactive
│   └── root_cli_container.py     ← CLI DI container
├── mcp/src/                      ← MCP server tools
│   ├── surface_mcp_*.py          ← MCP tool implementations
│   └── root_mcp_container.py     ← MCP DI container
├── root_cli_main_entry.py        ← CLI entry point
└── root_mcp_main_entry.py        ← MCP server entry

tests/                            ← Comprehensive test suite
├── test_*.py                     ← Unit, integration, E2E tests
├── fixtures/                     ← Production-mirrored DOM fixtures
├── conftest.py                   ← Golden task content, shared fixtures
└── smoke_qwen_auto.py           ← Regression lock (behavior locked)

lint_arwaky.config.yaml          ← AES architecture enforcement rules
pyproject.toml                   ← Build, Ruff, MyPy config
requirements.txt                 ← Runtime dependencies
```

---

## Building & Running

### Installation

```bash
git clone https://github.com/rakaarwaky/qwen-web.git
cd qwen-web
pip install -r requirements.txt
python3 -m playwright install chromium
```

### CLI Usage

```bash
# Interactive mode (menu-driven)
python3 src/main.py

# Watcher mode (continuous input/ monitoring)
python3 src/main.py --watch --headless

# Batch folder processing
python3 src/main.py -i input -o output --headless

# Single file processing
python3 src/main.py -i prompt.md -o output/result.md --headless

# MCP server mode
python3 src/main.py --mcp

# Manual login (first run)
python3 src/main.py --login
```

### Running Tests

```bash
# Full suite (behavior + pipeline)
pytest tests/ -v

# Behavior regression lock only (fast, ~90s headless)
pytest tests/test_qwen_client_behavior.py -v

# E2E tests (requires live network + auth session)
pytest tests/ -m e2e -v

# Slow tests (>5s each)
pytest tests/ -m slow -v
```

---

## Development Conventions

### AES Architecture Enforcement

- **`lint-arwaky-cli`** enforces 24+ AES rules (AES101–AES506) covering naming, import boundaries, quality gates, role violations, and orphan detection.
- **Import rule #1**: Capabilities must never import other capabilities. Agent must depend on Contract protocols, not concrete implementations.
- **Max 3 types per file** in agent layer; max 30 functions in capabilities.
- **No primitive types** in contract method signatures — use taxonomy VOs only.

### Testing Strategy

1. **Behavior Regression Lock** (`tests/TEST.md`): Pinned DOM selectors, JS injection strategies, and response-detection behavior verified against live Qwen UI (Qwen3.8-Max, August 2026).
2. **Production Mirrored Fixtures**: `tests/fixtures/` mirrors exact directory structure (`input/`, `output/`, `log/`) with golden task content.
3. **Three tiers of test coverage**: Unit → Integration → E2E (marked with pytest markers).

### Code Quality Tools

| Tool | Config | Purpose |
|------|--------|---------|
| **Ruff** | `pyproject.toml[tool.ruff]` | Linting, auto-formatting |
| **MyPy** | `pyproject.toml[tool.mypy]` | Strict type checking |
| **Bandit** | `.bandit` (via lint config) | Security vulnerability scanning |
| **Codacy** | Local scan via `codacy-analysis` | Static analysis pipeline |

### Codacy Local Scan (Source Code Only)

```bash
# Source-only scan (excludes tests/ via --files)
codacy-analysis analyze --files "modules/**/*.py" root_*.py --output-format json

# Full scan (includes tests — 508+ test issues, mostly intentional patterns)
codacy-analysis analyze --output-format json
```

**Test files excluded via `.codacy.yaml`** (`exclude_paths: tests/**`) for cloud scanning. Source code shows **20 violations**: Bandit B110/B112 (9), Prospector unused imports/vars (6), PyLint redefined builtins (3), Semgrep permissions (1), Agentlinter doc issues (2).

---

## Key Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `playwright` | >=1.62 | Browser automation (Chromium) |
| `structlog` | >=26.1 | Structured logging |
| `sentry-sdk` | >=2.66 | Error tracking |
| `opentelemetry-*` | >=1.44 | Distributed tracing |
| `tenacity` | >=9.1 | Retry/circuit breaker |
| `mcp` | >=2.0 | Model Context Protocol server |

---

## Current Migration State (AES Migration)

- **Branch**: `aes-migration` (worktree at `.herdr/worktrees/qwen-web-arwaky/aes-migration`)
- **Goal**: Complete AES layer migration with compliance-driven auth middleware rewrite
- **Compliance Driver**: Legal requirement — session token storage must meet new standards
- **Merge Freeze**: Began 2026-03-05 for mobile release cut

### Recent Linter Results

Scan shows **4 violations** (all linter limitations — time import AST, Python typing.Any/dict, utility function in constant file). Code complies with AES standards despite lint anomalies.

---

## Agent Interaction Guidelines

- **Lean-CTX active**: Use `ctx_*` MCP tools instead of native equivalents for reading, searching, and shell commands.
- **Ponytail mode**: Prefer the simplest working solution — reuse existing patterns, avoid over-engineering.
- **AES-first**: When modifying code, verify layer boundaries and naming conventions before committing changes.
- **Tests are regression locks**: Behavior tests must pass before merging; they pin verified Qwen UI DOM selectors.
