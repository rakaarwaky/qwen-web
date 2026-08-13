# PRD — qwen-web

## Problem Statement
Power users, system administrators, and local AI agents need to process large volumes of prompts through `chat.qwen.ai` without relying on official, rate-limited, or unavailable REST APIs. Manual interaction is slow, un-auditable, and prone to human error. Existing browser automation scripts are often brittle, lack observability, and fail to handle edge cases like CAPTCHAs, network timeouts, or dynamic UI changes gracefully. Furthermore, maintaining these scripts over time becomes a liability as codebases degrade into spaghetti code, making AI-assisted maintenance unsafe.

## Goals & Success Metrics
- Goal 1: Achieve 99.9% successful end-to-end pipeline execution for batch and watcher workloads on native Linux environments.
- Goal 2: Maintain strict AES 7-layer architectural compliance to ensure AI agents can safely modify, refactor, and maintain the codebase without introducing regressions.
- Goal 3: Provide seamless 1:1 feature parity between CLI and MCP interfaces for local AI agent integration.

## User Personas
- **Power User / Developer**: Runs batch markdown prompts locally, needs reliable file routing (`input` -> `.processing` -> `done`/`failed`) and detailed JSONL audit logs to track token usage and processing times.
- **AI Agent (via MCP)**: Interacts with the tool programmatically to send prompts, process files, and read audit logs without managing browser lifecycles or DOM selectors.
- **System Administrator**: Deploys the watcher mode as a background `systemd` service, relies on `sd_notify` for health checks, `fcntl` single-instance locks to prevent duplicate runs, and structured JSON logs for aggregation.

## Scope
- **In scope**: `chat.qwen.ai` web automation, Playwright persistent sessions, Batch/Watcher/Single/Interactive/MCP modes, Linux-native guards, structured observability (structlog, OpenTelemetry, Sentry), and strict AES 7-layer architecture enforcement.
- **Out of scope**: Support for other LLM providers (ChatGPT, Claude, Gemini), official REST API integrations, cloud-hosted SaaS deployments, and adding new features (the project is currently in strict **Maintenance & Stabilization Mode**).

## Feature Requirements (Prioritized)

### P0 — Must Have
- [x] **Multi-mode Execution**: Support Batch (folder processing), Watcher (continuous polling), and Single (one-off file) modes.
- [x] **Persistent Session Management**: Manual `--login` mode to solve CAPTCHAs and save persistent session cookies/LocalStorage.
- [x] **Atomic File Routing**: Safe file movement using atomic locks to prevent data loss during crashes.
- [x] **Multi-tier DOM Injection**: Fallback strategies for injecting text into dynamic React/ContentEditable input fields.
- [x] **Response Stability Polling**: Detect AI generation completion via DOM polling and stability checks.

### P1 — Should Have
- [x] **MCP Server Integration**: Expose all core functionalities as Model Context Protocol tools over stdio.
- [x] **Structured Audit Logging**: JSONL audit trail with run IDs, durations, and character counts.
- [x] **Linux Native Guards**: `fcntl` single-instance file locks and systemd `sd_notify` socket notifications.
- [x] **Circuit Breaker & Rate Limiter**: Prevent IP bans and API throttling via sliding-window failure tracking.

### P2 — Nice to Have
- [x] **Interactive TUI Menu**: Fallback interactive menu for users who prefer not to use CLI flags.
- [x] **OpenTelemetry Tracing**: Optional OTLP HTTP span export for distributed tracing.
- [x] **Sentry Error Capture**: Automatic unhandled exception reporting.

## Non-functional Requirements (High-level)
- **Performance**: Polling overhead must remain <300ms/cycle. Network traffic reduced by 40-60% via aggressive asset blocking (images, fonts, media).
- **Security**: Session tokens stored locally in XDG-compliant directories. No exfiltration of credentials. Strict prompt injection defense (scraped text is treated as untrusted data, never as agent instructions).
- **Reliability**: Atomic file moves (`safe_move`) to guarantee zero input loss. Graceful degradation on DOM changes via multi-tier selector fallbacks.
- **Maintainability**: Strict adherence to the AES 7-Layer Pattern (Taxonomy -> Utility -> Contract -> Capabilities -> Agent -> Surface -> Root) enforced by custom linting rules.

## Open Questions / Risks
- **Risk**: `chat.qwen.ai` UI DOM changes frequently, breaking Playwright selectors.
  - *Mitigation*: Multi-tier fallback selectors and JS-based extraction logic that relies on structural heuristics rather than brittle class names.
- **Risk**: Cloudflare/CAPTCHA challenges in headless mode.
  - *Mitigation*: Manual `--login` mode to solve CAPTCHAs in a headed browser and save the persistent session state for subsequent headless runs.
