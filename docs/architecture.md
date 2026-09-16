# Architecture

Agent Hook Probe separates fixture generation, provider execution, event recording, and conformance analysis.

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

The provider adapter never needs to read the user's hook files. The recorder intentionally stores raw payloads only inside the disposable fixture so the analyzer can inspect fields such as `hook_event_name`, `tool_name`, and `tool_use_id`.

## Report boundary

The public report includes provider/version, check names, expected/observed summaries, result, and duration. It does not include the model prompt, raw provider stdout/stderr, hook payloads, session ids, transcript paths, or normal fixture paths.
