"""Tests for the GitHub branch-ruleset definitions and apply helper."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
APPLY_SCRIPT = PROJECT_ROOT / "scripts" / "apply-ruleset.sh"
DEFAULT_RULESET = PROJECT_ROOT / ".github" / "rulesets" / "ruleset-main.json"
REQUIRED_CI_GATES = {
    "Format (ruff format)",
    "Lint (ruff check + mypy)",
    "Build package",
    "Tests (pytest) (3.12)",
    "Tests (pytest) (3.13)",
    "Self-Lint (lint-arwaky-cli)",
}

FAKE_GH = """#!/usr/bin/env bash
set -u
printf '%s\\n' "$*" >> "${GH_LOG}"

if [[ "${1:-}" == "auth" && "${2:-}" == "status" ]]; then
  exit "${GH_AUTH_EXIT:-0}"
fi

if [[ "${1:-}" == "api" && "${2:-}" == *"?per_page=100" ]]; then
  if [[ "${GH_LIST_EXIT:-0}" != "0" ]]; then
    echo "HTTP 403: Resource not accessible" >&2
    exit "${GH_LIST_EXIT}"
  fi
  if [[ -n "${GH_EXISTING_ID:-}" ]]; then
    printf '[{"id": %s, "name": "protect-main"}]\\n' "${GH_EXISTING_ID}"
  else
    printf '[]\\n'
  fi
  exit 0
fi

if [[ "${1:-}" == "api" ]]; then
  if [[ "${GH_MUTATE_EXIT:-0}" != "0" ]]; then
    echo "HTTP 403: Must have admin rights" >&2
    exit "${GH_MUTATE_EXIT}"
  fi
  printf '{}\\n'
  exit 0
fi

exit 2
"""


def _prepare_repo(tmp_path: Path, remote: str) -> tuple[Path, dict[str, str], Path]:
    repo = tmp_path / "repo"
    scripts_dir = repo / "scripts"
    rulesets_dir = repo / ".github" / "rulesets"
    fake_bin = tmp_path / "bin"
    scripts_dir.mkdir(parents=True)
    rulesets_dir.mkdir(parents=True)
    fake_bin.mkdir()

    shutil.copy2(APPLY_SCRIPT, scripts_dir / "apply-ruleset.sh")
    shutil.copy2(DEFAULT_RULESET, rulesets_dir / "ruleset-main.json")

    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "remote", "add", "origin", remote], cwd=repo, check=True)

    fake_gh = fake_bin / "gh"
    fake_gh.write_text(FAKE_GH, encoding="utf-8")
    fake_gh.chmod(0o755)

    gh_log = tmp_path / "gh.log"
    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{fake_bin}:{env['PATH']}",
            "GH_LOG": str(gh_log),
        }
    )
    return repo, env, gh_log


def _run_apply(repo: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", "scripts/apply-ruleset.sh"],
        cwd=repo,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )


@pytest.mark.parametrize(
    "remote",
    [
        "https://github.com/example/project.git",
        "git@github.com:example/project.git",
    ],
)
def test_detects_https_and_ssh_github_remotes(tmp_path: Path, remote: str) -> None:
    repo, env, gh_log = _prepare_repo(tmp_path, remote)

    result = _run_apply(repo, env)

    assert result.returncode == 0, result.stderr
    assert "Repo:        example/project" in result.stdout
    calls = gh_log.read_text(encoding="utf-8")
    assert "api repos/example/project/rulesets?per_page=100" in calls
    assert "api repos/example/project/rulesets -X POST" in calls


def test_updates_existing_ruleset_instead_of_creating_duplicate(tmp_path: Path) -> None:
    repo, env, gh_log = _prepare_repo(tmp_path, "https://github.com/example/project.git")
    env["GH_EXISTING_ID"] = "42"

    result = _run_apply(repo, env)

    assert result.returncode == 0, result.stderr
    assert "Updating existing ruleset (id=42)" in result.stdout
    calls = gh_log.read_text(encoding="utf-8")
    assert "api repos/example/project/rulesets/42 -X PUT" in calls
    assert "api repos/example/project/rulesets -X POST" not in calls


def test_reports_unauthenticated_gh_session(tmp_path: Path) -> None:
    repo, env, _ = _prepare_repo(tmp_path, "https://github.com/example/project.git")
    env["GH_AUTH_EXIT"] = "1"

    result = _run_apply(repo, env)

    assert result.returncode == 1
    assert "gh is not authenticated" in result.stderr


def test_reports_ruleset_list_permission_failure(tmp_path: Path) -> None:
    repo, env, _ = _prepare_repo(tmp_path, "https://github.com/example/project.git")
    env["GH_LIST_EXIT"] = "1"

    result = _run_apply(repo, env)

    assert result.returncode == 1
    assert "repository Admin role" in result.stderr


def test_reports_missing_admin_access_when_creating(tmp_path: Path) -> None:
    repo, env, _ = _prepare_repo(tmp_path, "https://github.com/example/project.git")
    env["GH_MUTATE_EXIT"] = "1"

    result = _run_apply(repo, env)

    assert result.returncode == 1
    assert "Repository Admin access is required" in result.stderr


@pytest.mark.parametrize(
    ("filename", "strict_policy", "thread_resolution"),
    [
        ("ruleset-main.json", False, False),
        ("ruleset-main-strict.json", True, True),
    ],
)
def test_rulesets_require_all_ci_gates(
    filename: str,
    strict_policy: bool,
    thread_resolution: bool,
) -> None:
    path = PROJECT_ROOT / ".github" / "rulesets" / filename
    ruleset = json.loads(path.read_text(encoding="utf-8"))
    pull_request = next(rule for rule in ruleset["rules"] if rule["type"] == "pull_request")
    status_checks = next(rule for rule in ruleset["rules"] if rule["type"] == "required_status_checks")

    assert ruleset["enforcement"] == "active"
    assert pull_request["parameters"]["required_review_thread_resolution"] is thread_resolution
    assert status_checks["parameters"]["strict_required_status_checks_policy"] is strict_policy
    assert {check["context"] for check in status_checks["parameters"]["required_status_checks"]} == REQUIRED_CI_GATES
