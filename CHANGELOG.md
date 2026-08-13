# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/), and this project adheres to [Semantic Versioning](https://semver.org/).

## [4.1.0] - 2026-08-13

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

- Merge pull request #25 from rakaarwaky/fix/install-clean-reinstall
- fix(install): clean reinstall + repair browser session dir perms
- Merge pull request #30 from rakaarwaky/arena/019ffc13-qwen-web
- fix(ci): restore os.chmod 0o700 on session dir to unbreak pytest job
- Merge pull request #18 from rakaarwaky/worktree-fix-login-browser
- fix: use owner-only 0o700 for session dir (address Codacy permissive chmod)
- fix: chmod session dir to 755 (not 644) before Chrome launch
- fix: use 'or' fallback for null error values (Codacy review)
- fix: propagate login failure through exit code + test stderr output
- fix: print login error instead of silent exit
- fix: update .last_run_ts for test consistency and adjust patch paths in TestRunInit
- fix: update .last_run_ts in tests and add it to .gitignore for consistency
- fix: update .last_run_ts in tests and adjust symlink test paths for consistency
- fix: update .last_run_ts timestamp for test consistency
- fix: update patch paths in tests to reflect module restructuring
- fix: patch XDG constants in test_creates_symlinks to avoid CI environment dependency
- fix: apply ruff format repo-wide and use libasound2t64 for Ubuntu 24.04 CI
- fix: expose generated MCP tools as module-level callables and satisfy ruff format
- fix: streamline async tool generation by consolidating dictionary comprehension
- fix: refactor async tool generation to use a dictionary for improved clarity and access

### Changed

- chore(release): v4.1.0
- Merge pull request #24 from rakaarwaky/dependabot/github_actions/actions-f435755103
- chore(release): v4.1.0
- chore(deps-ci): bump astral-sh/setup-uv in the actions group
- Merge pull request #32 from rakaarwaky/chore/gitignore-worktrees
- chore: gitignore worktrees/ directory
- chore: suppress Semgrep insecure-file-permissions on the 0o700 chmod
- test: lock session dir execute bit (regression for 644 chmod bug)
- chore(release): v4.1.0
- style: fix ruff format in test_main_extended.py
- chore(release): v4.1.0
- Merge pull request #14 from rakaarwaky/worktree-ci-release
- ci: add release automation and PR maintenance workflows
- Merge pull request #11 from rakaarwaky/arena/019ffb5b-qwen-web
- ci: address ruleset review feedback and test failures
- chore: add codacy exclusions for __pycache__, .venv, and uv.lock
- ci: require passing CI gates before merge
- ci: add main branch protection rulesets and apply script
- Merge pull request #9 from rakaarwaky/dependabot/github_actions/actions-9e919e9cab
- Merge pull request #10 from rakaarwaky/dependabot/uv/python-e3c1103597

## [4.1.0] - 2026-08-13

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

- Merge pull request #30 from rakaarwaky/arena/019ffc13-qwen-web
- fix(ci): restore os.chmod 0o700 on session dir to unbreak pytest job
- Merge pull request #18 from rakaarwaky/worktree-fix-login-browser
- fix: use owner-only 0o700 for session dir (address Codacy permissive chmod)
- fix: chmod session dir to 755 (not 644) before Chrome launch
- fix: use 'or' fallback for null error values (Codacy review)
- fix: propagate login failure through exit code + test stderr output
- fix: print login error instead of silent exit
- fix: update .last_run_ts for test consistency and adjust patch paths in TestRunInit
- fix: update .last_run_ts in tests and add it to .gitignore for consistency
- fix: update .last_run_ts in tests and adjust symlink test paths for consistency
- fix: update .last_run_ts timestamp for test consistency
- fix: update patch paths in tests to reflect module restructuring
- fix: patch XDG constants in test_creates_symlinks to avoid CI environment dependency
- fix: apply ruff format repo-wide and use libasound2t64 for Ubuntu 24.04 CI
- fix: expose generated MCP tools as module-level callables and satisfy ruff format
- fix: streamline async tool generation by consolidating dictionary comprehension
- fix: refactor async tool generation to use a dictionary for improved clarity and access
- fix: update actions/checkout and astral-sh/setup-uv versions in CI workflow for consistency
- fix: update gates.sh script for clarity and improve dependency management; enhance linting and testing processes

### Changed

