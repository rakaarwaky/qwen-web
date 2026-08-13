#!/usr/bin/env bash
# scripts/apply-ruleset.sh — Apply a GitHub branch ruleset from a JSON file.
# Usage:
#   bash scripts/apply-ruleset.sh                          # applies .github/rulesets/ruleset-main.json
#   bash scripts/apply-ruleset.sh .github/rulesets/ruleset-main-strict.json
# Requirements: `gh` CLI + Admin role on the repo.
# Idempotent: updates an existing ruleset with the same `name` instead of duplicating.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${PROJECT_ROOT}"

RULESET_FILE="${1:-.github/rulesets/ruleset-main.json}"
API_VERSION="2022-11-28"

fail() {
  echo "ERROR: $*" >&2
  exit 1
}

if [[ ! -f "${RULESET_FILE}" ]]; then
  fail "ruleset file not found: ${RULESET_FILE}"
fi

if [[ -z "${REPO:-}" ]]; then
  REMOTE_URL="$(git remote get-url origin 2>/dev/null || true)"
  REMOTE_URL="${REMOTE_URL%.git}"
  REPO="$(printf '%s' "${REMOTE_URL}" | sed -E 's#^.*github\.com[:/]##')"
fi
if [[ -z "${REPO}" || ! "${REPO}" =~ ^[^/[:space:]]+/[^/[:space:]]+$ ]]; then
  fail "cannot determine repo. Set REPO=owner/repo or add a GitHub origin remote."
fi

if ! command -v python3 >/dev/null 2>&1; then
  fail "python3 is required to validate the ruleset JSON."
fi

if ! RULESET_NAME="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["name"])' "${RULESET_FILE}" 2>/dev/null)"; then
  fail "invalid ruleset JSON or missing name: ${RULESET_FILE}"
fi

echo "Repo:        ${REPO}"
echo "Ruleset:     ${RULESET_NAME}"
echo "Source file: ${RULESET_FILE}"
echo "JSON OK"

if ! command -v gh >/dev/null 2>&1; then
  fail "gh CLI is required. Install it and authenticate with a repository Admin account."
fi
if ! gh auth status >/dev/null 2>&1; then
  fail "gh is not authenticated. Run 'gh auth login' with a repository Admin account."
fi

if ! RULESETS_JSON="$(gh api "repos/${REPO}/rulesets?per_page=100" \
  -H "Accept: application/vnd.github+json" \
  -H "X-GitHub-Api-Version: ${API_VERSION}")"; then
  fail "cannot inspect repository rulesets. Verify the repo name and repository Admin role."
fi

EXISTING_ID="$(python3 -c '
import json, sys
name = sys.argv[1]
rulesets = json.load(sys.stdin)
print(next((item["id"] for item in rulesets if item.get("name") == name), ""))
' "${RULESET_NAME}" <<<"${RULESETS_JSON}")"

if [[ -n "${EXISTING_ID}" ]]; then
  echo "Updating existing ruleset (id=${EXISTING_ID})..."
  if ! gh api "repos/${REPO}/rulesets/${EXISTING_ID}" \
    -X PUT \
    -H "Accept: application/vnd.github+json" \
    -H "X-GitHub-Api-Version: ${API_VERSION}" \
    -H "Content-Type: application/json" \
    --input "${RULESET_FILE}"; then
    fail "failed to update ruleset. Repository Admin access is required."
  fi
else
  echo "Creating new ruleset..."
  if ! gh api "repos/${REPO}/rulesets" \
    -X POST \
    -H "Accept: application/vnd.github+json" \
    -H "X-GitHub-Api-Version: ${API_VERSION}" \
    -H "Content-Type: application/json" \
    --input "${RULESET_FILE}"; then
    fail "failed to create ruleset. Repository Admin access is required."
  fi
fi

echo ""
echo "Done. Verify at: https://github.com/${REPO}/rules"
