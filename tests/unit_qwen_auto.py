"""Unit test suite for qwen_auto.py testing utility functions and core logic."""
import json
import tempfile
import unittest
from pathlib import Path

from modules.root_cli_main_entry import _build_config
from modules.core.src.capabilities_audit_repository import AuditRepository
from modules.core.src.capabilities_output_saver import write_output
from modules.shared.src import RunContext


class TestQwenAutoUnit(unittest.TestCase):
    """Unit tests for standalone functions and dataclass helpers."""

    def test_write_output_format(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            out_path = Path(tmp_dir) / "test_out.md"
            ctx = RunContext(run_id="test_run_123")
            write_output(
                path=out_path,
                content="Hello Qwen Result",
                ctx=ctx,
                src="source.md",
                dur=5.5,
                input_chars=100,
                output_chars=50,
            )
            self.assertTrue(out_path.exists())
            text = out_path.read_text(encoding="utf-8")
            self.assertIn("--- METADATA TRACEABILITY ---", text)
            self.assertIn("Run ID           : test_run_123", text)
            self.assertIn("Hello Qwen Result", text)

    def test_audit_log_record(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir)
            audit = AuditRepository(output_dir)
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

    def test_event_constants_and_emitter(self) -> None:
        from modules.shared.src import (
            EVENT_DISPATCH_ACKNOWLEDGED,
            EVENT_DOCUMENT_PARSED,
            EVENT_GENERATION_FINISHED,
            EVENT_NETWORK_RECONNECTING,
            EVENT_OUTPUT_COPIED,
            EVENT_SEND_CLICKED,
            EVENT_STREAMING_GENERATION,
            EVENT_THINKING_STARTED,
            LifecycleEmitter,
        )

        emitter = LifecycleEmitter()
        received_events = []

        for evt_name in [
            EVENT_THINKING_STARTED,
            EVENT_STREAMING_GENERATION,
            EVENT_GENERATION_FINISHED,
            EVENT_DOCUMENT_PARSED,
            EVENT_DISPATCH_ACKNOWLEDGED,
            EVENT_SEND_CLICKED,
            EVENT_NETWORK_RECONNECTING,
            EVENT_OUTPUT_COPIED,
        ]:
            emitter.on(evt_name, lambda e: received_events.append(e.name))

        for evt_name in [
            EVENT_THINKING_STARTED,
            EVENT_STREAMING_GENERATION,
            EVENT_GENERATION_FINISHED,
            EVENT_DOCUMENT_PARSED,
            EVENT_DISPATCH_ACKNOWLEDGED,
            EVENT_SEND_CLICKED,
            EVENT_NETWORK_RECONNECTING,
            EVENT_OUTPUT_COPIED,
        ]:
            emitter.emit(evt_name, {"test": True})

        self.assertEqual(len(received_events), 8)
        self.assertEqual(
            received_events,
            [
                "EVENT_THINKING_STARTED",
                "EVENT_STREAMING_GENERATION",
                "EVENT_GENERATION_FINISHED",
                "EVENT_DOCUMENT_PARSED",
                "EVENT_DISPATCH_ACKNOWLEDGED",
                "EVENT_SEND_CLICKED",
                "EVENT_NETWORK_RECONNECTING",
                "EVENT_OUTPUT_COPIED",
            ],
        )

    def test_enum_event_type_and_event_id(self) -> None:
        from modules.shared.src import LifecycleEmitter, QwenEventType

        emitter = LifecycleEmitter()
        received = []
        emitter.on(QwenEventType.THINKING_STARTED, lambda evt: received.append(evt))

        evt = emitter.emit(QwenEventType.THINKING_STARTED, {"mode": "realtime"})
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0].name, "EVENT_THINKING_STARTED")
        self.assertIsNotNone(received[0].event_id)
        self.assertEqual(received[0].details, {"mode": "realtime"})



if __name__ == "__main__":
    unittest.main()
