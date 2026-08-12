# Agent Instructions

<!-- lean-ctx -->

## lean-ctx

lean-ctx is active — the MCP tools replace native equivalents.
Full rules: LEAN-CTX.md (open on demand — do not auto-load).

<!-- /lean-ctx -->

---

### Key Patterns

1. **Exception hierarchy**: Base `QwenCliError` with domain-specific subclasses (`AuthRequiredError`, `NetworkTimeoutError`, `OutputValidationError`, etc.)
2. **Centralized types**: `AppConfig`, `CircuitBreaker`, `RateLimiter`, `LifecycleEmitter` in `types.py`
3. **XDG compliance**: Paths follow XDG Base Directory Specification