- Merge pull request #24 from rakaarwaky/dependabot/github_actions/actions-f435755103
- chore(release): v4.1.0
- chore(deps-ci): bump astral-sh/setup-uv in the actions group
- Merge pull request #32 from rakaarwaky/chore/gitignore-worktrees
- chore: gitignore worktrees/ directory
- chore: suppress Semgrep insecure-file-permissions on the 0o700 chmod
- test: lock session dir execute bit (regression for 644 chmod bug)
- chore(release): v4.1.0
- style: fix ruff format in test_main_extended.py
- chore(release): v4.1.0
- Merge pull request #14 from rakaarwaky/worktree-ci-release
- ci: add release automation and PR maintenance workflows
- Merge pull request #11 from rakaarwaky/arena/019ffb5b-qwen-web
- ci: address ruleset review feedback and test failures
- chore: add codacy exclusions for __pycache__, .venv, and uv.lock
- ci: require passing CI gates before merge
- ci: add main branch protection rulesets and apply script
- Merge pull request #9 from rakaarwaky/dependabot/github_actions/actions-9e919e9cab
- Merge pull request #10 from rakaarwaky/dependabot/uv/python-e3c1103597
- chore(deps): update setuptools requirement in the python group

## [4.1.0] - 2026-08-13

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

- Merge pull request #30 from rakaarwaky/arena/019ffc13-qwen-web
- fix(ci): restore os.chmod 0o700 on session dir to unbreak pytest job
- Merge pull request #18 from rakaarwaky/worktree-fix-login-browser
- fix: use owner-only 0o700 for session dir (address Codacy permissive chmod)
- fix: chmod session dir to 755 (not 644) before Chrome launch
- fix: use 'or' fallback for null error values (Codacy review)
- fix: propagate login failure through exit code + test stderr output
- fix: print login error instead of silent exit
- fix: update .last_run_ts for test consistency and adjust patch paths in TestRunInit
- fix: update .last_run_ts in tests and add it to .gitignore for consistency
- fix: update .last_run_ts in tests and adjust symlink test paths for consistency
- fix: update .last_run_ts timestamp for test consistency
- fix: update patch paths in tests to reflect module restructuring
- fix: patch XDG constants in test_creates_symlinks to avoid CI environment dependency
- fix: apply ruff format repo-wide and use libasound2t64 for Ubuntu 24.04 CI
- fix: expose generated MCP tools as module-level callables and satisfy ruff format
- fix: streamline async tool generation by consolidating dictionary comprehension
- fix: refactor async tool generation to use a dictionary for improved clarity and access
- fix: update actions/checkout and astral-sh/setup-uv versions in CI workflow for consistency
- fix: update gates.sh script for clarity and improve dependency management; enhance linting and testing processes

### Changed

- Merge pull request #32 from rakaarwaky/chore/gitignore-worktrees
- chore: gitignore worktrees/ directory
- chore: suppress Semgrep insecure-file-permissions on the 0o700 chmod
- test: lock session dir execute bit (regression for 644 chmod bug)
- chore(release): v4.1.0
- style: fix ruff format in test_main_extended.py
- chore(release): v4.1.0
- Merge pull request #14 from rakaarwaky/worktree-ci-release
- ci: add release automation and PR maintenance workflows
- Merge pull request #11 from rakaarwaky/arena/019ffb5b-qwen-web
- ci: address ruleset review feedback and test failures
- chore: add codacy exclusions for __pycache__, .venv, and uv.lock
- ci: require passing CI gates before merge
- ci: add main branch protection rulesets and apply script
- Merge pull request #9 from rakaarwaky/dependabot/github_actions/actions-9e919e9cab
- Merge pull request #10 from rakaarwaky/dependabot/uv/python-e3c1103597
- chore(deps): update setuptools requirement in the python group
- chore(deps-ci): bump the actions group with 3 updates
- Merge pull request #8 from rakaarwaky/arena/019ffb43-qwen-web
- ci: add Dependabot for uv and GitHub Actions updates

## [4.1.0] - 2026-08-13

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

- fix: use 'or' fallback for null error values (Codacy review)
- fix: propagate login failure through exit code + test stderr output
- fix: print login error instead of silent exit
- fix: update .last_run_ts for test consistency and adjust patch paths in TestRunInit
- fix: update .last_run_ts in tests and add it to .gitignore for consistency
- fix: update .last_run_ts in tests and adjust symlink test paths for consistency
- fix: update .last_run_ts timestamp for test consistency
- fix: update patch paths in tests to reflect module restructuring
- fix: patch XDG constants in test_creates_symlinks to avoid CI environment dependency
- fix: apply ruff format repo-wide and use libasound2t64 for Ubuntu 24.04 CI
- fix: expose generated MCP tools as module-level callables and satisfy ruff format
- fix: streamline async tool generation by consolidating dictionary comprehension
- fix: refactor async tool generation to use a dictionary for improved clarity and access
- fix: update actions/checkout and astral-sh/setup-uv versions in CI workflow for consistency
- fix: update gates.sh script for clarity and improve dependency management; enhance linting and testing processes
- fix: update CI workflow repository reference and use latest lint-arwaky-cli release
- fix: simplify CI workflow by consolidating jobs and updating dependencies; enhance self-linting process
- fix: update CI workflow to set up Rust toolchain and install lint-arwaky-cli; update last run timestamp in test fixtures
- fix: update Codacy and GitHub Release action versions; enhance Bandit security scan description; update last run timestamp in test fixtures
- fix: update variable name in send_prompt method for clarity; adjust bandit command in gates.sh; update last run timestamp in test fixtures

