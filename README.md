# Agent Hook Probe

[![CI](https://github.com/Tomdachs/agent-hook-probe/actions/workflows/ci.yml/badge.svg)](https://github.com/Tomdachs/agent-hook-probe/actions/workflows/ci.yml) [![Release](https://img.shields.io/github/v/release/Tomdachs/agent-hook-probe)](https://github.com/Tomdachs/agent-hook-probe/releases/latest) [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**Verify that your coding-agent hooks actually fire.**

Agent Hook Probe runs disposable workspaces against real coding-agent runtimes and checks observable lifecycle behavior. It catches missing hooks, duplicates, broken pre/post pairing, lifecycle-order regressions, and payload-contract drift instead of assuming a valid config means a working hook.

## Provider support

| Provider | Surface | Probe canary | Status |
| --- | --- | --- | --- |
| Codex CLI | `codex exec` | one sandboxed shell write | Released in `v0.1.0`; live-verified |
| Antigravity CLI | headless `agy -p` | one workspace `view_file` | `v0.2.0`; live-verified on Antigravity CLI 1.2.4 |
| Claude Code | — | — | Planned |

## Try it

Python 3.11+, Git, Codex CLI, and an authenticated Codex session are required. The probe performs one minimal model turn, so normal provider usage applies.

```bash
uvx --from https://github.com/Tomdachs/agent-hook-probe/releases/download/v0.2.0/agent_hook_probe-0.2.0-py3-none-any.whl agent-hook-probe codex
```

Antigravity uses the same release wheel:

```bash
uvx --from https://github.com/Tomdachs/agent-hook-probe/releases/download/v0.2.0/agent_hook_probe-0.2.0-py3-none-any.whl agent-hook-probe antigravity
```

Typical Codex output:

```text
Agent Hook Probe 0.1.0
Runtime: codex-cli 0.154.0
Mode:    exec

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

## Antigravity adapter

Antigravity CLI documents workspace hooks in `.agents/hooks.json` and headless execution with `agy -p`. The adapter uses a read-only `view_file` canary and does **not** enable `--dangerously-skip-permissions`.

After installing the `main` branch and authenticating Antigravity once:

```bash
agent-hook-probe antigravity
```

The Antigravity probe checks:

- at least one paired `PreInvocation` / `PostInvocation` sequence;
- exactly one target `PreToolUse` and `PostToolUse` for `view_file`;
- matching `stepIdx` and `toolCall` across those target tool hooks;
- exactly one `Stop` event;
- common camelCase payload fields documented by Antigravity;
- runtime order `PreToolUse < PostToolUse < Stop`;
- the canary file was actually written with the expected content.

If Antigravity is installed but not signed in, the command exits with setup error code `2` and tells you to run `agy` once. It does not misreport authentication failure as a hook regression.

## Safety model

Every provider probe owns a newly created temporary Git repository and deletes it by default. The public report never includes raw hook payloads, prompts, transcript paths, absolute workspace paths, credentials, or provider stdout/stderr.

For Codex, hooks are injected through per-invocation config. Codex's hook-trust automation flag is used only for the probe-generated hooks; the model-generated command remains inside `workspace-write` and the approval/sandbox bypass is never used.

For Antigravity, the probe writes `.agents/hooks.json` plus a probe-owned canary only inside its disposable repository, explicitly adds that directory as the active workspace, and asks `view_file` to read the canary. It also enables Antigravity's terminal sandbox. It does not edit `~/.gemini/antigravity-cli/settings.json`, `~/.gemini/config/hooks.json`, permissions, or existing projects.

Use `--keep-fixture` only when you intentionally need raw disposable records for debugging. Retained fixtures can contain provider-supplied session identifiers and transcript paths.

See [docs/safety.md](docs/safety.md), [docs/codex-contract.md](docs/codex-contract.md), and [docs/antigravity-contract.md](docs/antigravity-contract.md).

## JSON and CI

```bash
agent-hook-probe codex --json
agent-hook-probe antigravity --json
```

Exit codes:

- `0`: all checked hook contracts passed;
- `1`: the provider ran, but one or more observed hook contracts failed;
- `2`: setup/runtime error such as missing CLI, authentication failure, missing Git, or timeout.

CI unit tests do not call a model. Live provider probes remain separate because they require authentication and consume provider usage.

## Options

Both provider commands support `--model`, `--timeout`, `--keep-fixture`, and `--json`. You can also point at a specific executable with `--codex` or `--agy`.

```bash
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

CI validates Python 3.11-3.14 on Linux, Windows, and macOS. Provider-specific live smoke tests are documented release gates, not CI jobs with hidden credentials.

## Scope and roadmap

Keep the project narrow: lifecycle-hook conformance, not model benchmarking, config repair, or a generic agent test suite. See [ROADMAP.md](ROADMAP.md).

## License

MIT
