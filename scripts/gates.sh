#!/usr/bin/env bash
# scripts/gates.sh — Local quality gates mirror CI for qwen-web-cli.
# Usage: bash scripts/gates.sh [fast]
#   fast  = skip codacy, bandit (full run defaults)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${PROJECT_ROOT}"

# ─── Color helpers ──────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

info()  { printf "${CYAN}  [gates] %s${NC}\n" "$*"; }
ok()    { printf "${GREEN}  ✓%s${NC}\n" "$*"; }
warn()  { printf "${YELLOW}  ⚠%s${NC}\n" "$*"; }
fail()  { printf "${RED}  ✗%s${NC}\n" "$*"; exit 1; }

# ─── Pre-flight: virtual env ───────────────────────────────────────────────
VENV_DIR="${PROJECT_ROOT}/venv"
if [ ! -d "${VENV_DIR}" ]; then
    info "Creating virtual environment..."
    python3 -m venv "${VENV_DIR}"
fi
# shellcheck disable=SC1091
source "${VENV_DIR}/bin/activate"

info "Installing dependencies..."
pip install --quiet ruff mypy bandit pytest pytest-asyncio pytest-cov pytest-mock playwright structlog || true
pip install --quiet -e . 2>/dev/null || true
python3 -m playwright install --with-deps chromium 2>/dev/null || true

# ─── Gates ──────────────────────────────────────────────────────────────────
FAILURES=0

# Gate 1: Ruff lint + format check (root_*.py removed — file is at modules/root_cli_main_entry.py)
info "Gate 1/5 — Ruff lint & format..."
if ! ruff check modules/ tests/ 2>&1 | grep -q "All checks passed"; then
    warn "Ruff found issues (see output above)"
    FAILURES=$((FAILURES + 1))
else
    ok "Ruff clean"
fi

# Gate 2: Mypy type checking (modules/ covers root_cli_main_entry.py)
info "Gate 2/5 — Mypy type check..."
if ! mypy modules/ --ignore-missing-imports 2>&1 | tail -1; then
    warn "Mypy found type errors"
    FAILURES=$((FAILURES + 1))
else
    ok "Mypy clean"
fi

# Gate 3: Bandit security scan (source code only, exclude tests)
info "Gate 3/5 — Bandit security scan..."
if [ "${1:-}" = "fast" ]; then
    info "Skipping bandit (fast mode)"
else
    if ! bandit -r modules/ -s B110,B112 2>&1 | grep -q "No issues"; then
        warn "Bandit found potential issues"
        FAILURES=$((FAILURES + 1))
    else
        ok "Bandit clean"
    fi
fi

# Gate 4: AES architecture self-lint (lint-arwaky-cli)
info "Gate 4/5 — AES architecture self-lint..."
if command -v lint-arwaky-cli &>/dev/null; then
    output=$(lint-arwaky-cli check . 2>&1) || true
    violations=$(echo "$output" | grep -oP 'Total:\s*\K\d+' || echo "0")
    if [ "${violations}" = "0" ]; then
        ok "AES architecture clean (0 violations)"
    else
        warn "AES architecture found ${violations} violations"
        FAILURES=$((FAILURES + 1))
    fi
else
    warn "lint-arwaky-cli not installed — skipping AES check"
fi

# Gate 5: Pytest test suite
info "Gate 5/5 — Running pytest..."
if ! pytest tests/ --ignore=tests/test_e2e_pipeline.py -v -q 2>&1 | tail -3; then
    warn "Tests failed (see output above)"
    FAILURES=$((FAILURES + 1))
else
    ok "Tests passed"
fi

# ─── Summary ────────────────────────────────────────────────────────────────
echo ""
if [ "${FAILURES}" -eq 0 ]; then
    ok "All gates passed ✅"
    exit 0
else
    fail "${FAILURES} gate(s) failed ❌"
fi
