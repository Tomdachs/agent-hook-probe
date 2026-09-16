from __future__ import annotations

import contextlib
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


class ProbeSetupError(RuntimeError):
    pass


def _command_strings(event: str, records_dir: Path) -> tuple[str, str]:
    args = [
        sys.executable,
        "-m",
        "agent_hook_probe.recorder",
        "--event",
        event,
        "--output-dir",
        str(records_dir),
    ]
    return shlex.join(args), subprocess.list2cmdline(args)


def _toml_string(value: str) -> str:
    """Encode a string as a TOML basic string using compatible JSON escaping."""
    return json.dumps(value, ensure_ascii=False)


def build_codex_hooks_override(records_dir: Path) -> str:
    event_tables: list[str] = []
    for event in CORE_EVENTS:
        command, command_windows = _command_strings(event, records_dir)
        handler = (
            '{type="command",'
            f"command={_toml_string(command)},"
            f"commandWindows={_toml_string(command_windows)},"
            f"timeout={3 if event == 'SessionEnd' else 10}"
            "}"
        )
        matcher = ""
        if event == "SessionStart":
            matcher = 'matcher="^startup$",'
        elif event in {"PreToolUse", "PostToolUse"}:
            matcher = 'matcher="^Bash$",'
        event_tables.append(f"{event}=[{{{matcher}hooks=[{handler}]}}]")
    return "hooks={" + ",".join(event_tables) + "}"


def build_codex_project_trust_override(workspace: Path) -> str:
    """Trust only the disposable workspace for this invocation, without persisting it."""
    return f'projects={{{_toml_string(str(workspace))}={{trust_level="trusted"}}}}'


def write_codex_fixture(workspace: Path) -> Path:
    records_dir = workspace / ".agent-hook-probe-records"
    records_dir.mkdir(parents=True, exist_ok=True)
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
        if payload.get("tool_name") != "Bash":
            continue
        serialized_input = json.dumps(payload.get("tool_input"), ensure_ascii=False)
        if TARGET_FILE in serialized_input:
            matched.append(record)
    return matched


def _count_check(records: list[dict[str, Any]], event: str, expected: int = 1) -> CheckResult:
    observed = sum(record.get("event") == event for record in records)
    return CheckResult(
        name=event,
        status="PASS" if observed == expected else "FAIL",
        expected=str(expected),
        observed=str(observed),
    )


def analyse_codex_records(
    records: list[dict[str, Any]],
    *,
    runtime_version: str,
    duration_ms: int,
    artifact_ok: bool,
    fixture_path: str | None = None,
    mode: str = "exec",
) -> ProbeReport:
    checks = [
        _count_check(records, "SessionStart"),
        _count_check(records, "UserPromptSubmit"),
    ]

    pre = _target_tool_records(records, "PreToolUse")
    post = _target_tool_records(records, "PostToolUse")
    checks.append(
        CheckResult(
            name="PreToolUse:Bash",
            status="PASS" if len(pre) == 1 else "FAIL",
            expected="1 target shell hook",
            observed=str(len(pre)),
        )
    )
    checks.append(
        CheckResult(
            name="PostToolUse:Bash",
            status="PASS" if len(post) == 1 else "FAIL",
            expected="1 target shell hook",
            observed=str(len(post)),
        )
    )

    pre_ids = {_payload(item).get("tool_use_id") for item in pre}
    post_ids = {_payload(item).get("tool_use_id") for item in post}
    paired = len(pre) == len(post) == 1 and None not in pre_ids and pre_ids == post_ids
    checks.append(
        CheckResult(
            name="tool lifecycle pairing",
            status="PASS" if paired else "FAIL",
            expected="matching non-empty tool_use_id",
            observed="paired" if paired else "unpaired",
        )
    )
    checks.extend((_count_check(records, "Stop"), _count_check(records, "SessionEnd")))

    schema_ok = True
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
            status="PASS" if schema_ok and bool(records) else "FAIL",
            expected="documented common fields",
            observed="valid" if schema_ok and records else "invalid or absent",
            detail=schema_detail,
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

    result = "PASS" if all(check.status == "PASS" for check in checks) else "FAIL"
    return ProbeReport(
        schema_version="1",
        probe_version=__version__,
        provider="codex",
        runtime_version=runtime_version,
        mode=mode,
        checks=tuple(checks),
        result=result,
        duration_ms=duration_ms,
        fixture_path=fixture_path,
    )


