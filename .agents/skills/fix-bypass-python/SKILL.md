---
name: fix-bypass-python
description: "Fix Python bypass comments (type: ignore, noqa) by addressing root causes instead of suppressing errors."
metadata:
  tags: [python, bypass, comments, type-hints, refactoring, noqa]
  triggers:
    - "fix bypass python"
    - "remove noqa python"
    - "remove type ignore python"
  dependencies: []
  related:
    - cleanup-consolidate-python
---

# fix-bypass-python

**Rule:** Fix the root cause instead of suppressing errors. No `# type: ignore` or `# noqa` without justification.

## Workflow

1. **Find** bypass comments:
   ```bash
   grep -rn "type: ignore" modules/*/src/
   grep -rn "noqa" modules/*/src/
   ```
2. **Diagnose** — Why is there a bypass comment? What error is it hiding?
3. **Fix root cause:**
   - `type: ignore` → Add proper type annotations.
   - `noqa` → Fix the lint violation (formatting, naming, unused imports, etc.).
4. **Remove** the bypass comment.
5. **Verify:**
   ```bash
   python -m mypy modules/ --ignore-missing-imports
   pycodestyle modules/ --max-line-length=88
   ```

## Verification Checklist

- [ ] All `# type: ignore` removed (or justified with explanation).
- [ ] All `# noqa` removed (or justified with explanation).
- [ ] Type checker passes without errors.
- [ ] Linter passes without violations.
