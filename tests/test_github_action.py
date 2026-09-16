from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[1] / "scripts" / "github_action.py"
SPEC = importlib.util.spec_from_file_location("github_action", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
ActionInputError = MODULE.ActionInputError
build_command = MODULE.build_command


def base_env(**overrides: str) -> dict[str, str]:
    env = {
        "AHP_ACTION_PATH": "/action",
        "AHP_OPERATION": "probe",
        "AHP_PROVIDER": "codex",
        "AHP_SURFACE": "exec",
        "AHP_TIMEOUT": "180",
        "AHP_JSON": "false",
        "AHP_OVERWRITE_SNAPSHOT": "false",
    }
    env.update(overrides)
    return env


def test_codex_probe_command_is_argument_safe() -> None:
    command = build_command(
        base_env(
            AHP_MODEL="example model",
            AHP_BASELINE="snapshots/base file.json",
            AHP_SAVE_SNAPSHOT="snapshots/current file.json",
            AHP_JSON="true",
        )
    )
    assert command[:5] == ["uvx", "--from", str(Path("/action")), "agent-hook-probe", "codex"]
    assert command[command.index("--surface") + 1] == "exec"
    assert command[command.index("--model") + 1] == "example model"
    assert command[command.index("--baseline") + 1] == "snapshots/base file.json"
    assert command[command.index("--save-snapshot") + 1] == "snapshots/current file.json"
    assert "--json" in command


def test_antigravity_probe_does_not_pass_codex_surface() -> None:
    command = build_command(base_env(AHP_PROVIDER="antigravity"))
    assert command[4] == "antigravity"
    assert "--surface" not in command


def test_diff_requires_both_paths() -> None:
    with pytest.raises(ActionInputError, match="requires baseline and current"):
        build_command(base_env(AHP_OPERATION="diff", AHP_BASELINE="baseline.json"))


def test_diff_command_does_not_include_provider_options() -> None:
    command = build_command(
        base_env(
            AHP_OPERATION="diff",
            AHP_BASELINE="baseline.json",
            AHP_CURRENT="current.json",
            AHP_JSON="true",
        )
    )
    assert command == [
        "uvx",
        "--from",
        str(Path("/action")),
        "agent-hook-probe",
        "diff",
        "baseline.json",
        "current.json",
        "--json",
    ]


@pytest.mark.parametrize(
    ("key", "value", "message"),
    [
        ("AHP_OPERATION", "other", "operation must be"),
        ("AHP_PROVIDER", "other", "provider must be"),
        ("AHP_SURFACE", "other", "surface must be"),
        ("AHP_TIMEOUT", "zero", "timeout must be an integer"),
        ("AHP_TIMEOUT", "0", "timeout must be at least"),
        ("AHP_JSON", "yes", "must be true or false"),
    ],
)
def test_invalid_inputs_are_rejected(key: str, value: str, message: str) -> None:
    with pytest.raises(ActionInputError, match=message):
        build_command(base_env(**{key: value}))


def test_antigravity_rejects_nondefault_surface() -> None:
    with pytest.raises(ActionInputError, match="only supported for the codex"):
        build_command(base_env(AHP_PROVIDER="antigravity", AHP_SURFACE="tui"))


def test_overwrite_requires_snapshot_path() -> None:
    with pytest.raises(ActionInputError, match="requires save_snapshot"):
        build_command(base_env(AHP_OVERWRITE_SNAPSHOT="true"))


def test_action_path_is_required() -> None:
    with pytest.raises(ActionInputError, match="AHP_ACTION_PATH is required"):
        build_command(base_env(AHP_ACTION_PATH=""))
