"""Tests that scripts/install.sh session-dir logic stays in sync with the app config.

The installer repairs permissions on the browser session directory
(APP_SESSION_DIR). It must target exactly the directory the application uses at
runtime (cfg.session_path -> DEFAULT_SESSION), otherwise it fixes permissions on
a directory the app no longer touches. These tests lock the two sources of truth
together.
"""

from __future__ import annotations

import os
import site
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
INSTALL_SCRIPT = PROJECT_ROOT / "scripts" / "install.sh"
APP_CONFIG_SYMBOL = "modules.shared.src.taxonomy_core_constant"


def _env_with_pythonpath(tmp_path: Path) -> dict[str, str]:
    """Build an env where the subprocess python can import the app package.

    The nested subprocess does not inherit the parent's user site-packages
    automatically, so we forward it via PYTHONPATH.
    """
    env = {**os.environ, "HOME": str(tmp_path)}
    env.pop("XDG_DATA_HOME", None)
    user_site = site.getusersitepackages()
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = os.pathsep.join([str(user_site), existing]) if existing else str(user_site)
    return env


def _app_default_session(env: dict[str, str]) -> str:
    """Resolve the app's DEFAULT_SESSION in a subprocess under ``env``."""
    code = f"from {APP_CONFIG_SYMBOL} import DEFAULT_SESSION; print(DEFAULT_SESSION)"
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=True,
        cwd=PROJECT_ROOT,
        env=env,
    )
    return result.stdout.strip()


def _install_fallback_session_dir(env: dict[str, str]) -> str:
    """Evaluate install.sh's fallback APP_SESSION_DIR expression under ``env``."""
    lines = INSTALL_SCRIPT.read_text(encoding="utf-8").splitlines()
    fallback = next(
        line.lstrip() for line in lines if line.lstrip().startswith("APP_SESSION_DIR=") and "XDG_DATA_HOME" in line
    )
    expression = fallback.split("=", 1)[1].strip().strip('"')
    result = subprocess.run(
        ["bash", "-c", f"printf '%s' {expression}"],
        capture_output=True,
        text=True,
        check=True,
        cwd=PROJECT_ROOT,
        env=env,
    )
    return result.stdout


def test_install_script_derives_session_dir_from_app_config() -> None:
    """The installer must derive the session dir from the app config, not hardcode it."""
    script = INSTALL_SCRIPT.read_text(encoding="utf-8")
    derivation = next(line for line in script.splitlines() if "APP_SESSION_DIR=" in line and "DEFAULT_SESSION" in line)
    assert f"from {APP_CONFIG_SYMBOL} import DEFAULT_SESSION" in derivation


def test_install_fallback_matches_app_default_without_xdg_data_home(tmp_path) -> None:
    """With no XDG_DATA_HOME set, install.sh and the app resolve the same path."""
    env = _env_with_pythonpath(tmp_path)
    assert _install_fallback_session_dir(env) == _app_default_session(env)


def test_install_fallback_matches_app_default_with_xdg_data_home(tmp_path) -> None:
    """With XDG_DATA_HOME set, install.sh and the app resolve the same path."""
    env = _env_with_pythonpath(tmp_path)
    env["XDG_DATA_HOME"] = str(tmp_path / "xdg-data")
    assert _install_fallback_session_dir(env) == _app_default_session(env)
