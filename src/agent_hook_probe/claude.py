from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from . import __version__
from .model import CheckResult, ProbeReport

TARGET_FILE = ".agent-hook-probe-output"
TARGET_VALUE = "hook-probe-ok"
CORE_EVENTS = (
    "SessionStart",
    "UserPromptSubmit",
    "PreToolUse",
    "PostToolUse",
    "Stop",
    "SessionEnd",
)


class ClaudeProbeSetupError(RuntimeError):
    pass


def _handler_command(event: str, records_dir: Path) -> str:
    args = [
        sys.executable,
        "-m",
        "agent_hook_probe.recorder",
        "--event",
        event,
        "--output-dir",
        str(records_dir),
    ]
    return subprocess.list2cmdline(args) if os.name == "nt" else shlex.join(args)


def build_claude_settings(records_dir: Path) -> dict[str, Any]:
    def handler(event: str) -> dict[str, Any]:
        return {
            "type": "command",
            "command": _handler_command(event, records_dir),
            "timeout": 3 if event == "SessionEnd" else 10,
        }

    hooks: dict[str, list[dict[str, Any]]] = {}
    for event in CORE_EVENTS:
        group: dict[str, Any] = {"hooks": [handler(event)]}
        if event == "SessionStart":
            group["matcher"] = "startup"
        elif event in {"PreToolUse", "PostToolUse"}:
            group["matcher"] = "Read"
        hooks[event] = [group]
    return {"hooks": hooks}


