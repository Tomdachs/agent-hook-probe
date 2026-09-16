from __future__ import annotations

from pathlib import Path

from agent_hook_probe.codex import (
    TARGET_FILE,
    analyse_codex_records,
    build_codex_exec_command,
    build_codex_hooks_override,
    write_codex_fixture,
)


def event(name: str, **extra: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "session_id": "session-1",
        "cwd": "/disposable/workspace",
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
    tool_input = {"command": f"printf ok > {TARGET_FILE}"}
    return [
        event("SessionStart", source="startup"),
        event("UserPromptSubmit", turn_id="turn-1"),
        event(
            "PreToolUse",
            turn_id="turn-1",
            tool_name="Bash",
            tool_use_id="call-1",
            tool_input=tool_input,
        ),
        event(
            "PostToolUse",
            turn_id="turn-1",
            tool_name="Bash",
            tool_use_id="call-1",
            tool_input=tool_input,
            tool_response="ok",
        ),
        event("Stop", turn_id="turn-1"),
        event("SessionEnd", reason="other"),
    ]


def test_passing_records_produce_pass() -> None:
    report = analyse_codex_records(
        passing_records(), runtime_version="codex-cli 9.9.9", duration_ms=12, artifact_ok=True
    )
    assert report.result == "PASS"
    assert all(check.status == "PASS" for check in report.checks)


def test_missing_post_tool_use_fails_pairing() -> None:
    records = [record for record in passing_records() if record["event"] != "PostToolUse"]
    report = analyse_codex_records(
        records, runtime_version="codex-cli 9.9.9", duration_ms=12, artifact_ok=True
    )
    by_name = {check.name: check for check in report.checks}
    assert report.result == "FAIL"
    assert by_name["PostToolUse:Bash"].status == "FAIL"
    assert by_name["tool lifecycle pairing"].status == "FAIL"


def test_duplicate_stop_is_detected() -> None:
    records = passing_records() + [event("Stop", turn_id="turn-1")]
    report = analyse_codex_records(
        records, runtime_version="codex-cli 9.9.9", duration_ms=12, artifact_ok=True
    )
    stop = next(check for check in report.checks if check.name == "Stop")
    assert stop.status == "FAIL"
    assert stop.observed == "2"


def test_public_report_does_not_embed_raw_payloads() -> None:
    report = analyse_codex_records(
        passing_records(), runtime_version="codex-cli 9.9.9", duration_ms=12, artifact_ok=True
    )
    serialized = str(report.to_dict())
    assert "session-1" not in serialized
    assert "/disposable/workspace" not in serialized
    assert "printf ok" not in serialized


def test_fixture_only_creates_probe_record_directory(tmp_path: Path) -> None:
    records_dir = write_codex_fixture(tmp_path)
    assert records_dir == tmp_path / ".agent-hook-probe-records"
    assert records_dir.is_dir()
    assert not (tmp_path / ".codex").exists()


def test_session_hook_override_contains_expected_events(tmp_path: Path) -> None:
    records_dir = write_codex_fixture(tmp_path)
    override = build_codex_hooks_override(records_dir)
    for event_name in (
        "SessionStart",
        "UserPromptSubmit",
        "PreToolUse",
        "PostToolUse",
        "Stop",
        "SessionEnd",
    ):
        assert f"{event_name}=[" in override
    assert 'matcher="^Bash$"' in override
    assert "agent_hook_probe.recorder" in override


def test_exec_command_bypasses_only_generated_hook_trust(tmp_path: Path) -> None:
    records_dir = write_codex_fixture(tmp_path)
    command = build_codex_exec_command(["codex"], tmp_path, records_dir, "probe", None)
    assert "--dangerously-bypass-hook-trust" in command
    assert "--dangerously-bypass-approvals-and-sandbox" not in command
    assert command[command.index("-s") + 1] == "workspace-write"
    assert "--ignore-user-config" in command
    assert "--ephemeral" in command
    assert "features.hooks=true" in command
    assert any(part.startswith("hooks={") for part in command)


def test_exec_command_accepts_model_override(tmp_path: Path) -> None:
    records_dir = write_codex_fixture(tmp_path)
    command = build_codex_exec_command(["codex"], tmp_path, records_dir, "probe", "example-model")
    assert command[command.index("--model") + 1] == "example-model"
