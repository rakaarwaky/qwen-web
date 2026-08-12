---
name: add-docs-python
description: "Add proper docstrings, type hints, and crate-level PRD.md/FRD.md/README.md to Python packages following PEP 257 and project conventions."
metadata:
  tags: [python, docs, docstring, type-hints, prd, frd, readme, pep257]
  triggers:
    - "add docs python"
    - "add docstring python"
    - "add type hints python"
    - "add prd python"
    - "add frd python"
    - "add package readme python"
  dependencies: []
  related:
    - cleanup-consolidate-python
    - add-docs-rust
---

# add-docs-python

## Purpose

Add documentation at correct locations following project conventions.

## Document Location Matrix

| Document  | Location            | Audience                     | Focus                |
| --------- | ------------------- | ---------------------------- | -------------------- |
| PRD.md    | Root workspace      | Stakeholder, PM, Design, Eng | _What_ & _Why_       |
| README.md | Root workspace      | Developer (new/existing)     | _How to use/run_     |
| FRD.md    | Each feature module | Engineer, QA, Tech Lead      | _How_ (functionally) |

## Rules

- **PRD.md** = Product Requirements Document — **1 per project root** — describes **WHAT** and **WHY** for stakeholders.
- **README.md** = Developer onboarding — **1 per project root** — describes **HOW TO USE/RUN** for developers.
- **FRD.md** = Functional Requirements Document — **1 per feature module** — describes **HOW** (functionally) for engineers.
- Relationship: **PRD (what/why) → FRD (how) → README (how to use)**. Each serves a different audience.
- All public classes and functions MUST have docstrings (PEP 257).
- Docstrings MUST explain "what" and "why", not "how" (code shows how).

## Templates

### PRD.md

```markdown
# PRD — <project-name>

## Problem Statement

<One paragraph: what problem does this project solve?>

## Goals & Success Metrics

- Goal 1: <measurable outcome>
- Goal 2: <measurable outcome>

## User Personas

- **Persona 1**: <who they are, what they need>
- **Persona 2**: <...>

## Scope

- In scope: <...>
- Out of scope: <...>

## Feature Requirements (Prioritized)

### P0 — Must Have

- [ ] <feature with acceptance criteria>

### P1 — Should Have

- [ ] <feature with acceptance criteria>

### P2 — Nice to Have

- [ ] <feature with acceptance criteria>

## Non-functional Requirements (High-level)

- Performance: <...>
- Security: <...>
- Scalability: <...>

## Open Questions / Risks

- <question or risk>

```

### FRD.md

```markdown
# FRD — <feature-name>

## System Overview

<Architecture diagram or high-level description>

## Functional Requirements

### FR-001: <Feature Name>

- **Description**: <what it does>
- **Input**: <input data>
- **Output**: <output data>
- **Business Rules**: <validation logic>
- **Edge Cases**: <edge case handling>
- **Error Handling**: <error scenarios>

### FR-002: <Feature Name>

- ...

## API Contract

| Operation | Input | Output | Description |
|-----------|-------|--------|-------------|
| `<name>`  | ...   | ...    | ...         |

## Integration Points

- **3rd Party**: <service name, purpose>
- **Internal**: <service name, purpose>

## Non-functional Requirements (Detailed)

- Performance: <response time, throughput>
- Security: <auth, encryption, compliance>
- SLA: <availability, uptime>

## Test Scenarios / QA Checklist

- [ ] <test scenario with expected result>

## Assumptions & Constraints

- <assumption or constraint>

## Glossary

- **Term**: <definition>

## Reference

- PRD: <link to root PRD.md>

```

### README.md

```markdown
# <project-name>

> One-liner: what this project does and who it's for.

## Prerequisites

- Python 3.10+
- <other dependencies>

## Quick Start

```bash
git clone ...
cd <project>
pip install -e .
python -m <package>
```

## Architecture

<High-level diagram or link to full docs>

## Project Structure

```
modules/
├── feature-a/
│   └── FRD.md        # feature specs
├── feature-b/
│   └── FRD.md        # feature specs
└── ...
```

## Available Scripts

| Command               | Description     |
| --------------------- | --------------- |
| `python -m <package>` | Run the package |
| `pytest`              | Run tests       |
| `ruff check .`        | Lint code       |

## Configuration

<Environment variables, config files>

## Testing

```bash
pytest
```

## Contributing

<Branching strategy, PR conventions>

## License

<License type>

```

## Workflow

1. Analyze project structure — identify feature modules.
2. Create / Fix **PRD.md** at project root (stakeholder alignment).
3. Create / Fix **FRD.md** in each feature module (engineering specs).
4. Create / Update **README.md** at project root (developer onboarding).
5. Add docstrings to all public classes and functions.
6. `python -c "import <module>"`.

## Checklist

- [ ] PRD.md at project root with Problem Statement, Goals, Personas, Scope, Features.
- [ ] README.md at project root with Quick Start, Architecture, Commands, Testing.
- [ ] FRD.md in each feature module with Functional Requirements, API Contract.
- [ ] Documents serve correct audience (PRD=stakeholders, FRD=engineers, README=developers).
- [ ] All public classes have docstrings.
- [ ] All public functions have docstrings with Args/Returns.
