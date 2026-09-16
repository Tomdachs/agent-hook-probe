# Architecture

Agent Hook Probe separates fixture generation, provider execution, event recording, and conformance analysis. Provider adapters share the same privacy-minimized report model but keep provider-specific lifecycle semantics explicit.

## Codex flow

1. Resolve `codex` and read its version.
2. Create a temporary Git repository.
3. Build a per-invocation `hooks={...}` session override owned by the probe.
4. Configure lifecycle hooks to call `python -m agent_hook_probe.recorder`.
5. Launch one `codex exec` turn with user config ignored and `workspace-write` mode.
6. Ask for one exact shell command that writes a canary inside the temporary workspace.
7. Read recorder files after Codex exits.
8. Compare observed events and tool ids with the documented lifecycle contract.
9. Render only normalized results and delete the fixture unless debugging was explicitly requested.

## Antigravity flow

1. Resolve `agy` and read its version.
2. Create a temporary Git repository.
3. Write a single named hook set to the fixture's `.agents/hooks.json`.
4. Configure Pre/PostInvocation, Pre/PostToolUse, and Stop handlers to call the recorder.
5. Launch one headless `agy -p` turn with JSON output and terminal sandbox enabled.
6. Pre-create a canary in the temporary workspace and ask Antigravity to use `view_file` exactly once.
7. Parse only the terminal status from provider JSON, then read probe-owned recorder files.
8. Compare observed invocation counts, target tool pairing, Stop count, ordering, common fields, and canary content.
9. Delete the fixture unless debugging was explicitly requested.

The Antigravity adapter does not modify `~/.gemini` settings or hooks. Project-local hook discovery is exercised because that is part of the runtime contract the probe is intended to verify.

## Recorder protocol

The recorder stores each stdin payload as one JSON record in a probe-owned directory. Codex handlers use the generic empty response. Antigravity handlers return only the minimal protocol response required by the event: allow the probe-owned PreToolUse and allow Stop to terminate.

Raw records are analyzer input, not report output.

## Report boundary

The public report includes provider/version, execution surface, check names, expected/observed summaries, result, and duration. It does not include the model prompt, raw provider stdout/stderr, hook payloads, session/conversation ids, transcript paths, or normal fixture paths.
