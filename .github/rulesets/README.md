# Rulesets — branch protection for `main`

This directory contains GitHub API definitions for the repository's branch protection rulesets. They prevent direct pushes to `main`, require every change to go through a pull request with one approval, and block merging until every required CI check passes.

The required CI gates are:

- `Format (ruff format)`
- `Lint (ruff check + mypy)`
- `Build package`
- `Tests (pytest) (3.12)`
- `Tests (pytest) (3.13)`
- `Self-Lint (lint-arwaky-cli)`

> **IMPORTANT:** These JSON files are not applied automatically. GitHub stores and enforces rulesets under **Settings → Rules**. The files in this directory are only the source of truth and must be applied with the helper script.

## Apply a ruleset

Applying a ruleset requires an authenticated `gh` CLI session and the repository **Admin** role. Write access alone is insufficient.

```bash
# Require a PR, one approval, and successful CI gates.
bash scripts/apply-ruleset.sh

# Enforce the same gates, require the branch to be up to date, and require all review threads to be resolved.
bash scripts/apply-ruleset.sh .github/rulesets/ruleset-main-strict.json
```

The script is idempotent: it updates a ruleset with the same name instead of creating a duplicate.
