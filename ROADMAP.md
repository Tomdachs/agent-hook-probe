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
- Stop, payload-schema, lifecycle-order, and canary checks.
- No global Antigravity settings changes and no permission bypass.
- Live-verified against Antigravity CLI 1.2.4 on WSL.

## v0.3 — released

- Codex interactive/TUI execution-surface probe on Linux, WSL, and macOS.
- Real PTY automation with hook/canary evidence rather than screen scraping.
- TUI `SessionEnd` verification through normal idle `Ctrl+C` exit.
- Session-only disposable-project trust for both Codex exec and TUI probes.
- TUI history disabled with `history.persistence="none"`.
- Live-verified locally against Codex CLI 0.154.0 on WSL before release.

## v0.4 — released

- Privacy-minimized regression snapshots for every supported provider surface.
- Live `--baseline` comparison and offline `diff` command.
- PASS-to-FAIL regression, check removal, expected-contract drift, and improvement classification.
- Runtime-version changes are informational rather than failures by themselves.
- Snapshot overwrite protection and provider/surface compatibility checks.

## v0.5 — released

- Composite GitHub Action for offline snapshot diff and live provider probes.
- Provider installation and authentication remain caller-controlled.
- Action inputs are validated and passed as argument arrays without shell evaluation.
- CI self-tests the action for both unchanged and regression snapshots.
- Raw fixture retention is intentionally not exposed by the Action.

## v0.5.1 — released

- Composite Action outputs for status, provider, execution mode, runtime version, and change count.
- Privacy-minimized GitHub Job Summary for probe and diff runs.
- Cross-platform CI asserts the Action output contract on Linux, Windows, and macOS.
- Release workflow self-tests the output contract before publishing artifacts.

## v0.5.2 — release candidate

- Floating `v0.5` Action tag tracks backward-compatible 0.5.x patch releases.
- Release workflow updates that minor tag only after a stable `vX.Y.Z` release succeeds.
- Floating minor-tag pushes do not trigger a second package release.

## Next candidates

- Claude Code adapter is implemented on `feat/claude-adapter`, but its full live release gate is parked until an eligible Claude Code authentication environment is available.

## Out of scope

- Automatically fixing hook configuration.
- Installing or trusting arbitrary third-party hooks.
- Replacing provider hook documentation or schema validators.
- Benchmarking model intelligence or answer quality.
- Treating hooks as a complete security enforcement boundary.
