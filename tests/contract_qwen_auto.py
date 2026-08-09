"""Contract test suite for qwen_auto.py verifying public API contracts."""
import unittest
from pathlib import Path
from src.qwen_auto import (
    AppConfig,
    RunContext,
    AuditLog,
    QwenClient,
    AuthRequiredError,
    PromptInjectionError,
)


class TestQwenAutoContract(unittest.TestCase):
    """Contract tests to verify class and type signatures exist."""

    def test_app_config_contract(self) -> None:
        cfg = AppConfig(
            mode="single",
            input_path=Path("input.md"),
            output_path=Path("output.md"),
            done_path=Path("done"),
            failed_path=Path("failed"),
            proc_path=Path("proc"),
            session_path=Path("session"),
            interval=3,
            timeout=300,
            headless=True,
        )
        self.assertEqual(cfg.mode, "single")
        self.assertEqual(cfg.interval, 3)

    def test_run_context_contract(self) -> None:
        ctx = RunContext()
        self.assertTrue(isinstance(ctx.run_id, str))
        self.assertGreater(len(ctx.run_id), 0)

    def test_exceptions_contract(self) -> None:
        self.assertTrue(issubclass(AuthRequiredError, RuntimeError))
        self.assertTrue(issubclass(PromptInjectionError, RuntimeError))

    def test_qwen_client_contract_methods(self) -> None:
        expected_methods = [
            "start_new_chat",
            "_find_input",
            "_count_messages",
            "_latest_message_text",
            "_inject_text",
            "_is_file_parsing_or_waiting",
            "_wait_for_input_parsed",
            "_is_prompt_dispatched",
            "_click_send",
            "_wait_for_response",
            "_check_ui_error",
            "_upload_file_attachment",
            "send_file",
            "send_prompt",
        ]
        for m in expected_methods:
            self.assertTrue(
                hasattr(QwenClient, m), f"QwenClient missing method {m}"
            )


if __name__ == "__main__":
    unittest.main()
