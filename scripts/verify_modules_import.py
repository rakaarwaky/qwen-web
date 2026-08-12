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
    "modules.shared.src.common",
    "modules.shared.src.common.taxonomy_core_vo",
    "modules.shared.src.common.taxonomy_domain_error",
    "modules.shared.src.common.taxonomy_config_vo",
    "modules.shared.src.common.taxonomy_core_constant",
    "modules.shared.src.core",
    "modules.shared.src.core.taxonomy_core_vo",
    "modules.shared.src.core.taxonomy_core_constant",
    "modules.shared.src.core.taxonomy_core_entity",
    "modules.shared.src.core.taxonomy_core_event",
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
