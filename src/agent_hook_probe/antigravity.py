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
HOOK_NAME = "agent-hook-probe"
EVENTS = ("PreInvocation", "PostInvocation", "PreToolUse", "PostToolUse", "Stop")


class AntigravityProbeSetupError(RuntimeError):
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
        "--protocol",
        "antigravity",
    ]
    return shlex.join(args)


def build_antigravity_hooks(records_dir: Path) -> dict[str, Any]:
    def handler(event: str) -> dict[str, Any]:
        return {"type": "command", "command": _handler_command(event, records_dir), "timeout": 10}

    return {
        HOOK_NAME: {
            "PreInvocation": [handler("PreInvocation")],
            "PostInvocation": [handler("PostInvocation")],
            "PreToolUse": [{"matcher": "^view_file$", "hooks": [handler("PreToolUse")]}],
            "PostToolUse": [{"matcher": "^view_file$", "hooks": [handler("PostToolUse")]}],
            "Stop": [handler("Stop")],
        }
    }


def write_antigravity_fixture(workspace: Path) -> Path:
    records_dir = workspace / ".agent-hook-probe-records"
    records_dir.mkdir(parents=True, exist_ok=True)
    agents_dir = workspace / ".agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    hooks = build_antigravity_hooks(records_dir)
    (agents_dir / "hooks.json").write_text(
        json.dumps(hooks, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return records_dir


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
        tool_call = payload.get("toolCall")
        if not isinstance(tool_call, dict) or tool_call.get("name") != "view_file":
            continue
        serialized_args = json.dumps(tool_call.get("args"), ensure_ascii=False)
        if TARGET_FILE in serialized_args:
            matched.append(record)
    return matched


def _count(records: list[dict[str, Any]], event: str) -> int:
    return sum(record.get("event") == event for record in records)


def _common_schema_error(record: dict[str, Any]) -> str | None:
    if record.get("parse_error") is not None:
        return "at least one hook payload was not valid JSON"
    payload = _payload(record)
    if not isinstance(payload.get("conversationId"), str) or not payload.get("conversationId"):
        return "a payload was missing conversationId"
    workspace_paths = payload.get("workspacePaths")
    if not isinstance(workspace_paths, list) or not all(
        isinstance(value, str) and value for value in workspace_paths
    ):
        return "a payload had invalid workspacePaths"
    for field in ("transcriptPath", "artifactDirectoryPath", "modelName"):
        if not isinstance(payload.get(field), str) or not payload.get(field):
            return f"a payload was missing {field}"
    return None


def analyse_antigravity_records(
    records: list[dict[str, Any]],
    *,
    runtime_version: str,
    duration_ms: int,
    artifact_ok: bool,
    fixture_path: str | None = None,
) -> ProbeReport:
    checks: list[CheckResult] = []

    pre_invocations = _count(records, "PreInvocation")
    post_invocations = _count(records, "PostInvocation")
    invocation_ok = pre_invocations >= 1 and pre_invocations == post_invocations
    checks.append(
        CheckResult(
            name="model invocation pairing",
            status="PASS" if invocation_ok else "FAIL",
            expected=">=1 paired Pre/PostInvocation",
            observed=f"pre={pre_invocations}, post={post_invocations}",
        )
    )

    pre = _target_tool_records(records, "PreToolUse")
    post = _target_tool_records(records, "PostToolUse")
    checks.append(
        CheckResult(
            name="PreToolUse:view_file",
            status="PASS" if len(pre) == 1 else "FAIL",
            expected="1 target read hook",
            observed=str(len(pre)),
        )
    )
    checks.append(
        CheckResult(
            name="PostToolUse:view_file",
            status="PASS" if len(post) == 1 else "FAIL",
            expected="1 target read hook",
            observed=str(len(post)),
        )
    )

    paired = False
    if len(pre) == len(post) == 1:
        pre_payload = _payload(pre[0])
        post_payload = _payload(post[0])
        paired = pre_payload.get("stepIdx") == post_payload.get("stepIdx") and pre_payload.get(
            "toolCall"
        ) == post_payload.get("toolCall")
    checks.append(
        CheckResult(
            name="tool lifecycle pairing",
            status="PASS" if paired else "FAIL",
            expected="matching stepIdx and toolCall",
            observed="paired" if paired else "unpaired",
        )
    )

    stop_count = _count(records, "Stop")
    checks.append(
        CheckResult(
            name="Stop",
            status="PASS" if stop_count == 1 else "FAIL",
            expected="1",
            observed=str(stop_count),
        )
    )

    schema_error = next(
        (error for record in records if (error := _common_schema_error(record))), None
    )
    schema_ok = bool(records) and schema_error is None
    checks.append(
        CheckResult(
            name="payload schema",
            status="PASS" if schema_ok else "FAIL",
            expected="documented common fields",
            observed="valid" if schema_ok else "invalid or absent",
            detail=schema_error or "",
        )
    )
    checks.append(
        CheckResult(
            name="probe artifact",
            status="PASS" if artifact_ok else "FAIL",
            expected=TARGET_VALUE,
            observed=TARGET_VALUE if artifact_ok else "missing or different",
        )
    )

    if pre and post:
        pre_index = records.index(pre[0])
        post_index = records.index(post[0])
        stop_indexes = [i for i, record in enumerate(records) if record.get("event") == "Stop"]
        order_ok = pre_index < post_index and bool(stop_indexes) and post_index < stop_indexes[-1]
    else:
        order_ok = False
    checks.append(
        CheckResult(
            name="lifecycle order",
            status="PASS" if order_ok else "FAIL",
            expected="PreToolUse < PostToolUse < Stop",
            observed="ordered" if order_ok else "out of order or absent",
        )
    )

    result = "PASS" if all(check.status == "PASS" for check in checks) else "FAIL"
    return ProbeReport(
        schema_version="1",
        probe_version=__version__,
        provider="antigravity",
        runtime_version=runtime_version,
        mode="headless",
        checks=tuple(checks),
        result=result,
        duration_ms=duration_ms,
        fixture_path=fixture_path,
    )


def _runtime_version(agy_command: Sequence[str]) -> str:
    try:
        completed = subprocess.run(
            [*agy_command, "--version"],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise AntigravityProbeSetupError(f"could not run Antigravity CLI: {exc}") from exc
    if completed.returncode != 0:
        raise AntigravityProbeSetupError("Antigravity CLI version check failed")
    version = completed.stdout.strip() or completed.stderr.strip()
    return version.splitlines()[0] if version else "unknown"


def build_antigravity_command(
    agy_command: Sequence[str],
    workspace: Path,
    prompt: str,
    timeout: int,
    model: str | None,
) -> list[str]:
    command = [
        *agy_command,
        "-p",
        prompt,
        "--add-dir",
        str(workspace),
        "--output-format",
        "json",
        "--print-timeout",
        f"{timeout}s",
        "--sandbox",
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
    stderr = completed.stderr.lower()
    if "authentication required" in stderr or (
        data and "authentication" in str(data.get("error", "")).lower()
    ):
        return "Antigravity CLI is not authenticated; run 'agy' once and complete sign-in"
    if completed.returncode != 0:
        return f"Antigravity headless run exited with status {completed.returncode}"
    if data is None:
        return "Antigravity headless output was not valid JSON"
    if data.get("status") != "SUCCESS":
        status = data.get("status", "unknown")
        return f"Antigravity headless run ended with status {status}"
    return None


def probe_antigravity(
    *,
    agy_executable: str | None = None,
    model: str | None = None,
    timeout: int = 180,
    keep_fixture: bool = False,
) -> ProbeReport:
    executable = agy_executable or shutil.which("agy")
    if not executable:
        raise AntigravityProbeSetupError("Antigravity CLI (agy) was not found on PATH")
    agy_command = [executable]
    runtime_version = _runtime_version(agy_command)

    git = shutil.which("git")
    if not git:
        raise AntigravityProbeSetupError("Git was not found on PATH")

    workspace = Path(tempfile.mkdtemp(prefix="agent-hook-probe-agy-"))
    started = time.monotonic()
    try:
        records_dir = write_antigravity_fixture(workspace)
        init = subprocess.run(
            [git, "init", "-q", str(workspace)],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        if init.returncode != 0:
            raise AntigravityProbeSetupError("could not initialize disposable Git repository")

        artifact = workspace / TARGET_FILE
        artifact.write_text(TARGET_VALUE, encoding="utf-8")
        prompt = (
            "This is a lifecycle-hook conformance probe. Use the view_file tool exactly once "
            "and do not use any other tool. Read the existing file named "
            f"{TARGET_FILE} from the active workspace. After it succeeds, reply exactly "
            "HOOK_PROBE_DONE."
        )
        command = build_antigravity_command(agy_command, workspace, prompt, timeout, model)
        try:
            completed = subprocess.run(
                command,
                cwd=workspace,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=timeout + 30,
                check=False,
                env=os.environ.copy(),
            )
        except subprocess.TimeoutExpired as exc:
            raise AntigravityProbeSetupError(
                f"Antigravity probe timed out after {timeout} seconds"
            ) from exc

        if error := _headless_error(completed):
            raise AntigravityProbeSetupError(error)

        artifact_ok = artifact.is_file() and artifact.read_text(encoding="utf-8") == TARGET_VALUE
        records = _load_records(records_dir)
        duration_ms = round((time.monotonic() - started) * 1000)
        return analyse_antigravity_records(
            records,
            runtime_version=runtime_version,
            duration_ms=duration_ms,
            artifact_ok=artifact_ok,
            fixture_path=str(workspace) if keep_fixture else None,
        )
    finally:
        if not keep_fixture:
            shutil.rmtree(workspace, ignore_errors=True)
