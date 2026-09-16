# Claude Code contract checked by v0.6

Research snapshot: 2026-09-16.

Sources of truth:

- https://code.claude.com/docs/en/hooks
- https://code.claude.com/docs/en/hooks-guide
- https://code.claude.com/docs/en/cli-reference
- https://code.claude.com/docs/en/permissions

The v0.6 adapter probes Claude Code print mode (`claude -p`) with one read-only `Read` call in a disposable Git repository.

| Contract | Probe expectation |
| --- | --- |
| Hook source | explicit per-invocation `--settings` file inside the disposable fixture |
| Session isolation | `--restricted`, `--no-session-persistence`, no normal user/project setting sources |
| Tool surface | `--tools Read`; MCP tools denied |
| Permission mode | `dontAsk`; no bypass mode |
| Session start | one `SessionStart` with `source: startup` |
| Prompt submit | one `UserPromptSubmit` |
| Read pre-hook | one target `PreToolUse` with canonical `tool_name: Read` |
| Read post-hook | one target `PostToolUse` with canonical `tool_name: Read` |
| Pairing | target pre/post carry the same non-empty `tool_use_id` |
| Turn stop | one `Stop` |
| Session end | one `SessionEnd` |
| Common payload | `session_id`, `cwd`, `hook_event_name` |
| Lifecycle order | SessionStart < UserPromptSubmit < PreToolUse < PostToolUse < Stop < SessionEnd |

The canary is pre-created and only read. The adapter does not expose Bash, Edit, or Write to the probe turn and never uses `--dangerously-skip-permissions`.

Claude Code managed policy still applies by design. Restricted mode excludes normal user/project/local settings, while managed settings remain an administrative boundary that the probe does not attempt to bypass.
