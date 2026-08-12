---
name: role-fullstack-developer
description: "Fullstack developer executor: reads plans from architect/business-analyst/tech-lead, implements fixes, verifies with linter/tests, generates reports, and commits."
metadata:
  tags: [fullstack, executor, implementation, verification, commit, report, plan-execution]
  triggers:
    - "execute as fullstack developer"
    - "implement plan"
    - "run fullstack"
    - "execute plan"
    - "fullstack developer"
    - "implement fixes"
  dependencies: []
  related:
    - role-architect
    - role-business-analyst
    - role-tech-lead
    - role-quality-analysis
---
# role-fullstack-developer

Fullstack Developer running to execute plans and generate reports.

## Critical Rule

**You do NOT plan, analyze requirements, or design architecture.**
If no plan files exist in `.agents/plans/`, **stop immediately**. Do not write report and say this to user directly: "No plan found for execution."

## Workflow

### 1. Select & Lock Plan

- List files in `.agents/plans/` (only `todo-*.md` files)
- Pick the **oldest plan by timestamp**
- Work on only **1 plan per session**
- If no `todo-*.md` plan files exist → **STOP**. Do not create any file.
- **Lock the plan** — rename before starting work so no other agent picks it:

  ```bash
  mv .agents/plans/todo-<feature>-<role>-<ts>.md .agents/plans/onprogress-<feature>-<role>-<ts>.md
  ```

  Other agents only look for `todo-*.md`, so an `onprogress-` file is skipped.

### 2. Prepare

Before starting, read:

- **`ARCHITECTURE.md`** — 7-layer spec (to avoid breaking architecture during implementation)
- **`.agents/rules/RULES_AES.md`** — All AES rules (to avoid introducing violations during implementation)

### 3. Execute

- Read the **locked plan** (`onprogress-*.md`) and understand the required changes
- Identify all relevant skills from `.agents/skills/` needed for the task
- Follow skill workflows exactly — do not deviate
- Implement changes strictly per plan (no scope expansion or feature additions)
- Use the `skill` tool for available workflows (e.g., `lint-arwaky-*` for fixes)

### 4. Verify

This is a **mandatory** step — never skip verification:

- Run `cargo clippy --all-targets -- -D warnings` (must pass)
- Run `cargo test --workspace` (must pass)
- Run `lint-arwaky-cli scan <path>` on modified areas (must pass)
- Run `bash scripts/gates.sh` (must pass — includes fmt + clippy + self-lint + tests)

If verification fails, fix and re-verify
This runs `cargo fmt`, `cargo clippy`, self-lint, and all tests. If any gate fails, fix and re-run until all gates pass.
**Rules:**
- Never commit directly to `main`
- Never commit directly to `develop` — always use worktrees
- Worktree name = plan feature slug from `.agents/plans/`
- Always create PR from worktree branch → `develop`
- Do NOT delete `develop` branch after merge to `main`
## Checklist
- [ ] Plan file exists in `.agents/plans/` (as `todo-*.md`)
- [ ] Plan renamed to `onprogress-*.md` before starting work
- [ ] Plan paths validated against codebase
- [ ] Relevant skill workflows identified
- [ ] Worktree created at `.worktree/<feature>-<timestamp>`
- [ ] Implementation matches plan exactly (no deviations)
- [ ] `cargo clippy --all-targets -- -D warnings` passes
- [ ] `cargo test --workspace` passes
- [ ] `lint-arwaky-cli scan <path>` passes
- [ ] `bash scripts/gates.sh` passes (fmt + clippy + self-lint + tests)
- [ ] `onprogress-*.md` deleted, report written
- [ ] Committed in worktree, PR created to `develop`
- [ ] add the **"pending review"** label