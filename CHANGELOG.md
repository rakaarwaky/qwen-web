# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/), and this project adheres to [Semantic Versioning](https://semver.org/).

## [4.1.0] - 2026-08-14

### Added

- Hardened MCP stdio transport with context-aware stdout isolation and audit-log tooling.
- Added aggregate-boundary, CLI LinuxGuard, audit-tail, sender, and DOM-helper regression coverage.
- Added qwen-web-cli integration documentation and quality-gate traceability updates.

### Fixed

- Preserved complete AppConfig values through single, batch, and watcher dispatch.
- Enforced atomic role-relative routing and correct success/failure outcomes.
- Enforced CLI LinuxGuard lock and READY/STOPPING lifecycle notifications while keeping MCP lock-free.
- Refreshed CircuitBreaker state after reconfiguration and expiry.
- Honored SenderConfig fallback and explicit timeout precedence, including SendDispatchError on total dispatch failure.
- Bounded audit JSONL tail reads and handled blank, malformed, truncated, empty, and non-positive-limit cases.
- Preserved manual-login and interactive CLI error propagation.

### Changed

- Consolidated observability metrics and status handling under the current taxonomy and protocol model.
- Strengthened CI, self-lint, Codacy, and release quality gates.

## [4.0.0] - 2026-08-10

### Added
- MCP server mode (`--mcp`) for AI agent integration
- File attachment upload support
- Role-based directory structure for prompt organization
- Watcher mode (`--watch`) for continuous file processing
- Single-instance lock to prevent concurrent runs
- Systemd sd_notify integration for service readiness
- OpenTelemetry distributed tracing
- Sentry error monitoring
- Structured logging with structlog
- Lifecycle event emission system
- XDG-compliant configuration paths
- `init` command for first-time setup
- `login` command for manual authentication
- Regression test suite with behavior locks
- GitHub Actions CI pipeline (lint + test matrix)

### Changed
- Migrated to modular architecture: `prompt_injector`, `sender`, `streamer`, `saver`
- Response extraction now uses JS-based text detection (robust against CSS class changes)
- Default file paths reorganized under `~/.qwen-web/`
- Navigation wait strategy changed to `domcontentloaded`
- Python 3.10+ required

### Fixed
- AuthRequiredError handling in MCP tools and CLI
- Role-based done/failed paths for nested role folders
- Hardcoded user home path replaced with generic `qwc` command
- License metadata string format in pyproject.toml

### Removed
- Legacy role prompts
- Stale task fixtures

## [3.x] - 2026-07-01

### Added
- Initial CLI automation for Qwen AI Web
- Playwright-based browser session management
- Markdown prompt file processing
- Batch and single file modes
- Output file writing with metadata headers
