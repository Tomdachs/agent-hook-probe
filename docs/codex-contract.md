# Codex contract checked by v0.1

Research snapshot: 2026-09-16.

Source of truth: https://developers.openai.com/codex/hooks

The v0.1 probe focuses on the documented `codex exec` lifecycle around one Bash call.

| Contract | Probe expectation |
| --- | --- |
| Hook source | per-invocation session config (`-c hooks=...`) |
| Hook feature | per-invocation `features.hooks=true` |
| Session start | one `SessionStart` with startup matcher |
| Prompt submit | one `UserPromptSubmit` |
| Shell pre-hook | one `PreToolUse`, canonical `tool_name` `Bash` |
| Shell post-hook | one `PostToolUse`, canonical `tool_name` `Bash` |
| Pairing | pre/post carry the same non-empty `tool_use_id` |
| Turn stop | one `Stop` |
| Session end | one `SessionEnd` |
| Common payload | `session_id`, `cwd`, `hook_event_name` |

Codex documents that shell commands and unified exec are visible to `PreToolUse` and `PostToolUse` as `Bash`. It also notes that specialized paths can opt out, so this probe does not claim that hooks form a universal security boundary.

The model is instructed to use one exact shell command. The analyzer selects only hook records whose Bash input references the probe canary, so unrelated provider behavior is not mistaken for the target lifecycle pair.
