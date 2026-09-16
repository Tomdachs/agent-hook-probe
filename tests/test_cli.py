from __future__ import annotations

import json

from agent_hook_probe.cli import main, render_text
from agent_hook_probe.codex import analyse_codex_records


def test_no_provider_prints_help(capsys) -> None:
    assert main([]) == 2
    assert "Verify that coding-agent lifecycle hooks" in capsys.readouterr().out


def test_invalid_timeout_returns_setup_error(capsys) -> None:
    assert main(["codex", "--timeout", "0", "--json"]) == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["result"] == "ERROR"


def test_antigravity_invalid_timeout_returns_setup_error(capsys) -> None:
    assert main(["antigravity", "--timeout", "0", "--json"]) == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["result"] == "ERROR"


def test_text_renderer_is_compact() -> None:
    report = analyse_codex_records(
        [], runtime_version="codex-cli 9.9.9", duration_ms=1, artifact_ok=False
    )
    rendered = render_text(report)
    assert "Runtime: codex-cli 9.9.9" in rendered
    assert "Result: FAIL" in rendered
    assert "session_id" not in rendered


def _snapshot(status: str) -> dict[str, object]:
    return {
        "snapshot_schema_version": "1",
        "captured_at": "2026-09-16T00:00:00Z",
        "report": {
            "schema_version": "1",
            "probe_version": "0.4.0",
            "provider": "codex",
            "runtime_version": "codex-cli 1.0",
            "mode": "exec",
            "checks": [
                {"name": "Stop", "status": status, "expected": "1", "observed": "1"},
            ],
            "result": status,
            "duration_ms": 1,
        },
    }


def test_diff_command_returns_zero_when_unchanged(tmp_path, capsys) -> None:
    baseline = tmp_path / "baseline.json"
    current = tmp_path / "current.json"
    baseline.write_text(json.dumps(_snapshot("PASS")), encoding="utf-8")
    current.write_text(json.dumps(_snapshot("PASS")), encoding="utf-8")
    assert main(["diff", str(baseline), str(current)]) == 0
    assert "Status:   UNCHANGED" in capsys.readouterr().out


def test_diff_command_returns_one_for_regression_json(tmp_path, capsys) -> None:
    baseline = tmp_path / "baseline.json"
    current = tmp_path / "current.json"
    baseline.write_text(json.dumps(_snapshot("PASS")), encoding="utf-8")
    current.write_text(json.dumps(_snapshot("FAIL")), encoding="utf-8")
    assert main(["diff", str(baseline), str(current), "--json"]) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "REGRESSION"
