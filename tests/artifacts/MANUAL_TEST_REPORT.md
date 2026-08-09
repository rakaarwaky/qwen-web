# Manual Playwright Test Report — qwen-web-automation

**Date:** 2026-08-09
**Approach:** Headed Playwright probe against the LIVE `chat.qwen.ai` (Qwen3.8-Max),
using the saved session in `qwen_session/`. Non-destructive (throwaway file in /tmp).

## Result: 8/8 smoke-check PASS (after refactor)

| Step | Selector / Strategy | Status | Note |
|------|---------------------|--------|------|
| Session login | — | ✅ PASS | No `/login` redirect; saved cookies valid |
| New Chat | `[aria-label='New Chat']` | ✅ PASS | `NEW_CHAT_SELECTORS` still valid |
| Chat input | `textarea` | ✅ PASS | Real class is `textarea.message-input-textarea` |
| File attachment | `.mode-select-open` → "Upload attachment" | ✅ PASS | **Only working strategy** (see below) |
| Prompt injection | React value-setter + input/change events | ✅ PASS | 62 chars written; verified via `el.value` |
| Send button | `button[aria-label*='Send' i]:not([disabled])` | ✅ PASS | |
| Send dispatch | click | ✅ PASS | Requires waiting for file "Parsing..." to finish first |
| Response received | `MESSAGE_SELECTORS` stability loop | ✅ PASS | Qwen replied: *"Yes, I received the attached file and can read it."* |

## Key finding: 3 of 4 upload strategies were DEAD CODE

Against the current Qwen UI (Qwen3.8-Max):

- ❌ **Strategy 1** — `#filesUpload` `set_input_files`: hidden & `not visible`;
  `set_input_files` returns OK but renders **no attachment card**.
- ❌ **Strategy 2** — `[aria-label*='Upload']` button: no such element exists
  (the "+" button has no aria-label).
- ✅ **Strategy 3** — `.mode-select-open` → "Upload attachment" dropdown:
  opens native file chooser, `set_files` works, card appears with "Parsing...".
- ❌ **Strategy 4** — JS DataTransfer into `#filesUpload`: depends on the dead
  hidden input; no card rendered.

## Action taken (refactor in `src/qwen_client.py`)

1. **`_upload_file_attachment`** collapsed from 4 fallback strategies to the single
   verified mode-select path. Removed ~45 lines of dead code (hidden-input +
   DataTransfer strategies). Kept an explicit warning log if the card fails to appear.
2. **`_inject_text`** collapsed from 4 tiers to 2: React value-setter (primary) →
   clipboard paste (fallback). Removed `fill()` (does not trigger React state) and
   raw `type()` (O(n) slow for 100k+ char prompts).

## Test artifacts

- `tests/manual_probe.py` — re-runnable smoke-check; writes `selectors_live.json`
  (machine-readable snapshot of which selectors are alive) after every run.
  Re-run after any Qwen UI change: `python3 tests/manual_probe.py` (headed).
- `tests/artifacts/selectors_live.json` — latest snapshot.
- `tests/artifacts/0*.png` — per-step screenshots.
- `tests/artifacts/probe_response.txt` — actual Qwen reply from the live run.

## Note on browser-use

`github.com/browser-use/browser-use` was considered but rejected: the failure was a
**selector/strategy drift**, not a need for LLM-driven navigation. A single verified
Playwright path is more debuggable, faster, and dependency-light than adding an LLM
agent. The `selectors_live.json` snapshot gives us a cheap regression alarm instead.