def _runtime_version(codex_command: Sequence[str]) -> str:
    try:
        completed = subprocess.run(
            [*codex_command, "--version"],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ProbeSetupError(f"could not run Codex CLI: {exc}") from exc
    if completed.returncode != 0:
        raise ProbeSetupError("Codex CLI version check failed")
    version = completed.stdout.strip() or completed.stderr.strip()
    return version.splitlines()[0] if version else "unknown"


def build_codex_exec_command(
    codex_command: Sequence[str],
    workspace: Path,
    records_dir: Path,
    prompt: str,
    model: str | None,
) -> list[str]:
    command = [
        *codex_command,
        "exec",
        "--ignore-user-config",
        "--dangerously-bypass-hook-trust",
        "--ephemeral",
        "-c",
        "features.hooks=true",
        "-c",
        build_codex_hooks_override(records_dir),
        "-c",
        build_codex_project_trust_override(workspace),
        "-C",
        str(workspace),
        "-s",
        "workspace-write",
        "--json",
    ]
    if model:
        command.extend(("--model", model))
    command.append(prompt)
    return command


def build_codex_tui_command(
    codex_command: Sequence[str],
    workspace: Path,
    records_dir: Path,
    prompt: str,
    model: str | None,
) -> list[str]:
    command = [
        *codex_command,
        "--dangerously-bypass-hook-trust",
        "-c",
        "features.hooks=true",
        "-c",
        build_codex_hooks_override(records_dir),
        "-c",
        build_codex_project_trust_override(workspace),
        "-c",
        'history.persistence="none"',
        "-C",
        str(workspace),
        "-s",
        "workspace-write",
        "-a",
        "never",
        "--no-alt-screen",
    ]
    if model:
        command.extend(("--model", model))
    command.append(prompt)
    return command


def _probe_prompt() -> str:
    if os.name == "nt":
        shell_command = f"Set-Content -NoNewline -Path {TARGET_FILE} -Value {TARGET_VALUE}"
    else:
        shell_command = f"printf %s {TARGET_VALUE} > {TARGET_FILE}"
    return (
        "This is a lifecycle-hook conformance probe. Use the shell tool exactly once and "
        "do not use any other tool. Run this exact shell command:\n"
        f"{shell_command}\n"
        "After it succeeds, reply exactly HOOK_PROBE_DONE."
    )


def _init_workspace(workspace: Path, git: str) -> Path:
    records_dir = write_codex_fixture(workspace)
    init = subprocess.run(
        [git, "init", "-q", str(workspace)],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    if init.returncode != 0:
        raise ProbeSetupError("could not initialize disposable Git repository")
    return records_dir


def probe_codex(
    *,
    codex_executable: str | None = None,
    model: str | None = None,
    timeout: int = 180,
    keep_fixture: bool = False,
) -> ProbeReport:
    executable = codex_executable or shutil.which("codex")
    if not executable:
        raise ProbeSetupError("Codex CLI was not found on PATH")
    codex_command = [executable]
    runtime_version = _runtime_version(codex_command)

    git = shutil.which("git")
    if not git:
        raise ProbeSetupError("Git was not found on PATH")

    workspace = Path(tempfile.mkdtemp(prefix="agent-hook-probe-"))
    started = time.monotonic()
    try:
        records_dir = _init_workspace(workspace, git)
        command = build_codex_exec_command(
            codex_command, workspace, records_dir, _probe_prompt(), model
        )
        try:
            completed = subprocess.run(
                command,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise ProbeSetupError(f"Codex probe timed out after {timeout} seconds") from exc
        if completed.returncode != 0:
            raise ProbeSetupError(f"Codex exec exited with status {completed.returncode}")

        artifact = workspace / TARGET_FILE
        artifact_ok = artifact.is_file() and artifact.read_text(encoding="utf-8") == TARGET_VALUE
        records = _load_records(records_dir)
        duration_ms = round((time.monotonic() - started) * 1000)
        return analyse_codex_records(
            records,
            runtime_version=runtime_version,
            duration_ms=duration_ms,
            artifact_ok=artifact_ok,
            fixture_path=str(workspace) if keep_fixture else None,
        )
    finally:
        if not keep_fixture:
            shutil.rmtree(workspace, ignore_errors=True)


def _drain_pty(master_fd: int) -> None:
    try:
        while True:
            chunk = os.read(master_fd, 65536)
            if not chunk:
                return
    except (BlockingIOError, OSError):
        return


def probe_codex_tui(
    *,
    codex_executable: str | None = None,
    model: str | None = None,
    timeout: int = 180,
    keep_fixture: bool = False,
) -> ProbeReport:
    if os.name == "nt":
        raise ProbeSetupError("Codex TUI probe currently requires Linux, WSL, or macOS")

    # Imported lazily so the package remains importable on Windows.
    import fcntl
    import pty
    import struct
    import termios

    executable = codex_executable or shutil.which("codex")
    if not executable:
        raise ProbeSetupError("Codex CLI was not found on PATH")
    codex_command = [executable]
    runtime_version = _runtime_version(codex_command)

    git = shutil.which("git")
    if not git:
        raise ProbeSetupError("Git was not found on PATH")

    workspace = Path(tempfile.mkdtemp(prefix="agent-hook-probe-tui-"))
    started = time.monotonic()
    master_fd = -1
    process: subprocess.Popen[bytes] | None = None
    try:
        records_dir = _init_workspace(workspace, git)
        command = build_codex_tui_command(
            codex_command, workspace, records_dir, _probe_prompt(), model
        )
        master_fd, slave_fd = pty.openpty()
        fcntl.ioctl(slave_fd, termios.TIOCSWINSZ, struct.pack("HHHH", 40, 120, 0, 0))
        env = os.environ.copy()
        env["TERM"] = "xterm-256color"
        env.setdefault("COLORTERM", "truecolor")
        process = subprocess.Popen(
            command,
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            close_fds=True,
            env=env,
        )
        os.close(slave_fd)
        os.set_blocking(master_fd, False)

        completed_at: float | None = None
        deadline = started + timeout
        while time.monotonic() < deadline and process.poll() is None:
            _drain_pty(master_fd)
            records = _load_records(records_dir)
            artifact = workspace / TARGET_FILE
            if artifact.is_file():
                if completed_at is None:
                    completed_at = time.monotonic()
                # Once the canary proves the turn ran, allow hooks a short grace period.
                # Missing PostToolUse/Stop regressions should not wait for the full timeout.
                if any(record.get("event") == "Stop" for record in records) or (
                    time.monotonic() - completed_at >= 5
                ):
                    os.write(master_fd, b"\x03")
                    break
            time.sleep(0.1)
        else:
            if process.poll() is None:
                os.write(master_fd, b"\x03")

        exit_deadline = time.monotonic() + 12
        while process.poll() is None and time.monotonic() < exit_deadline:
            _drain_pty(master_fd)
            time.sleep(0.1)
        if process.poll() is None:
            os.write(master_fd, b"\x03")
            time.sleep(1)
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()

        if not (workspace / TARGET_FILE).is_file():
            raise ProbeSetupError(f"Codex TUI probe did not complete within {timeout} seconds")

        artifact = workspace / TARGET_FILE
        artifact_ok = artifact.read_text(encoding="utf-8") == TARGET_VALUE
        records = _load_records(records_dir)
        duration_ms = round((time.monotonic() - started) * 1000)
        return analyse_codex_records(
            records,
            runtime_version=runtime_version,
            duration_ms=duration_ms,
            artifact_ok=artifact_ok,
            fixture_path=str(workspace) if keep_fixture else None,
            mode="tui",
        )
    finally:
        if master_fd >= 0:
            with contextlib.suppress(OSError):
                os.close(master_fd)
        if process is not None and process.poll() is None:
            process.kill()
            process.wait()
        if not keep_fixture:
            shutil.rmtree(workspace, ignore_errors=True)
