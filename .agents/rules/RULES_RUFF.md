# Ruff Linting Rules

See [README.md](../README.md) for Python adapter usage and [RULES_AES.md](RULES_AES.md) for AES rule context.

Ruff is an extremely fast Python linter written in Rust. It re-implements popular linting rules from Flake8, Pyflakes, isort, and pylint.

## Rule Categories

| Prefix | Category                     | Description                                                           |
| ------ | ---------------------------- | --------------------------------------------------------------------- |
| F      | Pyflakes                     | Logic errors: unused imports, undefined names, duplicate arguments    |
| E/W    | Pycodestyle                  | PEP 8 formatting: indentation, line length, whitespace                |
| N      | PEP 8 Naming                 | Naming conventions: class names, function names, constants            |
| A      | Builtins                     | Shadowing built-in names, assignment to builtins                      |
| B      | Flake8 Bugbear               | Bug-prone patterns: mutable defaults, `pass` in `__init__`, star-args |
| C      | Complexity                   | McCabe cyclomatic complexity (`C901`) and cognitive complexity        |
| D      | pydocstyle                   | Docstring conventions: missing docstrings, formatting                 |
| I      | isort                        | Import ordering: standard library, third-party, first-party           |
| P      | flake8-print                 | Print statements (`print`, `pprint`) in production code               |
| S      | flake8-bandit                | Security: hardcoded passwords, SQL injection, exec usage              |
| T      | flake8-print / flake8-printf | Print / string formatting                                             |
| U      | pyupgrade                    | Modern Python syntax: f-strings, set literals, `super()`              |
| Y      | flake8-2020                  | Version checks: `sys.version`, `six` usage                            |
| R      | flake8-return                | Return statement consistency                                          |

## Key Rules

| Code | Rule                                               | Severity |
| ---- | -------------------------------------------------- | -------- |
| F401 | Module imported but unused                         | Error    |
| F403 | Star import (`from x import *`) used               | Error    |
| F405 | Star import used but name not defined in `__all__` | Error    |
| F821 | Undefined name                                     | Error    |
| F841 | Local variable assigned but not used               | Error    |
| E501 | Line too long (>88 chars)                          | Warning  |
| W291 | Trailing whitespace                                | Warning  |
| N801 | Class name should use CapWords convention          | Error    |
| N802 | Function name should be lowercase                  | Error    |
| N803 | Argument name should be lowercase                  | Error    |
| B006 | Mutable default argument (`def f(x=[])`)           | Error    |
| B007 | Loop control variable not used within loop body    | Warning  |
| C901 | Function is too complex (McCabe > 10)              | Warning  |
| D100 | Missing docstring in public module                 | Warning  |
| D101 | Missing docstring in public class                  | Warning  |
| D102 | Missing docstring in public method                 | Warning  |
| I001 | Import block is un-sorted or un-formatted          | Error    |
| P001 | `print()` statement found                          | Warning  |
| S101 | Use of `assert` detected (production code)         | Warning  |
| S102 | Use of `exec` detected                             | Error    |
| S105 | Hardcoded password string detected                 | Error    |
| U001 | Use `f""` instead of `.format()`                   | Warning  |