def write_claude_fixture(workspace: Path) -> tuple[Path, Path]:
    records_dir = workspace / ".agent-hook-probe-records"
    records_dir.mkdir(parents=True, exist_ok=True)
    settings_path = workspace / ".agent-hook-probe-claude-settings.json"
    settings_path.write_text(
        json.dumps(build_claude_settings(records_dir), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return records_dir, settings_path


def _load_records(records_dir: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in records_dir.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(data, dict):
            records.append(data)
    records.sort(key=lambda item: int(item.get("received_at_ns", 0)))
    return records


def _payload(record: dict[str, Any]) -> dict[str, Any]:
    payload = record.get("payload")
    return payload if isinstance(payload, dict) else {}


def _target_tool_records(records: list[dict[str, Any]], event: str) -> list[dict[str, Any]]:
    matched: list[dict[str, Any]] = []
    for record in records:
        if record.get("event") != event:
            continue
        payload = _payload(record)
        if payload.get("tool_name") != "Read":
            continue
        serialized_input = json.dumps(payload.get("tool_input"), ensure_ascii=False)
        if TARGET_FILE in serialized_input:
            matched.append(record)
    return matched


def _count_check(records: list[dict[str, Any]], event: str) -> CheckResult:
    observed = sum(record.get("event") == event for record in records)
    return CheckResult(
        name=event,
        status="PASS" if observed == 1 else "FAIL",
        expected="1",
        observed=str(observed),
    )


def analyse_claude_records(
    records: list[dict[str, Any]],
    *,
    runtime_version: str,
    duration_ms: int,
    artifact_ok: bool,
    fixture_path: str | None = None,
) -> ProbeReport:
    checks: list[CheckResult] = [
        _count_check(records, "SessionStart"),
        _count_check(records, "UserPromptSubmit"),
    ]

    pre = _target_tool_records(records, "PreToolUse")
    post = _target_tool_records(records, "PostToolUse")
    checks.append(
        CheckResult(
            name="PreToolUse:Read",
            status="PASS" if len(pre) == 1 else "FAIL",
            expected="1 target read hook",
            observed=str(len(pre)),
        )
    )
    checks.append(
        CheckResult(
            name="PostToolUse:Read",
            status="PASS" if len(post) == 1 else "FAIL",
            expected="1 target read hook",
            observed=str(len(post)),
        )
    )

    paired = False
    if len(pre) == len(post) == 1:
        pre_id = _payload(pre[0]).get("tool_use_id")
        post_id = _payload(post[0]).get("tool_use_id")
        paired = isinstance(pre_id, str) and bool(pre_id) and pre_id == post_id
    checks.append(
        CheckResult(
            name="tool lifecycle pairing",
            status="PASS" if paired else "FAIL",
            expected="matching non-empty tool_use_id",
            observed="paired" if paired else "unpaired",
        )
    )
    checks.extend((_count_check(records, "Stop"), _count_check(records, "SessionEnd")))

    schema_ok = bool(records)
    schema_detail = ""
    for record in records:
        payload = _payload(record)
        event = record.get("event")
        if record.get("parse_error") is not None:
            schema_ok = False
            schema_detail = "at least one hook payload was not valid JSON"
            break
        if payload.get("hook_event_name") != event:
            schema_ok = False
            schema_detail = "hook_event_name did not match the configured event"
            break
        if not isinstance(payload.get("session_id"), str) or not payload.get("session_id"):
            schema_ok = False
            schema_detail = "a payload was missing session_id"
            break
        if not isinstance(payload.get("cwd"), str) or not payload.get("cwd"):
            schema_ok = False
            schema_detail = "a payload was missing cwd"
            break
    checks.append(
        CheckResult(
            name="payload schema",
            status="PASS" if schema_ok else "FAIL",
            expected="documented common fields",
            observed="valid" if schema_ok else "invalid or absent",
            detail=schema_detail,
        )
    )
    checks.append(
        CheckResult(
            name="probe canary",
            status="PASS" if artifact_ok else "FAIL",
            expected=TARGET_VALUE,
            observed=TARGET_VALUE if artifact_ok else "missing or different",
        )
    )

    order_ok = False
    if len(pre) == len(post) == 1:
        indexes = {
            event: [i for i, record in enumerate(records) if record.get("event") == event]
            for event in ("SessionStart", "UserPromptSubmit", "Stop", "SessionEnd")
        }
        if all(len(indexes[event]) == 1 for event in indexes):
            order_ok = (
                indexes["SessionStart"][0]
                < indexes["UserPromptSubmit"][0]
                < records.index(pre[0])
                < records.index(post[0])
                < indexes["Stop"][0]
                < indexes["SessionEnd"][0]
            )
    checks.append(
        CheckResult(
            name="lifecycle order",
            status="PASS" if order_ok else "FAIL",
            expected="SessionStart < Prompt < PreToolUse < PostToolUse < Stop < SessionEnd",
            observed="ordered" if order_ok else "out of order or absent",
        )
    )

    result = "PASS" if all(check.status == "PASS" for check in checks) else "FAIL"
    return ProbeReport(
        schema_version="1",
        probe_version=__version__,
        provider="claude",
        runtime_version=runtime_version,
        mode="headless",
        checks=tuple(checks),
        result=result,
        duration_ms=duration_ms,
        fixture_path=fixture_path,
    )


def _runtime_version(claude_command: Sequence[str]) -> str:
    try:
        completed = subprocess.run(
            [*claude_command, "--version"],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ClaudeProbeSetupError(f"could not run Claude Code: {exc}") from exc
    if completed.returncode != 0:
        raise ClaudeProbeSetupError("Claude Code version check failed")
    version = completed.stdout.strip() or completed.stderr.strip()
    return version.splitlines()[0] if version else "unknown"


def build_claude_command(
    claude_command: Sequence[str],
    settings_path: Path,
    prompt: str,
    model: str | None,
) -> list[str]:
    command = [
        *claude_command,
        "--restricted",
        "--settings",
        str(settings_path),
        "--tools",
        "Read",
        "--disallowedTools",
        "mcp__*",
        "--permission-mode",
        "dontAsk",
        "--permission-prompts",
        "none",
        "--no-session-persistence",
        "--no-chrome",
        "-p",
        prompt,
        "--output-format",
        "json",
    ]
    if model:
        command.extend(("--model", model))
    return command


def _headless_error(completed: subprocess.CompletedProcess[str]) -> str | None:
    data: dict[str, Any] | None = None
    try:
        parsed = json.loads(completed.stdout)
        if isinstance(parsed, dict):
            data = parsed
    except json.JSONDecodeError:
        pass

    result_text = str(data.get("result", "")) if data else ""
    lowered = (result_text + "\n" + completed.stderr).lower()
    if "not logged in" in lowered or "please run /login" in lowered:
        return "Claude Code is not authenticated; run 'claude auth login' and complete sign-in"
    if "usage limit" in lowered or "rate limit" in lowered:
        return "Claude Code cannot run because the provider usage limit is exhausted"
    if completed.returncode != 0:
        return f"Claude Code headless run exited with status {completed.returncode}"
    if data is None:
        return "Claude Code headless output was not valid JSON"
    if data.get("is_error") is True:
        return "Claude Code headless run ended with a provider error"
    return None


def probe_claude(
    *,
    claude_executable: str | None = None,
    model: str | None = None,
    timeout: int = 180,
    keep_fixture: bool = False,
) -> ProbeReport:
    executable = claude_executable or shutil.which("claude")
    if not executable:
        raise ClaudeProbeSetupError("Claude Code CLI was not found on PATH")
    claude_command = [executable]
    runtime_version = _runtime_version(claude_command)

    git = shutil.which("git")
    if not git:
        raise ClaudeProbeSetupError("Git was not found on PATH")

    workspace = Path(tempfile.mkdtemp(prefix="agent-hook-probe-claude-"))
    started = time.monotonic()
    try:
        records_dir, settings_path = write_claude_fixture(workspace)
        init = subprocess.run(
            [git, "init", "-q", str(workspace)],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        if init.returncode != 0:
            raise ClaudeProbeSetupError("could not initialize disposable Git repository")

        artifact = workspace / TARGET_FILE
        artifact.write_text(TARGET_VALUE, encoding="utf-8")
        prompt = (
            "This is a lifecycle-hook conformance probe. Use the Read tool exactly once and "
            "do not use any other tool. Read the existing file named "
            f"{TARGET_FILE} from the current working directory. After it succeeds, reply exactly "
            "HOOK_PROBE_DONE."
        )
        command = build_claude_command(claude_command, settings_path, prompt, model)
        try:
            completed = subprocess.run(
                command,
                cwd=workspace,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
                env=os.environ.copy(),
            )
        except subprocess.TimeoutExpired as exc:
            raise ClaudeProbeSetupError(
                f"Claude Code probe timed out after {timeout} seconds"
            ) from exc

        if error := _headless_error(completed):
            raise ClaudeProbeSetupError(error)

        artifact_ok = artifact.is_file() and artifact.read_text(encoding="utf-8") == TARGET_VALUE
        records = _load_records(records_dir)
        duration_ms = round((time.monotonic() - started) * 1000)
        return analyse_claude_records(
            records,
            runtime_version=runtime_version,
            duration_ms=duration_ms,
            artifact_ok=artifact_ok,
            fixture_path=str(workspace) if keep_fixture else None,
        )
    finally:
        if not keep_fixture:
            shutil.rmtree(workspace, ignore_errors=True)
