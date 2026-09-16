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


def test_text_renderer_is_compact() -> None:
    report = analyse_codex_records(
        [], runtime_version="codex-cli 9.9.9", duration_ms=1, artifact_ok=False
    )
    rendered = render_text(report)
    assert "Runtime: codex-cli 9.9.9" in rendered
    assert "Result: FAIL" in rendered
    assert "session_id" not in rendered
