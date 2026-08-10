"""Regression tests for streamer module — validate_response_content, is_generation_complete, wait_for_response edge cases."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.streamer import (
    CHALLENGE_KEYWORDS,
    is_generation_complete,
    validate_response_content,
    wait_for_response,
)
from src.types import (
    AuthRequiredError,
    LifecycleEmitter,
    NetworkTimeoutError,
    OutputValidationError,
)


# ─── validate_response_content ──────────────────────────────────────────────


class TestValidateResponseContent:
    def test_valid_long_response(self):
        text = "Here is a detailed explanation of how to use Playwright for browser automation. " * 3
        validate_response_content(text)  # no exception

    def test_valid_short_response(self):
        validate_response_content("OK")

    def test_empty_string_raises(self):
        with pytest.raises(OutputValidationError, match="empty"):
            validate_response_content("")

    def test_whitespace_only_raises(self):
        with pytest.raises(OutputValidationError, match="empty"):
            validate_response_content("   \n\t  ")

    def test_captcha_challenge(self):
        with pytest.raises(AuthRequiredError, match="CAPTCHA"):
            validate_response_content("Please verify you are human to continue.")

    def test_attention_required(self):
        with pytest.raises(AuthRequiredError, match="CAPTCHA"):
            validate_response_content("Attention Required! Cloudflare check.")

    def test_502_bad_gateway(self):
        with pytest.raises(OutputValidationError, match="Server error"):
            validate_response_content("502 Bad Gateway")

    def test_504_gateway_timeout(self):
        with pytest.raises(OutputValidationError, match="Server error"):
            validate_response_content("504 Gateway Time-out")

    def test_service_unavailable(self):
        with pytest.raises(OutputValidationError, match="Server error"):
            validate_response_content("Service Unavailable")

    def test_access_denied(self):
        with pytest.raises(OutputValidationError, match="Server error"):
            validate_response_content("Access Denied")

    def test_upload_still_processing(self):
        with pytest.raises(OutputValidationError, match="Server error"):
            validate_response_content("Oops! There are files still uploading")

    def test_please_wait_for_upload(self):
        with pytest.raises(OutputValidationError, match="Server error"):
            validate_response_content("Please wait for the upload to complete")

    def test_challenge_keywords_all_covered(self):
        for kw in CHALLENGE_KEYWORDS:
            text = f"Error: {kw}"
            with pytest.raises((OutputValidationError, AuthRequiredError)):
                validate_response_content(text)

    def test_long_text_with_challenge_keyword_passes(self):
        long_text = ("502 bad gateway " + "word " * 200).strip()
        validate_response_content(long_text)

    def test_challenge_keyword_in_long_text_still_raises(self):
        text = "Please verify you are human. " + "word " * 50
        with pytest.raises(AuthRequiredError, match="CAPTCHA"):
            validate_response_content(text)


# ─── is_generation_complete ─────────────────────────────────────────────────


class TestIsGenerationComplete:
    def test_complete_when_send_enabled_no_stop(self):
        page = MagicMock()
        stop_btn = MagicMock()
        stop_btn.count.return_value = 0
        send_disabled = MagicMock()
        send_disabled.count.return_value = 0
        typing = MagicMock()
        typing.count.return_value = 0

        def locator_factory(sel):
            if "Stop" in sel:
                return stop_btn
            if "disabled" in sel:
                return send_disabled
            if "thinking" in sel or "typing" in sel:
                return typing
            return MagicMock(count=0)

        page.locator.side_effect = locator_factory
        assert is_generation_complete(page) is True

    def test_incomplete_when_stop_visible(self):
        page = MagicMock()
        stop_btn = MagicMock()
        stop_btn.count.return_value = 1
        stop_btn.first.is_visible.return_value = True

        def locator_factory(sel):
            if "Stop" in sel:
                return stop_btn
            return MagicMock(count=0)

        page.locator.side_effect = locator_factory
        assert is_generation_complete(page) is False

    def test_incomplete_when_send_disabled(self):
        page = MagicMock()
        stop_btn = MagicMock()
        stop_btn.count.return_value = 0
        send_disabled = MagicMock()
        send_disabled.count.return_value = 1
        send_disabled.first.is_visible.return_value = True
        typing = MagicMock()
        typing.count.return_value = 0

        def locator_factory(sel):
            if "Stop" in sel:
                return stop_btn
            if "disabled" in sel:
                return send_disabled
            if "thinking" in sel or "typing" in sel:
                return typing
            return MagicMock(count=0)

        page.locator.side_effect = locator_factory
        assert is_generation_complete(page) is False

    def test_incomplete_when_typing_visible(self):
        page = MagicMock()
        stop_btn = MagicMock()
        stop_btn.count.return_value = 0
        send_disabled = MagicMock()
        send_disabled.count.return_value = 0
        typing = MagicMock()
        typing.count.return_value = 1
        typing.first.is_visible.return_value = True

        def locator_factory(sel):
            if "Stop" in sel:
                return stop_btn
            if "disabled" in sel:
                return send_disabled
            if "thinking" in sel or "typing" in sel:
                return typing
            return MagicMock(count=0)

        page.locator.side_effect = locator_factory
        assert is_generation_complete(page) is False

    def test_exception_returns_false(self):
        page = MagicMock()
        page.locator.side_effect = Exception("browser crash")
        assert is_generation_complete(page) is False


# ─── wait_for_response edge cases ───────────────────────────────────────────


class TestWaitForResponseEdgeCases:
    def test_dispatch_not_acknowledged_raises(self):
        page = MagicMock()
        emitter = MagicMock(spec=LifecycleEmitter)
        with pytest.raises(RuntimeError, match="dispatch"):
            wait_for_response(page, timeout_sec=10, msg_count_before=0, emitter=emitter, dispatch_acknowledged=False)

    def test_timeout_returns_none(self):
        page = MagicMock()
        emitter = MagicMock(spec=LifecycleEmitter)

        with patch("src.streamer.count_messages", return_value=1), \
             patch("src.streamer.latest_message_text", return_value=None), \
             patch("src.streamer.time") as mock_time:
            mock_time.time.side_effect = [0, 0, 0, 9999]
            mock_time.sleep = MagicMock()

            result = wait_for_response(
                page,
                timeout_sec=1,
                msg_count_before=1,
                emitter=emitter,
                polling_interval_sec=0,
            )
            assert result is None

    def test_returns_stable_text(self):
        page = MagicMock()
        emitter = MagicMock(spec=LifecycleEmitter)
        stable_text = "This is a stable AI response with enough content to pass validation."

        # latest_message_text: first call sets baseline (return None), then return stable_text.
        # Without this, baseline_text == stable_text so text != baseline_text is always False
        # and the loop never processes any text, hanging until timeout.
        msg_side_effect = [None] + [stable_text] * 20

        with patch("src.streamer.count_messages", return_value=2), \
             patch("src.streamer.latest_message_text", side_effect=msg_side_effect), \
             patch("src.streamer.is_generation_complete", return_value=True), \
             patch("src.streamer.time") as mock_time:
            mock_time.time.side_effect = [0] + [0.1] * 50
            mock_time.sleep = MagicMock()

            result = wait_for_response(
                page,
                timeout_sec=5,
                msg_count_before=1,
                emitter=emitter,
                polling_interval_sec=0,
                stability_checks=2,
            )
            assert result == stable_text
