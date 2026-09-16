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

## Claude Code flow

1. Resolve `claude` and read its version.
2. Create a temporary Git repository, a pre-existing read-only canary, and an explicit probe settings file.
3. Configure SessionStart, UserPromptSubmit, Read Pre/PostToolUse, Stop, and SessionEnd command hooks to call the recorder.
4. Launch `claude -p` in restricted mode with only the `Read` built-in tool exposed and MCP tools denied.
5. Disable session persistence and permission prompts; use `dontAsk` rather than a permission bypass.
6. Ask Claude to read the canary exactly once.
7. Parse only provider completion/setup state from JSON output, then analyze the probe-owned hook records.
8. Verify exact lifecycle counts, Read pairing by `tool_use_id`, common fields, ordering, and unchanged canary content.
9. Delete the fixture unless debugging was explicitly requested.

Claude's normal user/project/local settings are not loaded in restricted mode. Managed policy remains in force and is intentionally not bypassed.

## Recorder protocol

The recorder stores each stdin payload as one JSON record in a probe-owned directory. Codex handlers use the generic empty response. Antigravity handlers return only the minimal protocol response required by the event.

Raw records are analyzer input, not report output.

## Report boundary

The public report includes provider/version, execution surface, check names, expected/observed summaries, result, and duration. It does not include the model prompt, raw provider stdout/stderr, hook payloads, session/conversation ids, transcript paths, or normal fixture paths.

## Regression snapshot flow

Provider adapters still produce the same `ProbeReport`. Snapshot handling sits after that boundary: it removes any retained `fixture_path`, adds a UTC capture timestamp, and writes schema-versioned JSON only when requested. Comparison operates entirely on normalized snapshots, so offline `diff` never launches a provider or reads hook payloads.

The diff engine keys checks by stable check name. Runtime-version changes are metadata; PASS-to-FAIL and removed checks are regressions, while added checks and changed expectations are contract drift. This keeps provider execution concerns separate from historical comparison.

## GitHub Action flow

The composite action is a thin transport layer over the same CLI. It pins `setup-uv`, validates Action inputs in a standard-library Python helper, and invokes the package from the checked-out action source with `uvx --from`. It does not duplicate provider contracts or diff logic.

Offline `diff` never invokes a provider. Live `probe` expects the caller to have selected, installed, and authenticated the provider CLI before the Action step. Action inputs are converted to a subprocess argument array without `eval` or shell command construction.
