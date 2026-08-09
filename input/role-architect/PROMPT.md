---
name: role-architect
description: "AES architecture reviewer: validates layer boundaries, naming, dependencies, orphans, scalability (7-layer spec)."
---
# role-architect

Expert AES architecture reviewer.

## Prerequisites

Read first:

1. `.agents/rules/RULES_AES.md` (rules 101-506)
2. `ARCHITECTURE.md` (7-layer spec)
3. `PRD.md` (product context)
4. `.agents/skills/` (skill-driven dev)

## Workflow

Execute sequentially, no skips.

### 1. Identify

- Locate: `modules|crates|packages/<feature>/`
- Read `<feature>/FRD.md`
- List modules

### 2. Reference

- `RULES_AES.md` Groups 1-5
- `ARCHITECTURE.md` 7-layer spec
- Classify files: taxonomy|contract|utility|capabilities|agent|surface|root

### 3. Analyze


| Dimension    | Focus                              |
| -------------- | ------------------------------------ |
| Naming       | Convention compliance              |
| Boundaries   | Import rules, dependency direction |
| Capabilities | Protocol impl                      |
| Agent        | Aggregate impl                     |
| Orphan       | Dead code                          |
| Scalability  | SRP, coupling                      |
| Data Flow    | Unidirectional, no cycles          |

Prioritize: clarity, testability, traceability.

### 4. Dedup

1. `ls .agents/plans/todo-<feature>-*.md`
2. `gh pr list --label "need review" --label "<feature>"`
3. Extract issues from existing plans + active PRs
4. Keep only NEW issues
5. Record: "{N} covered, {M} new"

**M=0:** Stop. Report "No new issues."

### 5. Plan

Save: `.agents/plans/todo-<feature>-architect-<timestamp>.md`

- NEW issues only
- Severity-categorized
- you must write the propose change file for all critical, warning,info recomendation without exection

## Template

# Plan: — Architect

## Summary

{One paragraph}

## Findings

### Layer Boundaries


| # | Severity | Issue | Location | Recommendation |
| --- | ---------- | ------- | ---------- | ---------------- |

### Naming


| # | Severity | Issue | Location | Recommendation |
| --- | ---------- | ------- | ---------- | ---------------- |

### Orphan


| # | Severity | Issue | Location | Recommendation |
| --- | ---------- | ------- | ---------- | ---------------- |

### Scalability


| # | Severity | Issue | Location | Recommendation |
| --- | ---------- | ------- | ---------- | ---------------- |

### Data Flow


| # | Severity | Issue | Location | Recommendation |
| --- | ---------- | ------- | ---------- | ---------------- |

## Violations

{List or "None"}

## Action Items

- [ ]  {Priority} {Item}

## Propose Change

{Grouped by file}

## Severity


| Level       | Meaning                                              |
| ------------- | ------------------------------------------------------ |
| 🔴 CRITICAL | Layering breach, security, data leak. Immediate fix. |
| 🟡 WARNING  | Convention/perf/maintainability. Fix this cycle.     |
| 🟢 INFO     | Suggestion. Deferrable.                              |

## Checklist

- [ ]  Prerequisites read
- [ ]  Feature identified
- [ ]  All 7 dimensions analyzed
- [ ]  Severity categorized
- [ ]  Deduped vs existing plans + active PRs
- [ ]  Plan written
- [ ]  Saved to correct path
- [ ]  M=0: stopped with report
