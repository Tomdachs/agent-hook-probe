# Agent Hook Probe

[![CI](https://github.com/Tomdachs/agent-hook-probe/actions/workflows/ci.yml/badge.svg)](https://github.com/Tomdachs/agent-hook-probe/actions/workflows/ci.yml) [![Release](https://img.shields.io/github/v/release/Tomdachs/agent-hook-probe)](https://github.com/Tomdachs/agent-hook-probe/releases/latest) [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**Verify that your coding-agent hooks actually fire.**

Agent Hook Probe runs a disposable Codex workspace, injects probe-owned lifecycle hooks as per-invocation config, performs one tiny shell task, and checks what really happened. It catches missing hooks, duplicate lifecycle events, broken PreToolUse/PostToolUse pairing, and payload-contract drift instead of assuming a valid config means a working hook.

> v0.1 supports **Codex CLI `exec` mode**. Claude Code and Gemini CLI adapters are planned, not claimed as supported.

## Try it

Python 3.11+, Git, Codex CLI, and an authenticated Codex session are required. The probe performs **one minimal model turn**, so normal Codex usage applies.

```bash
uvx --from https://github.com/Tomdachs/agent-hook-probe/releases/download/v0.1.0/agent_hook_probe-0.1.0-py3-none-any.whl agent-hook-probe codex
```

Typical output:

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

## What it proves

The Codex probe checks observable runtime behavior, not just JSON syntax:

- `SessionStart`, `UserPromptSubmit`, `Stop`, and `SessionEnd` each fire once for the probe turn;
- the exact probe shell call emits one `PreToolUse` and one `PostToolUse`;
- both tool hooks carry the same non-empty `tool_use_id`;
- hook payloads contain the documented common fields;
- the shell command actually ran and created the probe-owned canary file.

This targets bugs where hooks are configured and visible but silently do not run on a particular execution path.

## Safety model

The probe never edits your repository or your existing Codex hooks. It creates a temporary Git repository containing only recorder files and canary output, while the generated hooks are injected through Codex session flags for that invocation. The fixture is deleted by default.

Codex requires non-managed hooks to be trusted before execution. For this one-off generated fixture, Agent Hook Probe uses Codex's documented `--dangerously-bypass-hook-trust` automation flag. It **does not** use `--dangerously-bypass-approvals-and-sandbox`; the model-generated command stays inside Codex's `workspace-write` sandbox.

The normal report never includes raw hook payloads, prompts, transcript paths, absolute workspace paths, credentials, or provider output. Use `--keep-fixture` only when you intentionally need the raw disposable records for debugging.

See [docs/safety.md](docs/safety.md) and [docs/codex-contract.md](docs/codex-contract.md).

## JSON and CI

```bash
agent-hook-probe codex --json
```

Exit codes:

- `0`: all checked hook contracts passed;
- `1`: Codex ran, but one or more observed hook contracts failed;
- `2`: setup/runtime error such as missing Codex, missing Git, authentication failure, or timeout.

The JSON report is privacy-minimized and intentionally does not embed raw event payloads.

## Options

Use a specific model when you want to keep probe cost predictable:

```bash
agent-hook-probe codex --model <model>
```

Keep the disposable fixture for diagnosis:

```bash
agent-hook-probe codex --keep-fixture
```

The kept fixture can contain the probe prompt, shell command, working path, session identifiers, and transcript path supplied by Codex. Review it before sharing.

## Why a live probe?

A hook file can parse correctly and still fail at runtime because discovery, trust, execution mode, tool routing, or lifecycle dispatch changed. Codex documents hook discovery, trust, event schemas, and Bash tool coverage at https://developers.openai.com/codex/hooks. Agent Hook Probe turns those contracts into a small executable regression test.

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

CI validates Python 3.11-3.14 on Linux, Windows, and macOS. Unit tests do not call a model; the live provider probe is intentionally separate from CI because it requires authentication and consumes provider usage.

## Scope and roadmap

v0.1 is deliberately narrow: Codex CLI `exec` hook conformance with a disposable shell canary. Planned follow-ups include additional Codex execution surfaces and provider adapters where the lifecycle contract can be tested without touching user projects. See [ROADMAP.md](ROADMAP.md).

## License

MIT
