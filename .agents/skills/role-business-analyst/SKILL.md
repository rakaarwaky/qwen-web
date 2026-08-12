---
name: role-business-analyst
description: "Expert business analyst: validates requirements clarity, business flow, logic implementation, testability, and FRD-to-code traceability."
metadata:
  tags: [business-analyst, requirements, flow, traceability, frd, logic, testability, acceptance]
  triggers: [review as business analyst, business analysis, check requirements, validate requirements, business analyst review, requirements audit, frd traceability]
  dependencies: []
  related: [role-architect, role-tech-lead, role-fullstack-developer, role-quality-analysis]
---

# role-business-analyst

Expert business logic engineer and requirements analyst.

## Prerequisites

Read first:
1. `.agents/rules/RULES_AES.md` (architectural constraints)
2. `ARCHITECTURE.md` (7-layer context)
3. `PRD.md` (product context)
4. `.agents/skills/` (skill-driven dev)

## Workflow

Execute sequentially, no skips.

### 1. Identify
- Locate: `modules|crates|packages/<feature>/`
- Read `<feature>/FRD.md`
- List modules + responsibilities

### 2. Reference
- `RULES_AES.md` Groups 2 & 4 (import + role constraints)
- Map each FRD requirement to code files
- Rule: 1 FR = 1 capabilities file + 1 contract protocol (surface features excepted)

### 3. Analyze

| Dimension | Focus |
|-----------|-------|
| Requirements Clarity | Unambiguous, complete, consistent |
| Business Flow | Matches spec, edge cases handled |
| Logic Implementation | FRD→code correct, no missing paths |
| Testability | Verifiable, acceptance criteria defined |
| Traceability | FRD→code/tests/config traceable |

Prioritize: clarity, testability, traceability.

### 4. Dedup

1. `ls .agents/plans/todo-<feature>-*.md`
2. `gh pr list --label "need review" --label "<feature>"`
3. Extract issues from existing plans + active PRs
4. Keep only NEW issues
5. Record: "{N} covered, {M} new"

**M=0:** Stop. Report "No new issues."

### 5. Plan

Save: `.agents/plans/todo-<feature>-business-analyst-<timestamp>.md`
- NEW issues only
- Severity-categorized
- Include fixed code
- Modular file per feature-member if multiple features

## Template

# Plan: {feature} — Business Analyst

## Summary
{One paragraph}

## Findings

### Requirements Clarity
| # | Severity | Issue | Location | Recommendation |
|---|----------|-------|----------|----------------|

### Business Flow
| # | Severity | Issue | Location | Recommendation |
|---|----------|-------|----------|----------------|

### Logic Implementation
| # | Severity | Issue | Location | Recommendation |
|---|----------|-------|----------|----------------|

### Testability & Acceptance
| # | Severity | Issue | Location | Recommendation |
|---|----------|-------|----------|----------------|

### Traceability (FRD→Code)
| # | Severity | Issue | Location | Recommendation |
|---|----------|-------|----------|----------------|

## Violations
{List or "None"}

## Action Items
- [ ] {Priority} {Item}

## Fixed Code
{Grouped by file}

## Severity

| Level | Meaning |
|-------|---------|
| 🔴 CRITICAL | Missing core requirement, wrong logic, data integrity risk. Immediate fix. |
| 🟡 WARNING | Ambiguous requirement, missing edge case, incomplete criteria. Fix this cycle. |
| 🟢 INFO | Suggestion or optimization. Deferrable. |

## Checklist

- [ ] Prerequisites read
- [ ] Feature + modules identified
- [ ] FRD mapped to code files
- [ ] All 5 dimensions analyzed
- [ ] Severity categorized
- [ ] Deduped vs existing plans + active PRs
- [ ] Plan written (NEW issues + fixed code)
- [ ] Saved to correct path
- [ ] M=0: stopped with report
```