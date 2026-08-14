# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/), and this project adheres to [Semantic Versioning](https://semver.org/).

## [4.1.0] - 2026-08-14

### Added

- feat: update linting rules and ignore specific patterns for browser automation safety
- feat: update README and CLI commands for qwen-web-cli integration
- feat: add test suite initialization for qwen-web-cli
- feat: enhance CI workflow with quality gates and add local gates script
- feat: add atomic JSON file writing utility and update test fixture timestamp
- feat: refactor DOM helper functions and update related capabilities for improved visibility checks
- feat: add utilities for async event-loop isolation and Chrome binary discovery
- feat: add DOM action utilities for Playwright pages
- feat: refine exception handling across multiple modules
- feat: enable AES501 to AES506 rules in lint configuration
- feat: fix AES202/AES203 violations — 0 codacy & aes linter violations
- feat: add IMetricsProtocol import and create QWEN.md file; remove unused Path import
- feat: update protocols to use taxonomy value objects for metrics and status handling
- feat: add Codacy configuration to exclude scripts and tests from analysis
- feat: remove outdated key patterns section from AGENTS.md
- feat: remove unnecessary comment and clean up SKILL.md formatting
- feat: remove obsolete module verification script
- feat: implement atomic file writing with error handling in _write_file_atomic function
- feat: update protocol implementations and enhance class constructors with dependency injection
- feat: enhance class definitions and add __repr__ methods for better debugging

### Fixed

- fix(shared): address review feedback for event compatibility
- fix(shared): keep lazy legacy exports analyzer-friendly
- fix(shared): align event value aliases with mypy
- fix(shared): satisfy taxonomy self-lint after refactor
- fix(core): preserve explicit sender timeout
- fix(core): complete capabilities and aggregate test coverage
- Merge pull request #98 from rakaarwaky/fix/mcp-transport-and-spec
- fix(core): refresh circuit breaker state on reconfigure
- fix(mcp): harden stdio proxy validation
- fix: apply CodeRabbit auto-fixes
- fix(core): address PR review pipeline findings
- fix(cli): address review feedback for interactive errors
- fix(core): enforce pipeline routing outcomes and lifecycle gates
- fix(cli): enforce surface precedence and linux lifecycle
- fix(mcp): protect stdio and generate audit log tool
- Merge pull request #47 from rakaarwaky/fix/interactive-missing-appconfig
- fix: pass built config to run command in interactive mode
- Merge pull request #46 from rakaarwaky/arena/019ffc60-qwen-web
- fix: keep manual login browser open and verify session
- Merge pull request #31 from rakaarwaky/arena/019ffc14-qwen-web

### Changed

- Merge pull request #107 from rakaarwaky/refactor/shared-taxonomy-event
- refactor(shared): extract event and error taxonomy
- chore(release): v4.1.0
- test(core): honor processing outcome contract
- refactor(core): simplify breaker refresh helper
- style(mcp): organize test imports
- chore(core): keep self-lint compatible
- style(mcp): satisfy lint for generated signatures
- test(mcp): use buffered stdout fixtures
- test(core): avoid private breaker state access
- test(cli): strengthen interactive review coverage
- chore(release): v4.1.0
- Merge pull request #60 from rakaarwaky/arena/019ffcd8-qwen-web
- refactor(core): merge metrics and status into observability (12→10)
- docs(core): split PRD/FRD into 10 capability-aligned FRs
- chore(release): v4.1.0
- Merge pull request #44 from rakaarwaky/worktree/docs-update
- docs: lock scope to Stabilization Mode (PRD, README, FRDs, skill)
- chore(release): v4.1.0
- chore: remove obsolete .last_run_ts fixture file

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
