# Radon Code Complexity Rules

See [README.md](../README.md) for Python adapter usage and [RULES_RUFF.md](RULES_RUFF.md) for related Python linting.

Radon is a Python tool that computes code metrics, available at https://radon.readthedocs.io/. It measures cyclomatic complexity and maintainability index.

## Cyclomatic Complexity Grades

Cyclomatic complexity (M) measures the number of linearly independent paths through source code. It is computed as `M = E − N + 2P` where E = edges, N = nodes, P = connected components. Radon assigns a letter grade based on the score:

| Grade | Score Range | Interpretation                                            | Recommended Action                   |
| ----- | ----------- | --------------------------------------------------------- | ------------------------------------ |
| **A** | 1–5         | Low complexity — simple, well-structured code             | No action needed                     |
| **B** | 6–10        | Moderate complexity — manageable but worth reviewing      | Consider simplification if > 8       |
| **C** | 11–20       | High complexity — difficult to test and maintain          | Refactoring recommended              |
| **D** | 21–30       | Very high complexity — significant risk of defects        | Refactoring strongly recommended     |
| **E** | 31–40       | Extremely high complexity — major maintainability concern | Must refactor before further changes |
| **F** | 41+         | Critical complexity — code is incomprehensible            | Immediate refactoring required       |

## Complexity Contribution by Language Construct

Each construct below adds 1 to the cyclomatic complexity count:

| Construct                               | Example                                         |
| --------------------------------------- | ----------------------------------------------- |
| `if` statement                          | `if x > 0:`                                     |
| `elif` / `else if`                      | `elif x == 5:`                                  |
| `for` loop                              | `for item in items:`                            |
| `while` loop                            | `while condition:`                              |
| `except` block                          | `except ValueError:`                            |
| `with` statement (with context manager) | `with open(f) as fh:`                           |
| `and` / `or` boolean operators          | `if x and y:`                                   |
| `assert` statement                      | `assert condition`                              |
| `match`/`case` (Python 3.10+)           | `case pattern:` — each branch counts as 1       |
| Comprehension (nested)                  | `[x for x in y if z]` — `if` clause counts as 1 |

## Maintainability Index (MI)

Radon also computes the Maintainability Index, a composite metric:

```
MI = max(0, (171 - 5.2 * ln(V) - 0.23 * CC - 16.2 * ln(LoC)) * 100 / 171)
```

Where:

- **V** = Halstead Volume (vocabulary-based measure of code size)
- **CC** = Cyclomatic Complexity
- **LoC** = Lines of Code

| MI Score | Meaning                                                  |
| -------- | -------------------------------------------------------- |
| 85–100   | Highly maintainable — target for all code                |
| 65–84    | Moderately maintainable — some refactoring may help      |
| 0–64     | Difficult to maintain — refactoring strongly recommended |

## Radon CLI Usage

```bash
# Show cyclomatic complexity for all Python files in a directory
radon cc . -s --json

# Show complexity with grade letters
radon cc . -s -g A B C D E F

# Show average complexity per file
radon cc . -s -a

# Show maintainability index
radon mi . -s --json

# Raw metrics (LOC, LLOC, SLOC, comments, etc.)
radon raw . --json
```

## Radon CLI Flags

| Flag               | Description                                       |
| ------------------ | ------------------------------------------------- |
| `-s` / `--show`    | Show the computed complexity score                |
| `--json`           | Output in JSON format                             |
| `-a` / `--average` | Show average complexity per file                  |
| `-g` / `--grade`   | Filter by grade(s): A, B, C, D, E, F              |
| `-e` / `--exclude` | Exclude files/directories matching pattern        |
| `--min`            | Minimum complexity threshold for output           |
| `--max`            | Maximum complexity threshold for output           |
| `--no-assert`      | Exclude `assert` statements from complexity count |

## Threshold Configuration (lint-arwaky)

Recommended lint-arwaky config thresholds:

```yaml
complexity:
  max_grade: B # Acceptable up to grade B (CC ≤ 10)
  flag_on_grade: # Violations for these grades
    - D
    - E
    - F
  fail_build_on: # Build failure on these grades
    - E
    - F
  maintainability:
    min_index: 65 # Minimum acceptable maintainability index
```
