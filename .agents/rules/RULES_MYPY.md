# MyPy Type Checking Rules

See [README.md](../README.md) for Python adapter usage and [RULES_RUFF.md](RULES_RUFF.md) for related Python linting.

MyPy is a static type checker for Python, available at https://mypy-lang.org/. It enforces type annotations and detects type inconsistencies at analysis time.

## Error Categories

MyPy error codes follow the pattern `[<scope>-<code>]` or `[<code>]`. Below are the most common error codes organized by category.

## Argument & Return Type Errors

| Code         | Name                      | Description                                                                                                     |
| ------------ | ------------------------- | --------------------------------------------------------------------------------------------------------------- |
| arg-type     | Argument type mismatch    | Function argument has incompatible type. Example: `def f(x: int) -> None` called with `f("s")` — `str` ≠ `int`. |
| return-type  | Return type mismatch      | Function return value does not match declared return type. Example: `def f() -> int` returning `"s"`.           |
| return-value | Incompatible return value | Returned expression type is not compatible with the declared return type.                                       |
| call-arg     | Missing/extra arguments   | Function called with wrong number or names of arguments.                                                        |
| type-arg     | Missing type arguments    | Generic type used without type parameters. Example: `List` instead of `List[int]`.                              |

## Variable & Assignment Errors

| Code                 | Name                     | Description                                                                                            |
| -------------------- | ------------------------ | ------------------------------------------------------------------------------------------------------ |
| var-annotated        | Variable not annotated   | Variable has no type annotation and MyPy cannot infer the type. Required by `--disallow-untyped-defs`. |
| assignment           | Incompatible assignment  | Value assigned to variable is incompatible with its declared type. Example: `x: int = "s"`.            |
| misc                 | Miscellaneous type error | Catch-all for type errors that don't fit other categories. Often indicates structural type issues.     |
| annotation-unchecked | Annotation unchecked     | Type annotation could not be fully checked because the type is defined in an unchecked module.         |

## Import & Module Errors

| Code             | Name             | Description                                                                                      |
| ---------------- | ---------------- | ------------------------------------------------------------------------------------------------ |
| import           | Import not found | Module or symbol cannot be resolved. Either missing package, missing stub, or wrong import path. |
| import-untyped   | Untyped import   | Imported module has no type stubs and is not annotated, so its contents are `Any`.               |
| import-not-found | Import not found | The module file does not exist or is not on the Python path.                                     |
| import-private   | Private import   | Import of a private name (prefixed with `_`) from another module.                                |

## Attribute & Access Errors

| Code          | Name                            | Description                                                                                   |
| ------------- | ------------------------------- | --------------------------------------------------------------------------------------------- |
| attr-defined  | Attribute not defined           | Accessing an attribute that does not exist on the type. Example: `"".nonexistent`.            |
| method-assign | Method assignment               | Assigning to a method name overwrites the method.                                             |
| override      | Override signature mismatch     | Method override has an incompatible signature (wrong parameter types or return type).         |
| abstract      | Abstract method not implemented | Class fails to implement all abstract methods from its base class.                            |
| union-attr    | Union attribute access          | Accessing an attribute that may not exist on all union members. Use `isinstance` check first. |

## Operator & Expression Errors

| Code               | Name                 | Description                                                                      |
| ------------------ | -------------------- | -------------------------------------------------------------------------------- |
| operator           | Unsupported operator | Operator not supported for the given operand types. Example: `"s" - 5`.          |
| comparison-overlap | Comparison overlap   | Comparison between types that have no overlap (e.g., `int == str` always False). |
| redundant-cast     | Redundant cast       | Type cast is unnecessary because the expression already has the target type.     |
| redundant-expr     | Redundant expression | Expression has no effect or is always True/False based on type.                  |

## Control Flow & Index Errors

| Code        | Name                   | Description                                                                                                 |
| ----------- | ---------------------- | ----------------------------------------------------------------------------------------------------------- |
| index       | Invalid index type     | Index expression type does not match the container's index type. Example: `d[5]` where `d: Dict[str, int]`. |
| list-item   | Incompatible list item | Item being appended/inserted has type incompatible with list element type.                                  |
| dict-item   | Incompatible dict item | Key or value type in dict literal does not match declared dict type.                                        |
| truthy-bool | Truthy function        | Function that always returns a truthy value in boolean context; should return `bool`.                       |

## Configuration & Strictness Flags

| Flag                         | Effect                                                                                                       |
| ---------------------------- | ------------------------------------------------------------------------------------------------------------ |
| `--strict`                   | Enables all strictness options: `--strict-equality`, `--no-implicit-optional`, `--warn-unused-ignores`, etc. |
| `--disallow-untyped-defs`    | Requires type annotations on all function definitions.                                                       |
| `--disallow-incomplete-defs` | Requires complete annotations (not just `-> None` without parameter types).                                  |
| `--disallow-untyped-calls`   | Requires that all called functions have type annotations.                                                    |
| `--warn-return-any`          | Warns when function returns `Any` type.                                                                      |
| `--check-untyped-defs`       | Type-checks functions that lack annotations (treats as unchecked by default).                                |
| `--no-implicit-optional`     | Requires explicit `Optional[X]` instead of allowing `None` implicitly.                                       |
| `--warn-unused-ignores`      | Warns about `# type: ignore` comments that are no longer needed.                                             |
| `--strict-equality`          | Flags comparisons between types that can never be equal.                                                     |

## `# type: ignore` Suppression

| Code                 | Suppression                              |
| -------------------- | ---------------------------------------- |
| All errors on a line | `# type: ignore`                         |
| Specific error code  | `# type: ignore[arg-type]`               |
| Multiple codes       | `# type: ignore[arg-type, return-value]` |
