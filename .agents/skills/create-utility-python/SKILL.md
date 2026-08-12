---
name: create-utility-python
description: "Create and validate Python utility layer files following AES rules: stateless standalone functions, no class, no protocol impl, pure functions, domain-agnostic, reusable across modules."
metadata:
  tags: [python, aes, utility, shared, stateless, pure-function, domain-agnostic]
  triggers:
    - "create utility python"
    - "add utility python"
    - "extract utility python"
    - "create helper function python"
    - "check utility python"
    - "audit utility python"
  dependencies: []
  related:
    - create-taxonomy-python
    - create-capabilities-python
    - create-agent-python
---

# create-utility-python

Utility = stateless standalone functions. No class, no `self`, no domain rules. File: `utility_<domain>_<role>.py`.

**Allowed imports:** Taxonomy only.
**Forbidden:** Capabilities, Agent, Surface, Contract.

## Role Naming

Utility role suffixes are unlimited. The role name is chosen based on demand and must describe the technical responsibility and concern of the file.

## Templates

```python
"""<Domain> utility functions — stateless, pure, domain-agnostic.

Module-level functions only — no classes, no state.
"""

# from shared.user.taxonomy_user_vo import UserVO  # uncomment if using VOs


def <function_name>(<param_name>: str) -> str:
    """<Description of what this function does>.

    Args:
        <param_name>: <description>

    Returns:
        <description of return value>
    """
    # pure function logic here
    pass


def <function_name>(<param_name>: str) -> str:
    """<Description of what this function does>.

    Args:
        <param_name>: <description>

    Returns:
        <description of return value>
    """
    # pure function logic here
    pass
```

## Rules

1. Only module-level functions — no `class`, no `self`.
2. Pure + deterministic — no `random`, no `datetime.now()`, no global mutable state.
3. Domain-agnostic — no business rules, no layer-name knowledge.
4. Reusable — used by ≥2 modules; if single consumer → keep as private helper.
5. I/O allowed only if all above hold.

**Keep as private helper** if ANY: uses `self`, domain-specific, single consumer.
**Extract here** only if ALL: no `self`, pure/I/O-safe, domain-agnostic, ≥2 consumers.

## Workflow

1. Confirm ≥2 consumers, stateless, domain-agnostic.
2. Create `utility_<domain>_<role>.py`.
3. Register in `__init__.py`.
4. `python -c "import <module>"`.

## Checklist

- [ ] Only module-level functions — no class.
- [ ] No `self`, no instance state.
- [ ] Pure/deterministic (or I/O justified: domain-agnostic + reusable).
- [ ] No business rules or layer-name knowledge.
- [ ] Used by ≥2 modules.
- [ ] No import from Capabilities, Agent, Surface, Contract.
- [ ] No magic constants (→ `taxonomy_*_constant.py`).
- [ ] `python -c "import <module>"` passes.
