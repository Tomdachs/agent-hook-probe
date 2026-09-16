# Roadmap

Agent Hook Probe should grow by adding evidence-backed lifecycle contracts, not by becoming a generic coding-agent test suite.

## v0.1

- Codex CLI `exec` lifecycle probe.
- Disposable project-local hooks only.
- SessionStart / UserPromptSubmit / PreToolUse / PostToolUse / Stop / SessionEnd checks.
- Bash tool-use pairing by `tool_use_id`.
- Privacy-minimized text and JSON output.

## Next candidates

- Codex interactive/TUI probe where automation can drive the lifecycle without weakening safety boundaries.
- Regression snapshots across Codex versions and execution surfaces.
- Gemini CLI adapter based on its documented command-hook JSON contract.
- Claude Code adapter after defining a similarly isolated, deterministic fixture.
- GitHub Action wrapper once provider authentication and usage expectations can be made explicit.

## Out of scope

- Automatically fixing hook configuration.
- Installing or trusting arbitrary third-party hooks.
- Replacing provider hook documentation or schema validators.
- Benchmarking model intelligence or answer quality.
- Treating hooks as a complete security enforcement boundary.
