# Roadmap

Agent Hook Probe should grow by adding evidence-backed lifecycle contracts, not by becoming a generic coding-agent test suite.

## v0.1 — released

- Codex CLI `exec` lifecycle probe.
- Disposable fixture and per-invocation probe hooks.
- SessionStart / UserPromptSubmit / PreToolUse / PostToolUse / Stop / SessionEnd checks.
- Bash tool-use pairing by `tool_use_id`.
- Privacy-minimized text and JSON output.

## v0.2 — released

- Antigravity CLI headless adapter using project-local `.agents/hooks.json`.
- Passive Pre/PostInvocation checks plus read-only `view_file` Pre/PostToolUse pairing.
- Stop, payload-schema, lifecycle-order, and canary-artifact checks.
- No global Antigravity settings changes and no permission bypass.
- Live-verified against Antigravity CLI 1.2.4 on WSL.

## Next candidates

- Codex interactive/TUI probe where automation can drive the lifecycle without weakening safety boundaries.
- Regression snapshots across provider versions and execution surfaces.
- Claude Code adapter after defining a similarly isolated, deterministic fixture.
- GitHub Action wrapper once provider authentication and usage expectations can be made explicit.

## Out of scope

- Automatically fixing hook configuration.
- Installing or trusting arbitrary third-party hooks.
- Replacing provider hook documentation or schema validators.
- Benchmarking model intelligence or answer quality.
- Treating hooks as a complete security enforcement boundary.
