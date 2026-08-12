"""Phase verification helper — import smoke tests for the modules tree."""
import importlib
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

CHECKS = [
    "modules",
    "modules.shared",
    "modules.shared.src",
    "modules.shared.src.taxonomy_core_vo",
    "modules.shared.src.taxonomy_domain_error",
    "modules.shared.src.taxonomy_config_vo",
    "modules.shared.src.taxonomy_core_constant",
    "modules.shared.src.taxonomy_core_entity",
    "modules.shared.src.taxonomy_core_event",
    "modules.shared.src.contract_core_protocol",
    "modules.shared.src.contract_core_aggregate",
    "modules.shared.src.contract_cli_aggregate",
    "modules.shared.src.contract_mcp_aggregate",
    "modules.shared.src.utility_core_prompt",
    "modules.shared.src.utility_core_path",
    "modules.shared.src.utility_core_validation",
    "modules.shared.src.utility_core_text",
    "modules.shared.src.utility_core_error",
    "modules.shared.src.utility_core_events",
]

failed = []
for name in CHECKS:
    try:
        importlib.import_module(name)
    except Exception as exc:
        failed.append((name, exc))
        print(f"FAIL {name}: {type(exc).__name__}: {exc}")
if failed:
    raise SystemExit(1)
print(f"OK — {len(CHECKS)} modules import cleanly")