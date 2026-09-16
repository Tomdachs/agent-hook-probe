from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


class ActionInputError(ValueError):
    pass


def _value(env: dict[str, str], name: str, default: str = "") -> str:
    return env.get(name, default).strip()


def _boolean(env: dict[str, str], name: str, default: bool = False) -> bool:
    raw = _value(env, name, "true" if default else "false").lower()
    if raw not in {"true", "false"}:
        raise ActionInputError(f"{name} must be true or false")
    return raw == "true"


def build_command(env: dict[str, str]) -> list[str]:
    raw_action_path = _value(env, "AHP_ACTION_PATH")
    if not raw_action_path:
        raise ActionInputError("AHP_ACTION_PATH is required")
    action_path = Path(raw_action_path)

    operation = _value(env, "AHP_OPERATION", "probe").lower()
    command = ["uvx", "--from", str(action_path), "agent-hook-probe"]
    json_output = _boolean(env, "AHP_JSON")

    if operation == "diff":
        baseline = _value(env, "AHP_BASELINE")
        current = _value(env, "AHP_CURRENT")
        if not baseline or not current:
            raise ActionInputError("diff mode requires baseline and current snapshot paths")
        command.extend(("diff", baseline, current))
        if json_output:
            command.append("--json")
        return command

    if operation != "probe":
        raise ActionInputError("operation must be probe or diff")

    provider = _value(env, "AHP_PROVIDER", "codex").lower()
    if provider not in {"codex", "antigravity"}:
        raise ActionInputError("provider must be codex or antigravity")
    command.append(provider)

    surface = _value(env, "AHP_SURFACE", "exec").lower()
    if provider == "codex":
        if surface not in {"exec", "tui"}:
            raise ActionInputError("surface must be exec or tui")
        command.extend(("--surface", surface))
    elif surface != "exec":
        raise ActionInputError("surface is only supported for the codex provider")

    timeout = _value(env, "AHP_TIMEOUT", "180")
    try:
        timeout_value = int(timeout)
    except ValueError as exc:
        raise ActionInputError("timeout must be an integer") from exc
    if timeout_value < 1:
        raise ActionInputError("timeout must be at least 1 second")
    command.extend(("--timeout", str(timeout_value)))

    model = _value(env, "AHP_MODEL")
    if model:
        command.extend(("--model", model))
    baseline = _value(env, "AHP_BASELINE")
    if baseline:
        command.extend(("--baseline", baseline))
    snapshot = _value(env, "AHP_SAVE_SNAPSHOT")
    overwrite = _boolean(env, "AHP_OVERWRITE_SNAPSHOT")
    if overwrite and not snapshot:
        raise ActionInputError("overwrite_snapshot=true requires save_snapshot")
    if snapshot:
        command.extend(("--save-snapshot", snapshot))
        if overwrite:
            command.append("--overwrite-snapshot")
    if json_output:
        command.append("--json")
    return command


def main() -> int:
    try:
        command = build_command(dict(os.environ))
    except ActionInputError as exc:
        print(f"Agent Hook Probe action: ERROR: {exc}", file=sys.stderr)
        return 2
    return subprocess.run(command, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
