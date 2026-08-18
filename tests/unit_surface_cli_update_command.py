"""Unit tests for surface_cli_update_command and capabilities_update_manager."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from modules.cli.src import surface_cli_update_command
from modules.core.src.capabilities_update_manager import UpdateManager, compare_versions
from modules.shared.src.contract_core_protocol import IUpdateProtocol
from modules.shared.src.taxonomy_core_vo import (
    ForceFlag,
    UpdateCheckResult,
    UpdateReport,
    UpdateStepResult,
    VersionString,
)


class TestVersionComparison(unittest.TestCase):
    """Test version comparison helper logic."""

    def test_version_compare_equal(self) -> None:
        self.assertEqual(compare_versions("4.5.1", "4.5.1"), 0)
        self.assertEqual(compare_versions("v4.5.1", "4.5.1"), 0)

    def test_version_compare_newer(self) -> None:
        self.assertGreater(compare_versions("4.5.2", "4.5.1"), 0)
        self.assertGreater(compare_versions("4.6.0", "4.5.1"), 0)

    def test_version_compare_older(self) -> None:
        self.assertLess(compare_versions("4.4.0", "4.5.1"), 0)


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
            current_version="4.5.1",
            latest_version="4.5.1",
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
            current_version="4.5.1",
            latest_version="4.5.2",
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
            previous_version="4.5.1",
            latest_version="4.5.2",
            source="github",
            update_available=True,
            forced=False,
            changed=True,
            steps=(
                UpdateStepResult("package_upgrade", True, True, "git pull & editable reinstall"),
                UpdateStepResult("browser_sync", True, True, "playwright install chromium"),
            ),
            health_checks=(
                UpdateStepResult("health:python_runtime", True, True, "Python 3.10+"),
            ),
            post_update_version="4.5.2",
            healthy=True,
            message="Successfully updated qwen-web-cli 4.5.1 -> 4.5.2",
        )

        res = surface_cli_update_command.handle(args, self.updater)
        self.assertTrue(res.get("success"))
        self.assertIn("Successfully updated", str(res.get("message")))


class TestUpdateManagerRealFlow(unittest.TestCase):
    """Test UpdateManager 4.5.1 -> 4.5.2 version bump & upgrade pipeline."""

    def setUp(self) -> None:
        self.manager = UpdateManager()

    @patch("modules.core.src.capabilities_update_manager.UpdateManager._fetch_json")
    @patch("modules.core.src.capabilities_update_manager.get_package_version")
    def test_check_update_discovers_4_5_2(self, mock_get_ver: MagicMock, mock_fetch_json: MagicMock) -> None:
        mock_get_ver.return_value = "4.5.1"
        mock_fetch_json.return_value = {"tag_name": "v4.5.2", "name": "v4.5.2"}

        res = self.manager.check_update()

        self.assertEqual(res.current_version, "4.5.1")
        self.assertEqual(res.latest_version, "4.5.2")
        self.assertTrue(res.update_available)
        self.assertEqual(res.source, "github")

    @patch.object(UpdateManager, "upgrade_package")
    @patch.object(UpdateManager, "sync_browser")
    @patch.object(UpdateManager, "_postflight_health_checks")
    @patch("modules.core.src.capabilities_update_manager.UpdateManager.check_update")
    @patch.object(UpdateManager, "_resolve_installed_version")
    def test_perform_update_executes_pipeline(
        self,
        mock_curr_ver: MagicMock,
        mock_check_update: MagicMock,
        mock_health: MagicMock,
        mock_sync_browser: MagicMock,
        mock_upgrade: MagicMock,
    ) -> None:
        mock_curr_ver.side_effect = [VersionString("4.5.1"), VersionString("4.5.2")]
        mock_check_update.return_value = UpdateCheckResult(
            package_name="qwen-web-cli",
            current_version="4.5.1",
            latest_version="4.5.2",
            update_available=True,
            source="github",
        )
        mock_upgrade.return_value = UpdateStepResult("package_upgrade", True, True, "git pull ok")
        mock_sync_browser.return_value = UpdateStepResult("browser_sync", True, True, "chromium ok")
        mock_health.return_value = (UpdateStepResult("health:check", True, True, "ok"),)

        report = self.manager.perform_update(ForceFlag(False))

        self.assertTrue(report.healthy)
        self.assertEqual(report.previous_version, "4.5.1")
        self.assertEqual(report.latest_version, "4.5.2")
        self.assertEqual(report.post_update_version, "4.5.2")
        self.assertIn("Successfully updated", report.message)


if __name__ == "__main__":
    unittest.main()
