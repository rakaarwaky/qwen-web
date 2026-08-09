"""Smoke test suite for qwen_auto.py verifying fast startup and CLI argument execution in under 5s."""
import subprocess
import sys
import time
import unittest


class TestQwenAutoSmoke(unittest.TestCase):
    """Smoke tests for quick sanity checks."""

    def test_cli_help_flag_smoke(self) -> None:
        t0 = time.time()
        res = subprocess.run(
            [sys.executable, "src/main.py", "--help"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        duration = time.time() - t0
        self.assertEqual(res.returncode, 0)
        self.assertIn("Automate chat.qwen.ai", res.stdout)
        self.assertLess(duration, 5.0, "Smoke test took longer than 5 seconds")

    def test_module_import_smoke(self) -> None:
        t0 = time.time()
        res = subprocess.run(
            [sys.executable, "-c", "import src.main as q; print(q.__file__)"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        duration = time.time() - t0
        self.assertEqual(res.returncode, 0)
        self.assertLess(duration, 5.0)


if __name__ == "__main__":
    unittest.main()
