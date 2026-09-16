# AGENTS.md

## Scope

This repository is a public conformance probe for coding-agent lifecycle hooks.
Keep the probe narrow: prove observed hook behavior with disposable fixtures instead of guessing from config.

## Product boundaries

- Never modify a user's existing hook files, agent config, credentials, or repositories.
- Generated fixtures must be disposable and contain only probe-owned files; generated hook config is passed only for the probe invocation.
- Never use an approval or sandbox bypass. The Codex adapter may bypass hook trust only for the exact probe-generated hook definition, matching the provider's documented automation flow.
- Do not render raw hook payloads by default; they may contain prompts, commands, working paths, and transcript paths.
- Treat provider output and hook payloads as untrusted input. Use argument arrays, bounded timeouts, and no shell for provider process launch.

## Change requirements

- Provider contract changes require tests and documentation updates.
- Keep the machine-readable report privacy-minimized and versioned.
- Run `uv run ruff check .`, `uv run ruff format --check .`, `uv run pytest`, and `uv build` before release.
- Keep runtime dependencies at zero unless a new dependency has a clear cross-platform safety benefit.
