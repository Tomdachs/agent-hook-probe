from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent_hook_probe.model import CheckResult, ProbeReport
from agent_hook_probe.snapshot import (
    SnapshotError,
    compare_snapshots,
    load_snapshot,
    save_snapshot,
    snapshot_from_report,
)


def report(
    *,
    runtime: str = "runtime 1.0",
    provider: str = "codex",
    mode: str = "exec",
    checks: tuple[CheckResult, ...] | None = None,
    fixture_path: str | None = "/private/fixture",
) -> ProbeReport:
    values = checks or (
        CheckResult("SessionStart", "PASS", "1", "1"),
        CheckResult("Stop", "PASS", "1", "1"),
    )
    return ProbeReport(
        schema_version="1",
        probe_version="0.4.0",
        provider=provider,
        runtime_version=runtime,
        mode=mode,
        checks=values,
        result="PASS" if all(item.status == "PASS" for item in values) else "FAIL",
        duration_ms=12,
        fixture_path=fixture_path,
    )


def test_snapshot_is_privacy_minimized() -> None:
    payload = snapshot_from_report(report())
    assert payload["snapshot_schema_version"] == "1"
    assert "captured_at" in payload
    assert "fixture_path" not in payload["report"]


def test_save_load_and_overwrite_guard(tmp_path: Path) -> None:
    path = tmp_path / "baseline.json"
    save_snapshot(report(), path)
    loaded = load_snapshot(path)
    assert loaded["report"]["provider"] == "codex"
    with pytest.raises(SnapshotError, match="already exists"):
        save_snapshot(report(), path)
    save_snapshot(report(runtime="runtime 2.0"), path, overwrite=True)
    assert load_snapshot(path)["report"]["runtime_version"] == "runtime 2.0"


def test_runtime_version_change_alone_is_not_regression() -> None:
    baseline = snapshot_from_report(report(runtime="runtime 1.0"))
    current = snapshot_from_report(report(runtime="runtime 2.0"))
    diff = compare_snapshots(baseline, current)
    assert diff.status == "UNCHANGED"
    assert diff.to_dict()["runtime_changed"] is True
    assert not diff.has_blocking_change


def test_pass_to_fail_is_regression() -> None:
    baseline = snapshot_from_report(report())
    current = snapshot_from_report(
        report(
            checks=(
                CheckResult("SessionStart", "FAIL", "1", "0"),
                CheckResult("Stop", "PASS", "1", "1"),
            )
        )
    )
    diff = compare_snapshots(baseline, current)
    assert diff.status == "REGRESSION"
    assert diff.has_blocking_change
    assert any(change.kind == "regressed" for change in diff.changes)


def test_fail_to_pass_is_improvement() -> None:
    baseline = snapshot_from_report(
        report(
            checks=(
                CheckResult("SessionStart", "FAIL", "1", "0"),
                CheckResult("Stop", "PASS", "1", "1"),
            )
        )
    )
    current = snapshot_from_report(report())
    diff = compare_snapshots(baseline, current)
    assert diff.status == "IMPROVED"
    assert not diff.has_blocking_change


def test_expected_contract_change_is_drift() -> None:
    baseline = snapshot_from_report(report())
    current = snapshot_from_report(
        report(
            checks=(
                CheckResult("SessionStart", "PASS", ">=1", "1"),
                CheckResult("Stop", "PASS", "1", "1"),
            )
        )
    )
    diff = compare_snapshots(baseline, current)
    assert diff.status == "DRIFT"
    assert any(change.kind == "expected_changed" for change in diff.changes)


def test_removed_check_is_regression_and_added_check_is_drift() -> None:
    baseline = snapshot_from_report(report())
    removed = snapshot_from_report(report(checks=(CheckResult("SessionStart", "PASS", "1", "1"),)))
    assert compare_snapshots(baseline, removed).status == "REGRESSION"

    added = snapshot_from_report(
        report(
            checks=(
                CheckResult("SessionStart", "PASS", "1", "1"),
                CheckResult("Stop", "PASS", "1", "1"),
                CheckResult("SessionEnd", "PASS", "1", "1"),
            )
        )
    )
    assert compare_snapshots(baseline, added).status == "DRIFT"


def test_provider_or_surface_mismatch_is_rejected() -> None:
    baseline = snapshot_from_report(report())
    with pytest.raises(SnapshotError, match="same provider"):
        compare_snapshots(baseline, snapshot_from_report(report(provider="antigravity")))
    with pytest.raises(SnapshotError, match="same provider"):
        compare_snapshots(baseline, snapshot_from_report(report(mode="tui")))


def test_invalid_snapshot_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"snapshot_schema_version": "999", "report": {}}), encoding="utf-8")
    with pytest.raises(SnapshotError, match="unsupported snapshot schema"):
        load_snapshot(path)
