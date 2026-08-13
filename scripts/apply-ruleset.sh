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

if [[ ! -f "${RULESET_FILE}" ]]; then
  echo "ERROR: ruleset file not found: ${RULESET_FILE}" >&2
  exit 1
fi

if [[ -z "${REPO:-}" ]]; then
  REMOTE_URL="$(git remote get-url origin 2>/dev/null || true)"
  REMOTE_URL="${REMOTE_URL%.git}"
  REPO="$(printf '%s' "${REMOTE_URL}" | sed -E 's#^.*github\.com[:/]##')"
fi
if [[ -z "${REPO}" ]]; then
  echo "ERROR: cannot determine repo. Set REPO=owner/repo or add an origin remote." >&2
  exit 1
fi

RULESET_NAME="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["name"])' "${RULESET_FILE}")"

echo "Repo:        ${REPO}"
echo "Ruleset:     ${RULESET_NAME}"
echo "Source file: ${RULESET_FILE}"

python3 -c 'import json,sys; json.load(open(sys.argv[1])); print("JSON OK")' "${RULESET_FILE}"

EXISTING_ID="$(gh api "repos/${REPO}/rulesets?per_page=100" \
  --jq ".[] | select(.name==\"${RULESET_NAME}\") | .id" | head -n1)"

if [[ -n "${EXISTING_ID}" ]]; then
  echo "Updating existing ruleset (id=${EXISTING_ID})..."
  gh api "repos/${REPO}/rulesets/${EXISTING_ID}" \
    -X PUT \
    -H "Accept: application/vnd.github+json" \
    -H "X-GitHub-Api-Version: ${API_VERSION}" \
    -H "Content-Type: application/json" \
    --input "${RULESET_FILE}"
else
  echo "Creating new ruleset..."
  gh api "repos/${REPO}/rulesets" \
    -X POST \
    -H "Accept: application/vnd.github+json" \
    -H "X-GitHub-Api-Version: ${API_VERSION}" \
    -H "Content-Type: application/json" \
    --input "${RULESET_FILE}"
fi

echo ""
echo "Done. Verify at: https://github.com/${REPO}/rules"
