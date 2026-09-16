# Antigravity hook contract

The Antigravity adapter targets the documented Antigravity CLI hook contract and headless execution surface.

## Probe surface

- Runtime: `agy` CLI.
- Execution mode: one headless `agy -p` turn with JSON output.
- Hook discovery: project-local `.agents/hooks.json` inside a disposable repository.
- Canary tool: `view_file` reading one pre-created probe-owned file in the disposable workspace.
- Permission posture: no `--dangerously-skip-permissions`; terminal sandbox enabled.

Antigravity documents file writes inside the active workspace as auto-allowed in headless mode, so the probe does not need to edit the user's global permission settings.

## Events checked

`PreInvocation` and `PostInvocation` can occur more than once because a one-tool turn commonly needs a model invocation before the tool and another after it. The probe therefore requires at least one invocation and equal Pre/Post counts rather than a hard-coded count of one.

The target `PreToolUse` and `PostToolUse` each must occur exactly once for `view_file`. Antigravity's public hook schema does not expose a Codex-style tool-use ID, so the probe pairs the events using equal `stepIdx` and equal `toolCall` payloads.

`Stop` must occur exactly once after the target post-tool hook. The probe also validates the documented common camelCase fields: `conversationId`, `workspacePaths`, `transcriptPath`, `artifactDirectoryPath`, and `modelName`.

## Hook responses

The recorder returns `{"decision":"allow"}` for the probe-owned `PreToolUse` so the canary tool is not blocked by the hook itself. It returns a non-`continue` decision for `Stop`, allowing normal termination. Other observed events return an empty JSON object because their output fields are optional for this passive probe.

## Version notes

The implementation was developed against the public Antigravity CLI 1.2.x documentation and locally installed CLI 1.2.4. A tagged `v0.2.0` release is gated on an authenticated live smoke because the maintainer WSL environment did not already contain an Antigravity account session or `GEMINI_API_KEY`.

Official references:

- https://antigravity.google/docs/hooks
- https://antigravity.google/docs/cli/headless/
- https://antigravity.google/docs/cli/permissions
