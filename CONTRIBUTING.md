# Contributing

Thanks for helping improve Agent Hook Probe.

## Before opening an issue

Use the latest release when possible. Include the privacy-minimized `--json` report, provider version, OS, and execution surface. Do not paste authentication data, private repository content, or raw hook records unless you have reviewed them first.

## Development

Requirements: Git, Python 3.11+, and `uv`.

```bash
uv sync --frozen
uv run ruff check .
uv run ruff format --check .
uv run pytest
uv build
```

Unit tests must not consume provider usage. Live provider probes belong in explicit manual/release smoke checks.

## Pull requests

- Add tests for lifecycle-contract or report changes.
- Keep fixtures disposable and provider adapters isolated.
- Never weaken the provider sandbox or approval model to make a test pass.
- Preserve privacy-minimized default output.
- Update README/docs when public commands, checked events, or safety behavior changes.
- Prefer zero runtime dependencies and standard-library subprocess handling.

## New provider adapters

A useful adapter proposal links the provider's current official hook documentation, names a deterministic execution surface, explains how trust/approval is handled, and demonstrates that the probe can avoid user repositories and secrets.
