from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


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
    _boolean(env, "AHP_JSON")  # validate public input; the helper always captures JSON internally

    if operation == "diff":
        baseline = _value(env, "AHP_BASELINE")
        current = _value(env, "AHP_CURRENT")
        if not baseline or not current:
            raise ActionInputError("diff mode requires baseline and current snapshot paths")
        command.extend(("diff", baseline, current, "--json"))
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
    command.append("--json")
    return command


def _comparison(payload: dict[str, Any]) -> dict[str, Any] | None:
    value = payload.get("comparison")
    if isinstance(value, dict):
        return value
    if "status" in payload and "baseline_runtime_version" in payload:
        return payload
    return None


def _report(payload: dict[str, Any]) -> dict[str, Any] | None:
    value = payload.get("report")
    if isinstance(value, dict):
        return value
    if "result" in payload and "provider" in payload and "runtime_version" in payload:
        return payload
    return None


def metadata_from_payload(payload: dict[str, Any]) -> dict[str, str]:
    comparison = _comparison(payload)
    report = _report(payload)
    if comparison is not None:
        changes = comparison.get("changes")
        return {
            "status": str(comparison.get("status", "UNKNOWN")),
            "provider": str(
                comparison.get("provider", report.get("provider", "") if report else "")
            ),
            "mode": str(comparison.get("mode", report.get("mode", "") if report else "")),
            "runtime_version": str(
                comparison.get(
                    "current_runtime_version", report.get("runtime_version", "") if report else ""
                )
            ),
            "changes": str(len(changes) if isinstance(changes, list) else 0),
        }
    if report is not None:
        return {
            "status": str(report.get("result", "UNKNOWN")),
            "provider": str(report.get("provider", "")),
            "mode": str(report.get("mode", "")),
            "runtime_version": str(report.get("runtime_version", "")),
            "changes": "0",
        }
    return {
        "status": str(payload.get("result", "ERROR")),
        "provider": "",
        "mode": "",
        "runtime_version": "",
        "changes": "0",
    }


def _render_report(report: dict[str, Any]) -> str:
    lines = [
        f"Agent Hook Probe {report.get('probe_version', '')}",
        f"Runtime: {report.get('runtime_version', '')}",
        f"Mode:    {report.get('mode', '')}",
        "",
    ]
    checks = report.get("checks")
    if isinstance(checks, list):
        for check in checks:
            if not isinstance(check, dict):
                continue
            detail = f" — {check.get('detail')}" if check.get("detail") else ""
            expected = check.get("expected", "")
            observed = check.get("observed", "")
            lines.append(
                f"{str(check.get('status', '')):4}  {str(check.get('name', '')):24} "
                f"expected {expected}, observed {observed}{detail}"
            )
    lines.extend(("", f"Result: {report.get('result', '')}"))
    return "\n".join(lines)


def _render_comparison(comparison: dict[str, Any]) -> str:
    lines = [
        "Regression comparison",
        f"Provider: {comparison.get('provider', '')}",
        f"Mode:     {comparison.get('mode', '')}",
        (
            f"Runtime:  {comparison.get('baseline_runtime_version', '')} -> "
            f"{comparison.get('current_runtime_version', '')}"
        ),
        f"Status:   {comparison.get('status', '')}",
    ]
    changes = comparison.get("changes")
    if isinstance(changes, list) and changes:
        lines.append("")
        for change in changes:
            if isinstance(change, dict):
                lines.append(
                    f"{str(change.get('kind', '')):16} {change.get('name', '')}: "
                    f"{change.get('baseline', '')} -> {change.get('current', '')}"
                )
    else:
        lines.extend(("", "No contract or check-status changes detected."))
    return "\n".join(lines)


def render_text(payload: dict[str, Any]) -> str:
    report = _report(payload)
    comparison = _comparison(payload)
    sections: list[str] = []
    if report is not None:
        sections.append(_render_report(report))
    if comparison is not None:
        sections.append(_render_comparison(comparison))
    if sections:
        return "\n\n".join(sections)
    error = payload.get("error")
    return f"Agent Hook Probe action: ERROR: {error}" if error else json.dumps(payload, indent=2)


def _append_line(path: str, line: str) -> None:
    if not path:
        return
    with Path(path).open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(line + "\n")


def publish_github_metadata(payload: dict[str, Any], env: dict[str, str]) -> dict[str, str]:
    metadata = metadata_from_payload(payload)
    output_path = _value(env, "GITHUB_OUTPUT")
    for key, value in metadata.items():
        _append_line(output_path, f"{key}={value.replace(chr(10), ' ')}")

    summary_path = _value(env, "GITHUB_STEP_SUMMARY")
    if summary_path:
        _append_line(summary_path, "### Agent Hook Probe")
        _append_line(summary_path, "")
        _append_line(summary_path, "| Field | Value |")
        _append_line(summary_path, "| --- | --- |")
        for key in ("status", "provider", "mode", "runtime_version", "changes"):
            value = metadata[key].replace("|", "\\|")
            _append_line(summary_path, f"| {key} | {value} |")
        comparison = _comparison(payload)
        changes = comparison.get("changes") if comparison else None
        if isinstance(changes, list) and changes:
            _append_line(summary_path, "")
            _append_line(summary_path, "| Change | Check | Before | After |")
            _append_line(summary_path, "| --- | --- | --- | --- |")
            for change in changes:
                if isinstance(change, dict):
                    values = [
                        str(change.get("kind", "")),
                        str(change.get("name", "")),
                        str(change.get("baseline", "")),
                        str(change.get("current", "")),
                    ]
                    values = [value.replace("|", "\\|").replace("\n", " ") for value in values]
                    _append_line(summary_path, "| " + " | ".join(values) + " |")
    return metadata


def main() -> int:
    env = dict(os.environ)
    try:
        command = build_command(env)
    except ActionInputError as exc:
        print(f"Agent Hook Probe action: ERROR: {exc}", file=sys.stderr)
        return 2

    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    if completed.stderr:
        print(completed.stderr, file=sys.stderr, end="")
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        if completed.stdout:
            print(completed.stdout, end="")
        return completed.returncode
    if not isinstance(payload, dict):
        print(completed.stdout, end="")
        return completed.returncode

    publish_github_metadata(payload, env)
    if _boolean(env, "AHP_JSON"):
        print(json.dumps(payload, indent=2))
    else:
        output = render_text(payload)
        stream = sys.stderr if payload.get("result") == "ERROR" else sys.stdout
        print(output, file=stream)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
