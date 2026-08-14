# Issue: AES202 Does Not Resolve Public Barrel Imports Through `__init__.py`

## Suggested title

**AES202 incorrectly reports missing taxonomy/contract imports when dependencies are imported through a public `__init__.py` barrel**

## Summary

Lint Arwaky currently reports AES202 `MANDATORY_IMPORT` violations when a Python consumer imports shared dependencies through the package public barrel:

```python
from modules.shared.src import (
    AppConfig,
    IUploadProtocol,
    EVENT_WEB_LOADED,
    QwenCliError,
)
```

The import is valid at runtime, is accepted by `mypy`, and is the intended public API boundary. However, the architecture linter appears to classify the import only by the literal module path `modules.shared.src`. It does not resolve the symbols exported by `modules/shared/src/__init__.py` back to their canonical source layers (`taxonomy`, `contract(protocol)`, `contract(aggregate)`, or `utility`). As a result, AES202 incorrectly concludes that the consumer has not imported the mandatory layers.

This issue was observed while migrating the `qwen-web` repository to a deliberate import policy: consumers outside `modules/shared/src` use the shared public barrel, while modules inside `modules/shared/src` use direct imports between canonical files. The migration is recorded in commit [`d65614c`](https://github.com/rakaarwaky/qwen-web/commit/d65614c) [1].

## Environment

| Component | Value |
|---|---|
| Repository | [`rakaarwaky/qwen-web`](https://github.com/rakaarwaky/qwen-web) [1] |
| Lint Arwaky | `v3.5.1` |
| Language | Python 3.10+ |
| Project barrel | `modules/shared/src/__init__.py` |
| Project config | `lint_arwaky.config.yaml` |
| Affected rules | AES202 `MANDATORY_IMPORT` |
| Affected consumer layers | `capabilities`, `agent(orchestrator)` |
| Operating environment | Ubuntu 24.04, Python 3.12 validation environment |

## Reproduction

Create or use a project with the following structure:

```text
modules/
├── core/src/capabilities_file_uploader.py
├── core/src/agent_core_orchestrator.py
└── shared/src/
    ├── __init__.py
    ├── contract_core_protocol.py
    ├── taxonomy_core_event.py
    ├── taxonomy_core_error.py
    └── taxonomy_core_vo.py
```

Export the required symbols from `modules/shared/src/__init__.py`:

```python
from .contract_core_protocol import IUploadProtocol
from .taxonomy_core_event import EVENT_FILE_UPLOADED
from .taxonomy_core_vo import AppConfig
```

Then import them from an external consumer through the barrel:

```python
from modules.shared.src import AppConfig, EVENT_FILE_UPLOADED, IUploadProtocol
```

Run the architecture scan from the repository root:

```bash
lint-arwaky-cli scan .
```

## Observed result

Lint Arwaky reports 11 AES202 violations even though the required dependencies are present through `modules.shared.src`:

```text
modules/core/src/agent_core_orchestrator.py:1 [AES202] MANDATORY_IMPORT
Layer 'agent' is missing required import 'contract(aggregate)'.

modules/core/src/capabilities_browser_adapter.py:1 [AES202] MANDATORY_IMPORT
Layer 'capabilities' is missing required import 'contract(protocol)'.

modules/core/src/capabilities_file_uploader.py:1 [AES202] MANDATORY_IMPORT
Layer 'capabilities' is missing required import 'contract(protocol)'.

modules/core/src/capabilities_prompt_injector.py:1 [AES202] MANDATORY_IMPORT
Layer 'capabilities' is missing required import 'taxonomy'.
```

The complete scan produced 11 violations across the agent and capabilities files. The exact count can vary with the set of consumer files, but the failure mode is consistent: importing from the barrel is not treated as importing the canonical layer represented by the exported symbol.

## Expected result

The linter should resolve public barrel imports by inspecting the imported symbol and the barrel's export provenance. For example:

| Consumer import | Canonical provenance | Expected AES202 interpretation |
|---|---|---|
| `from modules.shared.src import AppConfig` | `taxonomy_core_vo.py` | Satisfies `taxonomy` |
| `from modules.shared.src import EVENT_FILE_UPLOADED` | `taxonomy_core_event.py` | Satisfies `taxonomy` |
| `from modules.shared.src import QwenCliError` | `taxonomy_core_error.py` | Satisfies `taxonomy` |
| `from modules.shared.src import IUploadProtocol` | `contract_core_protocol.py` | Satisfies `contract(protocol)` |
| `from modules.shared.src import ICoreAggregate` | `contract_core_aggregate.py` | Satisfies `contract(aggregate)` |
| `from modules.shared.src import validate_file` | `utility_core_validation.py` | Satisfies `utility` |

The linter should continue to reject genuinely forbidden imports. Supporting a public barrel must not disable AES201 forbidden-layer checks, circular-import detection, unused-import detection, or orphan detection.

## Validation evidence

The `qwen-web` migration passes all functional and static checks except the unresolved AES202 interpretation:

```text
compileall       PASS
pytest            PASS
mypy modules/    PASS — 55 source files
Ruff check       PASS
Ruff format      PASS
git diff --check PASS
```

The external import policy is also verified by searching all consumers outside `modules/shared/src`; no direct imports remain for `taxonomy_*`, `contract_*`, or `utility_*` modules:

```bash
grep -RIn --include='*.py' \
  -E '^from modules\\.shared\\.src\\.(taxonomy|contract|utility)' \
  modules/cli modules/core modules/mcp \
  modules/root_cli_main_entry.py modules/root_mcp_main_entry.py tests
```

The command returns no matches after the migration.

## Configuration behavior

The project configuration correctly describes the intended architecture, but the current binary still applies the built-in AES202 mandatory-import behavior. The following project-level configuration experiments were tested:

```yaml
mandatory: []
```

```yaml
mandatory: null
```

```yaml
enabled: false
```

The effective configuration displayed by `lint-arwaky-cli config` reflected the project changes, but `lint-arwaky-cli scan .` continued to emit the same AES202 violations. This suggests one of the following implementation problems:

1. AES202 mandatory checks are hard-coded and do not honor the effective rule configuration.
2. The import rule evaluates a separate language-specific configuration copy that is not overridden by the project configuration.
3. `modules.shared.src` imports are intentionally excluded from layer classification and there is no public-barrel configuration mechanism.
4. The `mandatory` field is parsed and displayed but not applied by the rule engine for this class of import.

## Proposed implementation options

### Option A — Add public barrel provenance resolution

When parsing an import such as:

```python
from modules.shared.src import AppConfig
```

resolve `AppConfig` from `modules/shared/src/__init__.py`, follow its import statement to `taxonomy_core_vo.py`, and classify the dependency according to the canonical source file. This is the most precise solution because it preserves symbol-level dependency information.

### Option B — Add a configurable public-barrel declaration

Add a configuration field such as:

```yaml
architecture:
  public_barrels:
    - module: "modules.shared.src"
      source_root: "modules/shared/src"
      resolve_reexports: true
```

The import rule can then treat symbols imported from this module as dependencies of their canonical source layers. This would support projects that intentionally expose a stable public API through `__init__.py` files.

### Option C — Add a barrel dependency mapping

Allow an explicit mapping when static symbol resolution is not possible:

```yaml
architecture:
  import_aliases:
    "modules.shared.src":
      layers: ["taxonomy", "contract", "utility"]
      public: true
```

This is less precise than symbol-level resolution, but it would be a practical compatibility mechanism. The linter should still inspect the imported symbol when possible and use the mapping only as a fallback.

## Acceptance criteria

This issue can be considered resolved when all of the following are true:

1. A fixture importing `taxonomy`, `contract(protocol)`, `contract(aggregate)`, and `utility` symbols through a public `__init__.py` barrel produces no false-positive AES202 violations.
2. The same fixture continues to produce AES201 when a genuinely forbidden direct import is introduced.
3. The rule engine honors project-level configuration for AES202, including `mandatory` and `enabled` behavior.
4. The result is consistent across Python projects and does not depend on whether the import is single-line or multiline.
5. Aliased imports work correctly, for example `from modules.shared.src import AppConfig as RuntimeConfig`.
6. Re-export chains are handled, for example `package_a.__init__` re-exporting from `package_b.__init__`.
7. The linter's own regression tests cover public-barrel resolution and verify that the current false positive does not return.
8. Existing checks for AES201, AES203, AES204, AES205, AES401–406, and AES501–506 remain unchanged.

## Additional context

The requested import policy is intentional:

> Modules outside `modules/shared/src` consume shared functionality through the public barrel. Modules inside `modules/shared/src` import directly from the canonical taxonomy, contract, or utility file.

This policy keeps the internal architecture explicit while giving external consumers a stable public API. Requiring external modules to add unused direct imports solely to satisfy AES202 would create dummy imports, violate the public-boundary policy, and potentially trigger AES203/AES204 checks.

## References

[1]: https://github.com/rakaarwaky/qwen-web/commit/d65614c "qwen-web public shared barrel import migration"

[2]: https://github.com/rakaarwaky/lint-arwaky "Lint Arwaky repository"

[3]: https://github.com/rakaarwaky/lint-arwaky/blob/main/README.md "Lint Arwaky README and configuration overview"
