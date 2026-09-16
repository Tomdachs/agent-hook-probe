# Codex contract checked by v0.3

Research snapshot: 2026-09-16.

Source of truth: https://developers.openai.com/codex/hooks

The Codex adapter checks the same lifecycle contract across two execution surfaces: non-interactive `codex exec` and the interactive TUI.

| Contract | Probe expectation |
| --- | --- |
| Hook source | per-invocation session config (`-c hooks=...`) |
| Hook feature | per-invocation `features.hooks=true` |
| Disposable project trust | per-invocation `projects={...trust_level="trusted"}` only |
| Session start | one `SessionStart` with startup matcher |
| Prompt submit | one `UserPromptSubmit` |
| Shell pre-hook | one `PreToolUse`, canonical `tool_name` `Bash` |
| Shell post-hook | one `PostToolUse`, canonical `tool_name` `Bash` |
| Pairing | pre/post carry the same non-empty `tool_use_id` |
| Turn stop | one `Stop` |
| Session end | one `SessionEnd` |
| Common payload | `session_id`, `cwd`, `hook_event_name` |
| Canary | exact probe-owned file content `hook-probe-ok` |

## Exec surface

`agent-hook-probe codex` runs `codex exec` with `--ephemeral`, ignores normal user config, enables the probe-generated hooks, selects `workspace-write`, and validates the lifecycle around one exact Bash command.

## TUI surface

`agent-hook-probe codex --surface tui` launches the real interactive terminal UI inside a pseudo-terminal. It supplies the same generated hooks and sandbox, sets `history.persistence="none"`, waits for the canary turn to finish, then sends `Ctrl+C` to the idle TUI so `SessionEnd` can be observed.

The TUI screen is not parsed to decide conformance. Hook recorder files and the canary are the evidence source. This avoids coupling the probe to terminal rendering changes.

The TUI surface currently requires Linux, WSL, or macOS. Windows remains supported for the exec surface.

Codex documents that shell commands and unified exec are visible to `PreToolUse` and `PostToolUse` as `Bash`. Specialized execution paths can opt out, so this probe does not claim that hooks form a universal security boundary.
