"""Unit test suite for qwen_auto.py testing utility functions and core logic."""
import json
import tempfile
import unittest
from pathlib import Path

from src.config import AppConfig, RunContext
from src.main import _build_config, _parse_args
from src.pipeline import AuditLog, _write_output


class TestQwenAutoUnit(unittest.TestCase):
    """Unit tests for standalone functions and dataclass helpers."""

    def test_write_output_format(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            out_path = Path(tmp_dir) / "test_out.md"
            ctx = RunContext(run_id="test_run_123")
            _write_output(
                path=out_path,
                content="Hello Qwen Result",
                ctx=ctx,
                src="source.md",
                dur=5.5,
                in_c=100,
                out_c=50,
            )
            self.assertTrue(out_path.exists())
            text = out_path.read_text(encoding="utf-8")
            self.assertIn("--- METADATA TRACEABILITY ---", text)
            self.assertIn("Run ID           : test_run_123", text)
            self.assertIn("Hello Qwen Result", text)

    def test_audit_log_record(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir)
            audit = AuditLog(output_dir)
            ctx = RunContext(run_id="audit_run_456")
            audit.log("SUCCESS", ctx, "src.md", "dst.md", 2.5, 120, 80)

            audit_file = output_dir / "audit_history.jsonl"
            self.assertTrue(audit_file.exists())

            line = audit_file.read_text(encoding="utf-8").strip()
            data = json.loads(line)
            self.assertEqual(data["run_id"], "audit_run_456")
            self.assertEqual(data["status"], "SUCCESS")
            self.assertEqual(data["duration_sec"], 2.5)

    def test_build_config_mode_resolution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            dummy_file = Path(tmp_dir) / "input.md"
            dummy_file.write_text("prompt content")

            # Single file mode args
            class MockArgs:
                login = False
                watch = False
                input = str(dummy_file)
                output = str(Path(tmp_dir) / "output.md")
                done_dir = str(Path(tmp_dir) / "done")
                failed_dir = str(Path(tmp_dir) / "failed")
                proc_dir = str(Path(tmp_dir) / "proc")
                data_dir = str(Path(tmp_dir) / "session")
                interval = 3
                timeout = 300
                headless = True

            cfg = _build_config(MockArgs())
            self.assertEqual(cfg.mode, "single")
            self.assertTrue(cfg.headless)

            # Watcher mode args
            MockArgs.watch = True
            cfg_watch = _build_config(MockArgs())
            self.assertEqual(cfg_watch.mode, "watcher")


if __name__ == "__main__":
    unittest.main()
