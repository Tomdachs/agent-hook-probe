from __future__ import annotations

import json
from pathlib import Path

from agent_hook_probe.recorder import record


def test_recorder_writes_structured_event(tmp_path: Path) -> None:
    path = record("SessionStart", tmp_path, '{"hook_event_name":"SessionStart"}')
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["event"] == "SessionStart"
    assert data["payload"]["hook_event_name"] == "SessionStart"
    assert data["parse_error"] is None


def test_recorder_does_not_persist_invalid_raw_input(tmp_path: Path) -> None:
    path = record("Stop", tmp_path, "secret-looking invalid json")
    text = path.read_text(encoding="utf-8")
    data = json.loads(text)
    assert data["payload"] is None
    assert data["parse_error"].startswith("invalid JSON")
    assert "secret-looking" not in text
