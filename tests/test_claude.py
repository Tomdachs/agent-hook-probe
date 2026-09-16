from __future__ import annotations

import json
import subprocess
from pathlib import Path

from agent_hook_probe.claude import (
    TARGET_FILE,
    _headless_error,
    analyse_claude_records,
    build_claude_command,
    build_claude_settings,
    write_claude_fixture,
)


def event(name: str, **extra: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "session_id": "session-1",
        "transcript_path": "/private/transcript.jsonl",
        "cwd": "/disposable/workspace",
        "permission_mode": "dontAsk",
        "hook_event_name": name,
    }
    payload.update(extra)
    return {
        "event": name,
        "received_at_ns": 1,
        "payload": payload,
        "parse_error": None,
    }


def passing_records() -> list[dict[str, object]]:
    tool_input = {"file_path": f"/disposable/workspace/{TARGET_FILE}"}
    records = [
        event("SessionStart", source="startup"),
        event("UserPromptSubmit", prompt="probe"),
        event("PreToolUse", tool_name="Read", tool_use_id="toolu-1", tool_input=tool_input),
        event(
            "PostToolUse",
            tool_name="Read",
            tool_use_id="toolu-1",
            tool_input=tool_input,
            tool_response={"content": "hook-probe-ok"},
        ),
        event("Stop", stop_hook_active=False, last_assistant_message="HOOK_PROBE_DONE"),
        event("SessionEnd", reason="other"),
    ]
    for index, record in enumerate(records):
        record["received_at_ns"] = index
    return records


def test_passing_records_produce_pass() -> None:
    report = analyse_claude_records(
        passing_records(), runtime_version="2.1.267 (Claude Code)", duration_ms=12, artifact_ok=True
    )
    assert report.result == "PASS"
    assert report.provider == "claude"
    assert report.mode == "headless"
    assert all(check.status == "PASS" for check in report.checks)


def test_missing_post_tool_use_fails_pairing() -> None:
    records = [record for record in passing_records() if record["event"] != "PostToolUse"]
    report = analyse_claude_records(
        records, runtime_version="2.1.267 (Claude Code)", duration_ms=12, artifact_ok=True
    )
    by_name = {check.name: check for check in report.checks}
    assert report.result == "FAIL"
    assert by_name["PostToolUse:Read"].status == "FAIL"
    assert by_name["tool lifecycle pairing"].status == "FAIL"


def test_public_report_does_not_embed_raw_payloads() -> None:
    report = analyse_claude_records(
        passing_records(), runtime_version="2.1.267 (Claude Code)", duration_ms=12, artifact_ok=True
    )
    serialized = str(report.to_dict())
    assert "session-1" not in serialized
    assert "/private/transcript.jsonl" not in serialized
    assert "/disposable/workspace" not in serialized


def test_fixture_writes_explicit_settings_and_records_dir(tmp_path: Path) -> None:
    records_dir, settings_path = write_claude_fixture(tmp_path)
    assert records_dir == tmp_path / ".agent-hook-probe-records"
    assert settings_path == tmp_path / ".agent-hook-probe-claude-settings.json"
    assert settings_path.is_file()
    assert not (tmp_path / ".claude").exists()


def test_settings_contain_documented_events_and_read_matcher(tmp_path: Path) -> None:
    settings = build_claude_settings(tmp_path)
    hooks = settings["hooks"]
    assert set(hooks) == {
        "SessionStart",
        "UserPromptSubmit",
        "PreToolUse",
        "PostToolUse",
        "Stop",
        "SessionEnd",
    }
    assert hooks["SessionStart"][0]["matcher"] == "startup"
    assert hooks["PreToolUse"][0]["matcher"] == "Read"
    assert hooks["PostToolUse"][0]["matcher"] == "Read"
    assert "agent_hook_probe.recorder" in json.dumps(settings)


def test_headless_command_is_restricted_and_read_only(tmp_path: Path) -> None:
    settings = tmp_path / "settings.json"
    command = build_claude_command(["claude"], settings, "probe", None)
    assert "--restricted" in command
    assert command[command.index("--settings") + 1] == str(settings)
    assert command[command.index("--tools") + 1] == "Read"
    assert command[command.index("--permission-mode") + 1] == "dontAsk"
    assert command[command.index("--permission-prompts") + 1] == "none"
    assert "--no-session-persistence" in command
    assert "--dangerously-skip-permissions" not in command
    assert "Bash" not in command
    assert "Edit" not in command
    assert "Write" not in command


def test_headless_command_accepts_model_override(tmp_path: Path) -> None:
    command = build_claude_command(["claude"], tmp_path / "settings.json", "probe", "sonnet")
    assert command[command.index("--model") + 1] == "sonnet"


def test_not_logged_in_is_setup_error() -> None:
    payload = {"is_error": True, "result": "Not logged in · Please run /login"}
    completed = subprocess.CompletedProcess(["claude"], 1, json.dumps(payload), "")
    assert _headless_error(completed) == (
        "Claude Code is not authenticated; run 'claude auth login' and complete sign-in"
    )


def test_usage_limit_is_setup_error() -> None:
    payload = {"is_error": True, "result": "You've hit your usage limit."}
    completed = subprocess.CompletedProcess(["claude"], 1, json.dumps(payload), "")
    assert _headless_error(completed) == (
        "Claude Code cannot run because the provider usage limit is exhausted"
    )


def test_lifecycle_order_is_checked() -> None:
    records = passing_records()
    records[2]["received_at_ns"], records[3]["received_at_ns"] = 4, 2
    records.sort(key=lambda item: int(item["received_at_ns"]))
    report = analyse_claude_records(
        records, runtime_version="2.1.267 (Claude Code)", duration_ms=12, artifact_ok=True
    )
    check = next(item for item in report.checks if item.name == "lifecycle order")
    assert check.status == "FAIL"
