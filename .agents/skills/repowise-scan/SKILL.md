---
name: repowise-scan
description: "Run repowise CLI for codebase intelligence — dead code, code health, change risk, security scan, and search. Use the self-hosted CLI instead of the hosted MCP endpoint so exclusions (.repowiseIgnore) apply and results reflect production code only."
metadata:
  tags: [repowise, dead-code, code-health, risk, security, scan, intelligence, cleanup]
  triggers:
    - "repowise scan"
    - "dead code"
    - "code health"
    - "change risk"
    - "security scan repowise"
    - "vulnerability repowise"
    - "codebase intelligence"
  dependencies:
    - cleanup-consolidate-rust
    - cleanup-consolidate-python
    - cleanup-consolidate-typescript
  related:
    - lint-arwaky-rust
    - role-architect
    - role-tech-lead
---

# repowise-scan — Self-Hosted Codebase Intelligence via CLI

Use the **local repowise CLI** (not the hosted MCP endpoint) so repository exclusions
(`.repowiseIgnore`, `.repowise/config.yaml exclude_patterns`, `.gitignore`) apply and
findings reflect production code only. The hosted endpoint at `api.repowise.dev`
does not reindex on the free plan (no auto-sync) and can still report fixture files.

## Preflight

Verify the CLI is installed and indexed:

```bash
repowise doctor        # all checks OK
repowise status        # last sync commit, index storage
```

If not indexed yet, run a fast structural index (no LLM, no cost):

```bash
repowise init --no-prose -y --mode fast
```

## 1. Dead code

```bash
# Table (default)
repowise dead-code

# JSON (best for agents — parse with python)
repowise dead-code --format json 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(d)"

# High-confidence, safe-to-delete only
repowise dead-code --safe-only

# Filter by kind
repowise dead-code --kind unreachable_file
repowise dead-code --kind unused_export
repowise dead-code --kind unused_internal
repowise dead-code --kind zombie_package
```

**Interpretation:**
- `unreachable_file` at confidence ≤ 0.40 for `crates/root_*_main_entry.rs` → **false positive** — these are Rust binary entry points (`fn main()`, declared in `Cargo.toml` `[[bin]]`). Repowise does not mark Cargo `[[bin]]` as `is_entry_point`, so they read as unreachable (known issue: repowise-dev/repowise#666 for the Python analogue; Rust binaries have the same gap). Never delete them.
- `zombie_package` on a workspace root like `crates/` → **false positive** (it is the workspace itself).
- Fixture paths (`workspaces-bad/`, `workspaces-good/`) should **never appear** — if they do, the exclude is not applied (see §6).

## 2. Code health

```bash
repowise health                        # repo-level KPIs + worst files
repowise health --format json 2>/dev/null | python3 -m json.tool
repowise health --include-internals    # include private-symbol findings
```

Key signals: `defect`, `maintainability`, `performance` scores per file; `band`
(`alert` = worst). Cross-check hotspots:

```bash
repowise health 2>&1 | grep -i hotspot
```

## 3. Change risk

```bash
# Risk of a specific commit or branch
repowise risk <commit-sha-or-ref>
repowise risk HEAD~3..HEAD

# Hotspot assessment for a file (uses the graph)
repowise risk --help   # see available flags for file mode
```

## 4. Security scan (local)

The self-hosted CLI has its own pattern scan (independent of the hosted Pro security suite). Note the subcommand shape:

```bash
# Working tree scan (already runs during init/update; this persists findings)
repowise security scan --output json

# Full git history — leaked secrets / risky patterns later removed
repowise security scan --history --output json
repowise security scan --history --all-patterns --output json   # incl. code smells
```

For dependency CVEs the project also has native adapters — prefer these when present:

```bash
cargo audit                  # Rust CVE scan (in crates/)
lint-arwaky-cli security crates/    # Bandit + Cargo Audit + ESLint Security
lint-arwaky-cli dependencies crates/
```

## 5. Search & questions

```bash
repowise search "concept or symbol"    # semantic + symbol search
repowise export --format md --help     # wiki/architecture export options
```

## 6. Exclusions (fixture/non-production)

Ensure the repo has the committed ignore layers so results stay clean:

- `.repowiseIgnore` (gitignore syntax) — the primary committed exclusion
- `.repowise/config.yaml` → `exclude_patterns` (local only; `.repowise/` is a local cache, not committed except `bot.yaml`)
- `.gitignore`

Verify an exclusion actually took effect:

```bash
# Should print "0" — fixture paths must not be indexed
repowise dead-code 2>&1 | grep -c "workspaces-bad" 
```

If fixture files still appear, re-index locally:

```bash
repowise init --no-prose -y --mode fast --force
```

## 7. Local dashboard (optional)

```bash
repowise serve     # web UI at http://localhost:3000
```

## 8. Workflow: Clean dead code findings

1. **Scan**: `repowise dead-code --format json` → parse with python, list findings.
2. **Filter false positives**: skip `crates/root_*_main_entry.rs`, workspace-root `zombie_package`, anything in fixtures.
3. **Verify each real finding** in source (grep for importers/usage).
4. **Fix**: remove the dead symbol/file, or wire it up if it should be live.
5. **Re-scan**: `repowise dead-code` count should drop; `git grep` confirms no references.
6. **Run tests**: `cargo nextest run --workspace --lib --tests` or per-package equivalents.

## Notes

- `repowise dead-code` re-parses files on each call; `repowise get_dead_code` via MCP reads the index. Both respect `.repowiseIgnore` now.
- The hosted MCP endpoint (`api.repowise.dev`) needs a dashboard **re-sync** to pick up exclude changes (free plan: no auto-sync). Prefer the local CLI for reproducible results.
- Never commit `.repowise/` cache files; only `.repowise/bot.yaml` and `.repowiseIgnore` are meant to be version-controlled.
