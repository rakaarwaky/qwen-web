com

---
name: codacy-review
description: "Codacy quality workflow: local analysis (codacy-analysis), cloud dashboard queries (issues/findings/PR via codacy CLI), and PR code review enriched with Codacy data. Use whenever the user mentions Codacy, wants to check issues or security findings, review a PR with Codacy data, reduce false positives, or interact with Codacy Cloud."
license: MIT
metadata:
  author: Codacy
  version: 1.0.0
---
# Codacy Review

One skill for the full Codacy workflow: **local analysis**, **cloud queries**, and **PR review**. Two CLIs share credentials at `~/.codacy/credentials`:

- `codacy` (Cloud CLI) — remote data: issues, findings, PR analysis, coverage
- `codacy-analysis` (Analysis CLI) — local static analysis without pushing

## Prerequisites

```bash
codacy info                     # verify Cloud CLI auth
codacy-analysis --help 2>&1 | head -1
```

Auth: `codacy login` or `export CODACY_API_TOKEN=<token>` (token from Codacy > My Account > Access Management > API Tokens). Both CLIs share the same session. Inside a repo, provider/org/repo are auto-detected from the git remote — most commands work with short forms like `codacy issues`.

## Workflow A: Local analysis (before push)

```bash
codacy-analysis init --default              # first time only; merges .codacy.yaml excludes
codacy-analysis analyze --pr --output-format json          # changes vs PR target branch
codacy-analysis analyze --diff --output-format json        # changes vs merge base
codacy-analysis analyze --staged --output-format json      # staged only
codacy-analysis analyze --tool Ruff --files "src/**/*.ts" --output-format json
```

Use `--install-dependencies` to fetch missing tool binaries (installed under `~/.codacy/`). Exit codes: 0 = clean, 1 = issues found, 2 = execution error. Parse `.issues[]` with severity/file; check `.capability.unavailable` for tools only available in Cloud.

## Workflow B: Cloud queries & dashboard

```bash
codacy info                                        # account / orgs
codacy issues --overview                           # totals by category/severity/language + noise suggestions
codacy issues --severities Critical,High           # filter: --branch --patterns --categories --tools --authors
codacy issue <issueId>                             # single issue detail (pattern docs + code context)
codacy findings --severities Critical,High         # security findings (SAST/SCA/Secrets)
codacy finding <findingId>                         # single finding (CVE data, affected functions)
codacy repository                                  # dashboard: metrics, PRs, issues
codacy repository --reanalyze-and-wait             # trigger reanalysis, block until done
codacy tools / codacy patterns <tool>              # inspect enabled tools/patterns
```

Handle noise (false positives):

```bash
codacy issue <issueId> --ignore --ignore-reason FalsePositive --ignore-comment "..."
codacy issues --severities Minor --categories CodeStyle --ignore   # bulk ignore
codacy issue <issueId> --unignore
```

Config changes (enable/disable tools/patterns) only take effect after the next analysis — trigger `--reanalyze-and-wait` or wait for the next commit.

## Workflow C: PR review with Codacy data

1. **Context**: fetch PR title/description + linked ticket from the source provider.
2. **Local analysis** of PR changes (fast, no push needed): `codacy-analysis analyze --pr --output-format json`.
3. **Cloud PR data**: `codacy pull-request <prNumber>` → up-to-standards status, coverage delta, complexity/duplication delta. Use `--diff` for annotated diff with coverage. If stale, `codacy pull-request <prNumber> --reanalyze-and-wait`.
4. **Issues introduced**: combine local + cloud results; flag Critical/High as blockers. Ignore false positives via the ignore commands above (`codacy pull-request <prNumber> --ignore-issue <id>`).
5. **Coverage**: flag files with new uncovered lines.
6. **Alignment**: does the code match the ticket and PR description? Note scope gaps.
7. **Test plan**: scenarios from changed code; flag missing tests.
8. **Summary**: quality gate, issues introduced, coverage delta, alignment, test plan, suggested improvements.

If another review skill (e.g. `coderabbit-review`) already ran, append a Codacy data section instead of replacing its findings.

## Reanalysis

`codacy repository --reanalyze-and-wait` captures a baseline, triggers analysis, polls every 10s (max 20 min), and reports issue deltas by pattern/severity/category. Use `-o json` for a machine-readable delta report. Fire-and-forget: `--reanalyze` (check completion by re-running without the flag: "Reanalysis in progress..." vs "Finished X ago").

## Reminders

- Data reflects the HEAD commit — no per-line historical view.
- Organization-level coding standards cannot be overridden per-repository; update the standard instead.
- `--output json` (`-o json` / `--output-format json`) is preferred for agentic workflows.
