# Agent Hook Probe

[![CI](https://github.com/Tomdachs/agent-hook-probe/actions/workflows/ci.yml/badge.svg)](https://github.com/Tomdachs/agent-hook-probe/actions/workflows/ci.yml) [![Release](https://img.shields.io/github/v/release/Tomdachs/agent-hook-probe)](https://github.com/Tomdachs/agent-hook-probe/releases/latest) [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**Verify that your coding-agent hooks actually fire.**

Agent Hook Probe runs disposable workspaces against real coding-agent runtimes and checks observable lifecycle behavior. It catches missing hooks, duplicates, broken pre/post pairing, execution-surface regressions, lifecycle-order regressions, and payload-contract drift instead of assuming a valid config means a working hook.

## Provider support

| Provider | Surface | Probe canary | Status |
| --- | --- | --- | --- |
| Codex CLI | `codex exec` | one sandboxed shell write | `v0.3.0`; live-verified on Codex CLI 0.154.0 |
| Codex CLI | interactive TUI | one sandboxed shell write | `v0.3.0`; live-verified on WSL with Codex CLI 0.154.0 |
| Antigravity CLI | headless `agy -p` | one workspace `view_file` | `v0.3.0`; live-verified on Antigravity CLI 1.2.4 |
| Claude Code | — | — | Planned |

The Codex TUI probe is currently supported on Linux, WSL, and macOS. Windows can still use the Codex `exec` probe.

## Try it

Python 3.11+, Git, the target provider CLI, and an authenticated provider session are required. Each probe performs one minimal model turn, so normal provider usage applies.

```bash
uvx --from https://github.com/Tomdachs/agent-hook-probe/releases/download/v0.3.0/agent_hook_probe-0.3.0-py3-none-any.whl agent-hook-probe codex
```

Probe the interactive Codex TUI instead of `exec`:

```bash
uvx --from https://github.com/Tomdachs/agent-hook-probe/releases/download/v0.3.0/agent_hook_probe-0.3.0-py3-none-any.whl agent-hook-probe codex --surface tui
```

Probe Antigravity with the same release wheel:

```bash
uvx --from https://github.com/Tomdachs/agent-hook-probe/releases/download/v0.3.0/agent_hook_probe-0.3.0-py3-none-any.whl agent-hook-probe antigravity
```

Typical Codex result:

```text
Agent Hook Probe 0.3.0
Runtime: codex-cli 0.154.0
Mode:    tui

PASS  SessionStart             expected 1, observed 1
PASS  UserPromptSubmit         expected 1, observed 1
PASS  PreToolUse:Bash          expected 1 target shell hook, observed 1
PASS  PostToolUse:Bash         expected 1 target shell hook, observed 1
PASS  tool lifecycle pairing   expected matching non-empty tool_use_id, observed paired
PASS  Stop                     expected 1, observed 1
PASS  SessionEnd               expected 1, observed 1
PASS  payload schema           expected documented common fields, observed valid
PASS  probe artifact           expected hook-probe-ok, observed hook-probe-ok

Result: PASS
```

## Codex execution surfaces

`agent-hook-probe codex` keeps `exec` as the default for backward compatibility. Use `--surface tui` to run the same lifecycle contract through the interactive terminal UI.

The TUI adapter creates a real pseudo-terminal, starts Codex with a 120x40 terminal, waits for the canary turn to complete, then closes the idle TUI with `Ctrl+C` so `SessionEnd` can be observed. It does not scrape the screen to decide pass/fail; hook records and the canary remain the source of truth.

Both Codex surfaces inject the probe-generated hooks and disposable-project trust as per-invocation config. They do not add the temporary workspace to `~/.codex/config.toml`. The TUI additionally sets `history.persistence="none"` so its probe session is not retained in normal Codex history.

## Antigravity adapter

Antigravity CLI documents workspace hooks in `.agents/hooks.json` and headless execution with `agy -p`. The adapter uses a read-only `view_file` canary and does **not** enable `--dangerously-skip-permissions`.

The Antigravity probe checks:

- at least one paired `PreInvocation` / `PostInvocation` sequence;
- exactly one target `PreToolUse` and `PostToolUse` for `view_file`;
- matching `stepIdx` and `toolCall` across those target tool hooks;
- exactly one `Stop` event;
- common camelCase payload fields;
- runtime order `PreToolUse < PostToolUse < Stop`;
- the probe-owned canary remained intact while the target read occurred.

If Antigravity is installed but not signed in, the command exits with setup error code `2`. It does not misreport authentication failure as a hook regression.

## Safety model

Every provider probe owns a newly created temporary Git repository and deletes it by default. The public report never includes raw hook payloads, prompts, transcript paths, absolute workspace paths, credentials, or provider stdout/stderr.

For Codex, hooks are injected through per-invocation config. Codex's hook-trust automation flag is used only for the probe-generated hook definition. The model-generated canary command remains inside `workspace-write`, and the approval/sandbox bypass is never used. Disposable project trust is also per-invocation, so the probe does not persist temporary trust entries in the user's Codex config.

For Antigravity, the probe writes `.agents/hooks.json` plus a probe-owned canary only inside its disposable repository, explicitly adds that directory as the active workspace, and asks `view_file` to read the canary. It enables Antigravity's terminal sandbox and does not edit global Antigravity settings, hooks, permissions, or existing projects.

Use `--keep-fixture` only when you intentionally need raw disposable records for debugging. Retained fixtures can contain provider-supplied session identifiers and transcript paths.

See [docs/safety.md](docs/safety.md), [docs/codex-contract.md](docs/codex-contract.md), and [docs/antigravity-contract.md](docs/antigravity-contract.md).

## JSON and CI

```bash
agent-hook-probe codex --json
agent-hook-probe codex --surface tui --json
agent-hook-probe antigravity --json
```

Exit codes:

- `0`: all checked hook contracts passed;
- `1`: the provider ran, but one or more observed hook contracts failed;
- `2`: setup/runtime error such as missing CLI, authentication failure, missing Git, unsupported surface, or timeout.

CI unit tests do not call a model. Live provider probes remain separate because they require authentication and consume provider usage.

## Options

Both provider commands support `--model`, `--timeout`, `--keep-fixture`, and `--json`. You can point at a specific executable with `--codex` or `--agy`. Codex additionally supports `--surface exec|tui`.

```bash
agent-hook-probe codex --surface tui --timeout 120
agent-hook-probe antigravity --model <model> --timeout 120
```

## Why a live probe?

A hook file can parse correctly and still fail because discovery, trust, execution surface, tool routing, or lifecycle dispatch changed. Agent Hook Probe turns provider lifecycle contracts into small executable regression tests without modifying real projects.

Provider references:

- Codex hooks: https://developers.openai.com/codex/hooks
- Antigravity hooks: https://antigravity.google/docs/hooks
- Antigravity headless mode: https://antigravity.google/docs/cli/headless/
- Antigravity permissions: https://antigravity.google/docs/cli/permissions

## Development

```bash
git clone https://github.com/Tomdachs/agent-hook-probe.git
cd agent-hook-probe
uv sync --frozen
uv run ruff check .
uv run ruff format --check .
uv run pytest
uv build
```

CI validates Python 3.11-3.14 on Linux, Windows, and macOS. Provider-specific live smoke tests are release gates, not CI jobs with hidden credentials.

## Scope and roadmap

Keep the project narrow: lifecycle-hook conformance, not model benchmarking, config repair, or a generic agent test suite. See [ROADMAP.md](ROADMAP.md).

## License

MIT
