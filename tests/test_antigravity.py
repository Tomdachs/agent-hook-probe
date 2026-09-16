from __future__ import annotations

import json
from pathlib import Path

from agent_hook_probe.antigravity import (
    TARGET_FILE,
    analyse_antigravity_records,
    build_antigravity_command,
    build_antigravity_hooks,
    write_antigravity_fixture,
)


def event(name: str, **extra: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "conversationId": "conversation-1",
        "workspacePaths": ["/disposable/workspace"],
        "transcriptPath": "/private/transcript.jsonl",
        "artifactDirectoryPath": "/private/artifacts",
        "modelName": "example-model",
    }
    payload.update(extra)
    return {
        "event": name,
        "received_at_ns": len(name),
        "payload": payload,
        "parse_error": None,
    }


def passing_records() -> list[dict[str, object]]:
    tool_call = {
        "name": "view_file",
        "args": {"AbsolutePath": TARGET_FILE},
    }
    records = [
        event("PreInvocation", invocationNum=0, initialNumSteps=1),
        event("PostInvocation", invocationNum=0, initialNumSteps=1),
        event("PreToolUse", stepIdx=2, toolCall=tool_call),
        event("PostToolUse", stepIdx=2, toolCall=tool_call, error=""),
        event("PreInvocation", invocationNum=1, initialNumSteps=3),
        event("PostInvocation", invocationNum=1, initialNumSteps=3),
        event("Stop", executionNum=1, terminationReason="model_stop", fullyIdle=True),
    ]
    for index, record in enumerate(records):
        record["received_at_ns"] = index
    return records


def test_passing_records_produce_pass() -> None:
    report = analyse_antigravity_records(
        passing_records(), runtime_version="1.2.4", duration_ms=12, artifact_ok=True
    )
    assert report.result == "PASS"
    assert report.provider == "antigravity"
    assert report.mode == "headless"
    assert all(check.status == "PASS" for check in report.checks)


def test_missing_post_tool_use_fails_pairing() -> None:
    records = [record for record in passing_records() if record["event"] != "PostToolUse"]
    report = analyse_antigravity_records(
        records, runtime_version="1.2.4", duration_ms=12, artifact_ok=True
    )
    by_name = {check.name: check for check in report.checks}
    assert report.result == "FAIL"
    assert by_name["PostToolUse:view_file"].status == "FAIL"
    assert by_name["tool lifecycle pairing"].status == "FAIL"


def test_duplicate_stop_is_detected() -> None:
    records = passing_records() + [
        event("Stop", executionNum=2, terminationReason="model_stop", fullyIdle=True)
    ]
    report = analyse_antigravity_records(
        records, runtime_version="1.2.4", duration_ms=12, artifact_ok=True
    )
    stop = next(check for check in report.checks if check.name == "Stop")
    assert stop.status == "FAIL"
    assert stop.observed == "2"


def test_unbalanced_model_invocations_fail() -> None:
    records = [record for record in passing_records() if record["event"] != "PostInvocation"]
    records.append(event("PostInvocation", invocationNum=0, initialNumSteps=1))
    report = analyse_antigravity_records(
        records, runtime_version="1.2.4", duration_ms=12, artifact_ok=True
    )
    invocation = next(check for check in report.checks if check.name == "model invocation pairing")
    assert invocation.status == "FAIL"


def test_public_report_does_not_embed_raw_payloads() -> None:
    report = analyse_antigravity_records(
        passing_records(), runtime_version="1.2.4", duration_ms=12, artifact_ok=True
    )
    serialized = str(report.to_dict())
    assert "conversation-1" not in serialized
    assert "/private/transcript.jsonl" not in serialized
    assert "/disposable/workspace" not in serialized


def test_fixture_writes_only_project_hook_and_records_dir(tmp_path: Path) -> None:
    records_dir = write_antigravity_fixture(tmp_path)
    assert records_dir == tmp_path / ".agent-hook-probe-records"
    hooks_file = tmp_path / ".agents" / "hooks.json"
    assert hooks_file.is_file()
    hooks = json.loads(hooks_file.read_text(encoding="utf-8"))
    assert set(hooks) == {"agent-hook-probe"}
    assert not (tmp_path / ".gemini").exists()


def test_hook_config_contains_documented_events_and_safe_tool_matcher(tmp_path: Path) -> None:
    hooks = build_antigravity_hooks(tmp_path)
    config = hooks["agent-hook-probe"]
    assert set(config) == {
        "PreInvocation",
        "PostInvocation",
        "PreToolUse",
        "PostToolUse",
        "Stop",
    }
    assert config["PreToolUse"][0]["matcher"] == "^view_file$"
    assert config["PostToolUse"][0]["matcher"] == "^view_file$"
    commands = json.dumps(config)
    assert "agent_hook_probe.recorder" in commands
    assert "--protocol antigravity" in commands


def test_headless_command_keeps_permission_bypass_disabled() -> None:
    command = build_antigravity_command(["agy"], Path("/tmp/probe"), "probe", 90, None)
    assert "--dangerously-skip-permissions" not in command
    assert "--sandbox" in command
    assert command[command.index("--add-dir") + 1] == "/tmp/probe"
    assert command[command.index("--output-format") + 1] == "json"
    assert command[command.index("--print-timeout") + 1] == "90s"


def test_headless_command_accepts_model_override() -> None:
    command = build_antigravity_command(["agy"], Path("/tmp/probe"), "probe", 90, "example-model")
    assert command[command.index("--model") + 1] == "example-model"
