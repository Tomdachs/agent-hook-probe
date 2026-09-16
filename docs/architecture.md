# Architecture

Agent Hook Probe separates fixture generation, provider execution, event recording, and conformance analysis. Provider adapters share the same privacy-minimized report model but keep provider-specific lifecycle semantics explicit.

## Codex exec flow

1. Resolve `codex` and read its version.
2. Create a temporary Git repository.
3. Build per-invocation `hooks={...}` and disposable-project trust overrides.
4. Configure lifecycle hooks to call `python -m agent_hook_probe.recorder`.
5. Launch one `codex exec` turn with user config ignored and `workspace-write` mode.
6. Ask for one exact shell command that writes a canary inside the temporary workspace.
7. Read recorder files after Codex exits.
8. Compare observed events and tool ids with the lifecycle contract.
9. Render only normalized results and delete the fixture unless debugging was explicitly requested.

The project trust override is scoped to the process invocation. The temporary workspace is not added to `~/.codex/config.toml`.

## Codex TUI flow

1. Build the same disposable repository, hooks, canary prompt, and session-only trust override as the exec probe.
2. Set `history.persistence="none"` for the invocation.
3. Open a real pseudo-terminal sized to 120x40 with `TERM=xterm-256color`.
4. Launch interactive Codex with `workspace-write`, approval policy `never`, and inline screen mode.
5. Drain terminal output without using it as the conformance oracle.
6. Wait until the canary proves the model turn executed, allowing a short grace period for `Stop`.
7. Send `Ctrl+C` to the idle TUI and wait for normal exit so `SessionEnd` can fire.
8. Analyze the same hook records and canary contract as `exec`.

The TUI probe is currently POSIX-only because it relies on the standard pseudo-terminal APIs available on Linux, WSL, and macOS.

## Antigravity flow

1. Resolve `agy` and read its version.
2. Create a temporary Git repository.
3. Write a single named hook set to the fixture's `.agents/hooks.json`.
4. Configure Pre/PostInvocation, Pre/PostToolUse, and Stop handlers to call the recorder.
5. Launch one headless `agy -p` turn with JSON output and terminal sandbox enabled.
6. Pre-create a canary and ask Antigravity to use `view_file` exactly once.
7. Parse only terminal status from provider JSON, then read probe-owned recorder files.
8. Compare invocation counts, target tool pairing, Stop count, ordering, common fields, and canary content.
9. Delete the fixture unless debugging was explicitly requested.

The Antigravity adapter does not modify global Antigravity settings or hooks. Project-local hook discovery is exercised because that is part of the runtime contract being tested.

## Recorder protocol

The recorder stores each stdin payload as one JSON record in a probe-owned directory. Codex handlers use the generic empty response. Antigravity handlers return only the minimal protocol response required by the event.

Raw records are analyzer input, not report output.

## Report boundary

The public report includes provider/version, execution surface, check names, expected/observed summaries, result, and duration. It does not include the model prompt, raw provider stdout/stderr, hook payloads, session/conversation ids, transcript paths, or normal fixture paths.
