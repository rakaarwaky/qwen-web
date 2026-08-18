"""Unit tests for surface_cli_update_command and capabilities_update_manager."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from modules.cli.src import surface_cli_update_command
from modules.core.src.capabilities_update_manager import compare_versions
from modules.shared.src.contract_core_protocol import IUpdateProtocol
from modules.shared.src.taxonomy_core_vo import (
    UpdateCheckResult,
    UpdateReport,
    UpdateStepResult,
    VersionString,
)


class TestVersionComparison(unittest.TestCase):
    """Test version comparison helper logic."""

    def test_version_compare_equal(self) -> None:
        self.assertEqual(compare_versions("4.2.0", "4.2.0"), 0)
        self.assertEqual(compare_versions("v4.2.0", "4.2.0"), 0)

    def test_version_compare_newer(self) -> None:
        self.assertGreater(compare_versions("4.3.0", "4.2.0"), 0)
        self.assertGreater(compare_versions("4.2.1", "4.2.0"), 0)

    def test_version_compare_older(self) -> None:
        self.assertLess(compare_versions("4.1.9", "4.2.0"), 0)


class TestSurfaceCliUpdateCommand(unittest.TestCase):
    """Test CLI surface update command controller handling."""

    def setUp(self) -> None:
        self.updater = MagicMock(spec=IUpdateProtocol)

    def test_handle_check_mode_up_to_date(self) -> None:
        args = MagicMock()
        args.check = True
        args.force = False

        self.updater.check_update.return_value = UpdateCheckResult(
            package_name="qwen-web-cli",
            current_version="4.2.0",
            latest_version="4.2.0",
            update_available=False,
            source="github",
        )

        res = surface_cli_update_command.handle(args, self.updater)
        self.assertTrue(res.get("success"))
        self.assertIn("already running the latest version", str(res.get("message")))

    def test_handle_check_mode_update_available(self) -> None:
        args = MagicMock()
        args.check = True
        args.force = False

        self.updater.check_update.return_value = UpdateCheckResult(
            package_name="qwen-web-cli",
            current_version="4.2.0",
            latest_version="4.3.0",
            update_available=True,
            source="github",
        )

        res = surface_cli_update_command.handle(args, self.updater)
        self.assertTrue(res.get("success"))
        self.assertIn("qwen-web-cli update", str(res.get("message")))

    def test_handle_perform_update_success(self) -> None:
        args = MagicMock()
        args.check = False
        args.force = False

        self.updater.perform_update.return_value = UpdateReport(
            package_name="qwen-web-cli",
            previous_version="4.2.0",
            latest_version="4.3.0",
            source="github",
            update_available=True,
            forced=False,
            changed=True,
            steps=(
                UpdateStepResult("package_upgrade", True, True, "pip upgrade"),
                UpdateStepResult("browser_sync", True, True, "playwright install chromium"),
            ),
            health_checks=(
                UpdateStepResult("health:python_runtime", True, True, "Python 3.10+"),
            ),
            post_update_version="4.3.0",
            healthy=True,
            message="Successfully updated qwen-web-cli 4.2.0 -> 4.3.0",
        )

        res = surface_cli_update_command.handle(args, self.updater)
        self.assertTrue(res.get("success"))
        self.assertIn("Successfully updated", str(res.get("message")))


if __name__ == "__main__":
    unittest.main()
