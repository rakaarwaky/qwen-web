# PRD — qwen-web

## Problem Statement

Power users, system administrators, and local AI agents need to process large
volumes of prompts through `chat.qwen.ai` without relying on official,
rate-limited, or unavailable REST APIs. Manual interaction is slow,
un-auditable, and prone to human error. Existing browser automation scripts
are often brittle, lack observability, and fail to handle edge cases like
CAPTCHAs, network timeouts, or dynamic UI changes gracefully. Furthermore,
maintaining these scripts over time becomes a liability as codebases degrade
into spaghetti code, making AI-assisted maintenance unsafe.

## Goals & Success Metrics

- Goal 1: Achieve 99.9% successful end-to-end pipeline execution for batch
  and watcher workloads on native Linux environments.
- Goal 2: Maintain strict AES 7-layer architectural compliance so AI agents
  can safely modify, refactor, and maintain the codebase without introducing
  regressions.
- Goal 3: Provide seamless 1:1 feature parity between CLI and MCP interfaces
  for local AI agent integration.

## User Personas

- **Power User / Developer**: Runs batch markdown prompts locally, needs
  reliable file routing (`input` → `.processing` → `done`/`failed`) and
  detailed JSONL audit logs to track character counts and processing times.
- **AI Agent (via MCP)**: Interacts with the tool programmatically to send
  prompts, process files, and read audit logs without managing browser
  lifecycles or DOM selectors.
- **System Administrator**: Deploys watcher mode as a background service and
  relies on structured JSON logs for aggregation.

## Scope

- **In scope**: `chat.qwen.ai` web automation, Playwright persistent sessions,
  Batch / Watcher / Single / Interactive / MCP modes, the eight core
  capabilities listed below, structured observability
  (structlog, OpenTelemetry, Sentry), and strict AES 7-layer architecture.
- **Out of scope**: other LLM providers (ChatGPT, Claude, Gemini), official
  REST API integrations, cloud-hosted SaaS deployments, and new product
  features (the project is in **Maintenance & Stabilization Mode**).

Core functional specs live in [`modules/core/FRD.md`](modules/core/FRD.md)
(exactly 8 FRs, one per capability + protocol). CLI and MCP surfaces have
their own FRDs.

## Feature Requirements (Prioritized)

AES rule for Core: **1 FR = 1 capability file + 1 contract protocol**.
Product modes (batch / watcher / single / login / MCP) are how surfaces
compose these FRs, not additional core FRs.

### P0 — Must Have (Core, 10 FRs)

- [x] **FR-001 Browser Adapter** — Persistent Chromium/Playwright context,
  stale-lock cleanup, `0o700` session dir, asset blocking, and auth
  triple-check (URL + login form + chat textarea).
  *Accept*: headless run reuses a `login` profile; login page raises
  `AuthRequiredError`.
- [x] **FR-002 File Uploader** — Local-file pre-flight (exists, readable,
  ≤100 MB) and Qwen UI attach with retry/backoff; degrade to text-only on
  failure.
  *Accept*: oversized file never opens the chooser; successful attach shows
  a file card.
- [x] **FR-003 Output Saver** — Atomic UTF-8 write of the AI response plus
  metadata header and `.meta.json` sidecar.
  *Accept*: crash mid-write does not leave a truncated destination file.
- [x] **FR-004 Prompt Injector** — Prepare and inject prompt text via
  four-tier DOM strategy (React setter → ContentEditable → `fill` → `type`).
  *Accept*: empty text is rejected; fixture textarea receives the prompt.
- [x] **FR-005 Send Dispatcher** — Click Send (Enter fallback) only after
  document-parse gate; expose message count / latest text for the stream
  baseline.
  *Accept*: send is blocked while attachment parsing is incomplete.
- [x] **FR-006 Stream Monitor** — Poll until N identical snapshots and
  generation UI is gone; reject CAPTCHA / error-page content.
  *Accept*: stable response is returned; challenge keywords raise
  `AuthRequiredError` / `OutputValidationError`.
- [x] **FR-007 Workspace Provisioner** — First-run XDG dirs,
  `.agents/skills/qwen-web/SKILL.md`, `.qwen-web` symlinks, `.gitignore`.
  *Accept*: `qwen-web-cli init` is idempotent.
- [x] **FR-008 Observability Setup** — structlog + optional OTLP traces +
  optional Sentry + process excepthooks; missing telemetry must not block
  start.
  Owns in-process metrics counters and `status.json` writes (merged helpers,
  not extra capabilities).
  *Accept*: process boots with empty `SENTRY_DSN` and no OTLP endpoint.
- [ ] **FR-009 Linux Guard** — RETIRED. The `fcntl` single-instance lock and
  systemd `sd_notify` readiness were removed; no part of the system references
  them anymore.

### P1 — Should Have (Surfaces)

- [x] **Multi-mode execution**: Batch (folder), Watcher (continuous poll),
  Single (one file), and raw `send_prompt` — all via `ICoreAggregate`.
- [x] **Persistent session login**: `qwen-web-cli login` validates a saved profile
  first; only an invalid session opens a headed browser for CAPTCHA.
- [x] **Atomic file routing**: `input` → `.processing` → `done` / `failed`
  with circuit breaker and rate limiter in the agent.
- [x] **MCP server**: 1:1 tools for send / single / batch / watcher /
  session / audit over stdio.

### P2 — Nice to Have

- [x] **Interactive TUI menu** when the CLI is launched with no args on a TTY.
- [x] **OpenTelemetry tracing** (optional OTLP HTTP export; part of FR-009).
- [x] **Sentry error capture** (optional; part of FR-009).

## Non-functional Requirements (High-level)

- **Performance**: Polling overhead must remain <300 ms/cycle. Network
  traffic reduced by 40–60% via aggressive asset blocking (images, fonts,
  media) outside login mode.
- **Security**: Session tokens stored locally in XDG-compliant directories
  with `0o700`. No exfiltration of credentials. Strict prompt-injection
  defense (scraped text is untrusted data, never agent instructions).
- **Reliability**: Atomic file moves and atomic output writes to guarantee
  zero input/output loss. Graceful degradation on DOM changes via multi-tier
  selector fallbacks. Telemetry is best-effort.
- **Maintainability**: Strict AES 7-Layer Pattern (Taxonomy → Utility →
  Contract → Capabilities → Agent → Surface → Root) enforced by custom
  linting. Core stays at **10 FRs**; do not merge capabilities back into
  bundled requirements.

## Open Questions / Risks

- **Risk**: `chat.qwen.ai` UI DOM changes frequently, breaking Playwright
  selectors.
  - *Mitigation*: Multi-tier fallback selectors and JS extraction that
    relies on structural heuristics. Behavior locked by
    `tests/fixtures/qwen_fixture.html`.
- **Risk**: Cloudflare/CAPTCHA challenges in headless mode.
  - *Mitigation*: Manual `--login` solves CAPTCHA in a headed browser and
    saves persistent session state for subsequent headless runs.
- **Risk**: Two processes sharing one Chromium profile corrupt the session.
  - *Mitigation*: FR-010 single-instance lock on the CLI; MCP skips the lock
    and must not launch a second headed browser against the same profile.