### Changed

- style: fix ruff format in test_main_extended.py
- chore(release): v4.1.0
- Merge pull request #14 from rakaarwaky/worktree-ci-release
- ci: add release automation and PR maintenance workflows
- Merge pull request #11 from rakaarwaky/arena/019ffb5b-qwen-web
- ci: address ruleset review feedback and test failures
- chore: add codacy exclusions for __pycache__, .venv, and uv.lock
- ci: require passing CI gates before merge
- ci: add main branch protection rulesets and apply script
- Merge pull request #9 from rakaarwaky/dependabot/github_actions/actions-9e919e9cab
- Merge pull request #10 from rakaarwaky/dependabot/uv/python-e3c1103597
- chore(deps): update setuptools requirement in the python group
- chore(deps-ci): bump the actions group with 3 updates
- Merge pull request #8 from rakaarwaky/arena/019ffb43-qwen-web
- ci: add Dependabot for uv and GitHub Actions updates
- chore: update .gitignore and add .mcp.json configuration for repowise
- refactor: remove noqa comments for clarity and update test fixture timestamp
- refactor: move status_path_for to separate file to fix circular import
- refactor: generate MCP tools from specification table instead of manual wrappers
- refactor: centralize optional import guards to dedicated helper functions

## [4.1.0] - 2026-08-13

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

- fix: update .last_run_ts for test consistency and adjust patch paths in TestRunInit
- fix: update .last_run_ts in tests and add it to .gitignore for consistency
- fix: update .last_run_ts in tests and adjust symlink test paths for consistency
- fix: update .last_run_ts timestamp for test consistency
- fix: update patch paths in tests to reflect module restructuring
- fix: patch XDG constants in test_creates_symlinks to avoid CI environment dependency
- fix: apply ruff format repo-wide and use libasound2t64 for Ubuntu 24.04 CI
- fix: expose generated MCP tools as module-level callables and satisfy ruff format
- fix: streamline async tool generation by consolidating dictionary comprehension
- fix: refactor async tool generation to use a dictionary for improved clarity and access
- fix: update actions/checkout and astral-sh/setup-uv versions in CI workflow for consistency
- fix: update gates.sh script for clarity and improve dependency management; enhance linting and testing processes
- fix: update CI workflow repository reference and use latest lint-arwaky-cli release
- fix: simplify CI workflow by consolidating jobs and updating dependencies; enhance self-linting process
- fix: update CI workflow to set up Rust toolchain and install lint-arwaky-cli; update last run timestamp in test fixtures
- fix: update Codacy and GitHub Release action versions; enhance Bandit security scan description; update last run timestamp in test fixtures
- fix: update variable name in send_prompt method for clarity; adjust bandit command in gates.sh; update last run timestamp in test fixtures
- fix: update last run timestamp in test fixtures
- fix: update last run timestamp in test fixtures
- fix: remove unused import from capabilities_prompt_injector and update test assertions for message counting

### Changed

- Merge pull request #14 from rakaarwaky/worktree-ci-release
- ci: add release automation and PR maintenance workflows
- Merge pull request #11 from rakaarwaky/arena/019ffb5b-qwen-web
- ci: address ruleset review feedback and test failures
- chore: add codacy exclusions for __pycache__, .venv, and uv.lock
- ci: require passing CI gates before merge
- ci: add main branch protection rulesets and apply script
- Merge pull request #9 from rakaarwaky/dependabot/github_actions/actions-9e919e9cab
- Merge pull request #10 from rakaarwaky/dependabot/uv/python-e3c1103597
- chore(deps): update setuptools requirement in the python group
- chore(deps-ci): bump the actions group with 3 updates
- Merge pull request #8 from rakaarwaky/arena/019ffb43-qwen-web
- ci: add Dependabot for uv and GitHub Actions updates
- chore: update .gitignore and add .mcp.json configuration for repowise
- refactor: remove noqa comments for clarity and update test fixture timestamp
- refactor: move status_path_for to separate file to fix circular import
- refactor: generate MCP tools from specification table instead of manual wrappers
- refactor: centralize optional import guards to dedicated helper functions
- refactor: centralize status path derivation to shared utility
- refactor: consolidate DOM selector fallback into try_selectors helper

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
