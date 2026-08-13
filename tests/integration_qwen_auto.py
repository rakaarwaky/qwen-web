"""Integration test suite for qwen_auto.py testing queue pipeline and file system workflow."""
import tempfile
import unittest
from pathlib import Path

from modules.core.src.capabilities_audit_repository import AuditRepository
from modules.core.src.agent_core_orchestrator import CoreOrchestrator
from modules.shared.src import AppConfig, RunContext
from modules.shared.src.taxonomy_core_entity import CircuitBreaker, RateLimiter


class MockQwenClient:
    """Mock QwenClient for pipeline integration tests without opening a real browser."""

    def __init__(self, raise_error: bool = False, return_text: str = "Mock Qwen Answer Response Body") -> None:
        self.raise_error = raise_error
        self.return_text = return_text
        self.reset_count = 0

    def send_file(self, file_path: Path, timeout: int = 300, custom_prompt_path: Path | None = None, *args, **kwargs) -> str:
        if self.raise_error:
            raise RuntimeError("Mock network failure")
        return self.return_text

    def reset_page(self) -> None:
        self.reset_count += 1


class TestQwenAutoIntegration(unittest.TestCase):
    """Integration tests for file movement and quarantine handling."""

    def test_single_file_processing_pipeline(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            base = Path(tmp_dir)
            input_file = base / "test.md"
            input_file.write_text("Sample input prompt")

            out_dir = base / "out"
            done_dir = base / "done"
            fail_dir = base / "failed"
            proc_dir = base / "proc"
            sess_dir = base / "sess"

            cfg = AppConfig(
                mode="single",
                input_path=input_file,
                output_path=out_dir / "test.md",
                done_path=done_dir,
                failed_path=fail_dir,
                proc_path=proc_dir,
                session_path=sess_dir,
            )

            orch = CoreOrchestrator(
                browser=MagicMock(),
                injector=MagicMock(),
                sender=MagicMock(return_value="Successful response text"),
                streamer=MagicMock(wait_for_response=MagicMock(return_value="Successful response text")),
                uploader=MagicMock(upload_attachment=MagicMock(return_value=False)),
                saver=MagicMock(),
                audit=AuditRepository(out_dir),
                observability=MagicMock(get_logger=MagicMock(return_value=MagicMock())),
                workspace=MagicMock(),
                circuit_breaker=CircuitBreaker(),
                rate_limiter=RateLimiter(),
            )

            ctx = RunContext()
            for proc_file, rel_path in orch._iter_todo(cfg):
                orch._process_file(proc_file, rel_path, cfg, ctx)

            # Output file created
            out_file = out_dir / "test.md"
            self.assertTrue(out_file.exists())
            self.assertIn("Successful response text", out_file.read_text(encoding="utf-8"))

    def test_quarantine_pipeline_on_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            base = Path(tmp_dir)
            input_file = base / "failing.md"
            input_file.write_text("Failing prompt content")

            out_dir = base / "out"
            done_dir = base / "done"
            fail_dir = base / "failed"
            proc_dir = base / "proc"
            sess_dir = base / "sess"

            cfg = AppConfig(
                mode="single",
                input_path=input_file,
                output_path=out_dir / "failing.md",
                done_path=done_dir,
                failed_path=fail_dir,
                proc_path=proc_dir,
                session_path=sess_dir,
            )

            orch = CoreOrchestrator(
                browser=MagicMock(),
                injector=MagicMock(),
                sender=MagicMock(side_effect=RuntimeError("Mock network failure")),
                streamer=MagicMock(),
                uploader=MagicMock(upload_attachment=MagicMock(return_value=False)),
                saver=MagicMock(),
                audit=AuditRepository(out_dir),
                observability=MagicMock(get_logger=MagicMock(return_value=MagicMock())),
                workspace=MagicMock(),
                circuit_breaker=CircuitBreaker(),
                rate_limiter=RateLimiter(),
            )

            ctx = RunContext()
            for proc_file, rel_path in orch._iter_todo(cfg):
                try:
                    orch._process_file(proc_file, rel_path, cfg, ctx)
                except RuntimeError:
                    pass

            # Quarantined file in failed folder
            quarantined = fail_dir / "failing.md"
            self.assertTrue(quarantined.exists())


if __name__ == "__main__":
    unittest.main()
