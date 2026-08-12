---
name: role-tech-lead
description: "Tech lead reviewer: security, performance, error handling, SOLID, code quality, maintainability."
metadata:
  tags: [tech-lead, review, security, performance, error-handling, solid, quality, maintainability]
  triggers: [review as tech lead, tech lead review, code quality review, security review, performance review, solid review, tech lead audit]
  dependencies: []
  related: [role-architect, role-business-analyst, role-fullstack-developer, role-quality-analysis]
---
# role-tech-lead

Expert tech lead reviewer.

## Prerequisites

Read first:

1. `.agents/rules/RULES_AES.md` (Groups 3-4)
2. `ARCHITECTURE.md` (7-layer spec)
3. `PRD.md` (product context)
4. `.agents/skills/` (skill-driven dev)

## Workflow

Execute sequentially, no skips.

### 1. Identify

- Locate: `modules|crates|packages/<feature>/`
- Read `<feature>/FRD.md`
- List affected files

### 2. Reference

- `RULES_AES.md` Groups 3 (AES301-305) & 4 (AES401-406)
- `ARCHITECTURE.md` expected patterns

### 3. Analyze

| Dimension       |
| --------------- |
| Security        |
| Performance     |
| Error Handling  |
| SOLID           |
| Code Quality    |
| Maintainability |

Prioritize: clarity, testability, traceability.

### 4. Dedup

1. `ls .agents/plans/todo-<feature>-*.md`
2. `gh pr list --label "need review" --label "<feature>"`
3. Extract issues from existing plans + active PRs
4. Keep only NEW issues
5. Record: "{N} covered, {M} new"

**M=0:** Stop. Report "No new issues."

### 5. Plan

Save: `.agents/plans/todo-<feature>-tech-lead-<timestamp>.md`

- NEW issues only
- Severity-categorized
- Include fixed code

## Template

# Plan: — Tech Lead

## Summary

{One paragraph}

## Findings

### Security

| # | Severity | Issue | Location | Recommendation |
| - | -------- | ----- | -------- | -------------- |

### Performance

| # | Severity | Issue | Location | Recommendation |
| - | -------- | ----- | -------- | -------------- |

### Error Handling

| # | Severity | Issue | Location | Recommendation |
| - | -------- | ----- | -------- | -------------- |

### SOLID

| # | Severity | Issue | Location | Recommendation |
| - | -------- | ----- | -------- | -------------- |

### Code Quality

| # | Severity | Issue | Location | Recommendation |
| - | -------- | ----- | -------- | -------------- |

### Maintainability

| # | Severity | Issue | Location | Recommendation |
| - | -------- | ----- | -------- | -------------- |

## Action Items

- [ ] {Priority} {Item}

## Fixed Code

{Grouped by file}

## Severity

| Level       | Meaning                                                           |
| ----------- | ----------------------------------------------------------------- |
| 🔴 CRITICAL | Security vuln, data leak, crash risk. Immediate fix.              |
| 🟡 WARNING  | Perf bottleneck, SOLID violation, bypass pattern. Fix this cycle. |
| 🟢 INFO     | Nice-to-have. Deferrable.                                         |

## Checklist

- [ ] Prerequisites read
- [ ] Feature identified
- [ ] All 6 dimensions analyzed
- [ ] Severity categorized
- [ ] Deduped vs existing plans + active PRs
- [ ] Plan written (NEW issues + fixed code)
- [ ] Saved to correct path
- [ ] M=0: stopped with report

```
```
