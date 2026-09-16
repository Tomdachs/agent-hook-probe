from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from .model import ProbeReport

SNAPSHOT_SCHEMA_VERSION = "1"
DiffStatus = Literal["UNCHANGED", "IMPROVED", "DRIFT", "REGRESSION"]


class SnapshotError(RuntimeError):
    pass


@dataclass(frozen=True)
class CheckChange:
    name: str
    kind: str
    baseline: str
    current: str

    def to_dict(self) -> dict[str, str]:
        return {
            "name": self.name,
            "kind": self.kind,
            "baseline": self.baseline,
            "current": self.current,
        }


@dataclass(frozen=True)
class SnapshotDiff:
    provider: str
    mode: str
    baseline_runtime_version: str
    current_runtime_version: str
    status: DiffStatus
    changes: tuple[CheckChange, ...]

    @property
    def has_blocking_change(self) -> bool:
        return self.status in {"DRIFT", "REGRESSION"}

    def to_dict(self) -> dict[str, object]:
        return {
            "provider": self.provider,
            "mode": self.mode,
            "baseline_runtime_version": self.baseline_runtime_version,
            "current_runtime_version": self.current_runtime_version,
            "runtime_changed": self.baseline_runtime_version != self.current_runtime_version,
            "status": self.status,
            "changes": [change.to_dict() for change in self.changes],
        }


def _public_report(report: ProbeReport) -> dict[str, object]:
    data = report.to_dict()
    data.pop("fixture_path", None)
    return data


def snapshot_from_report(report: ProbeReport) -> dict[str, object]:
    return {
        "snapshot_schema_version": SNAPSHOT_SCHEMA_VERSION,
        "captured_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "report": _public_report(report),
    }


def save_snapshot(report: ProbeReport, path: Path, *, overwrite: bool = False) -> None:
    if path.exists() and not overwrite:
        raise SnapshotError(
            f"snapshot already exists: {path}; pass --overwrite-snapshot to replace it"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    payload = snapshot_from_report(report)
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def load_snapshot(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise SnapshotError(f"could not read snapshot {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise SnapshotError(f"snapshot is not valid JSON: {path}") from exc
    if (
        not isinstance(payload, dict)
        or payload.get("snapshot_schema_version") != SNAPSHOT_SCHEMA_VERSION
    ):
        raise SnapshotError(f"unsupported snapshot schema: {path}")
    report = payload.get("report")
    if not isinstance(report, dict):
        raise SnapshotError(f"snapshot is missing report data: {path}")
    return payload


def _report(payload: dict[str, Any]) -> dict[str, Any]:
    report = payload.get("report")
    if not isinstance(report, dict):
        raise SnapshotError("snapshot is missing report data")
    return report


def _checks(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    raw = report.get("checks")
    if not isinstance(raw, list):
        raise SnapshotError("snapshot report is missing checks")
    result: dict[str, dict[str, Any]] = {}
    for item in raw:
        if not isinstance(item, dict) or not isinstance(item.get("name"), str):
            raise SnapshotError("snapshot contains an invalid check")
        name = item["name"]
        if name in result:
            raise SnapshotError(f"snapshot contains duplicate check: {name}")
        result[name] = item
    return result


def compare_snapshots(baseline: dict[str, Any], current: dict[str, Any]) -> SnapshotDiff:
    left = _report(baseline)
    right = _report(current)
    provider = left.get("provider")
    mode = left.get("mode")
    if provider != right.get("provider") or mode != right.get("mode"):
        raise SnapshotError("snapshots must use the same provider and execution mode")
    if not isinstance(provider, str) or not isinstance(mode, str):
        raise SnapshotError("snapshot report has invalid provider or mode")

    left_checks = _checks(left)
    right_checks = _checks(right)
    changes: list[CheckChange] = []
    regression = False
    drift = False
    improved = False

    for name in sorted(left_checks.keys() | right_checks.keys()):
        before = left_checks.get(name)
        after = right_checks.get(name)
        if before is None:
            changes.append(CheckChange(name, "added_check", "missing", str(after.get("status"))))
            drift = True
            continue
        if after is None:
            changes.append(CheckChange(name, "removed_check", str(before.get("status")), "missing"))
            regression = True
            continue
        if before.get("expected") != after.get("expected"):
            changes.append(
                CheckChange(
                    name,
                    "expected_changed",
                    str(before.get("expected")),
                    str(after.get("expected")),
                )
            )
            drift = True
        before_status = before.get("status")
        after_status = after.get("status")
        if before_status == "PASS" and after_status == "FAIL":
            changes.append(CheckChange(name, "regressed", "PASS", "FAIL"))
            regression = True
        elif before_status == "FAIL" and after_status == "PASS":
            changes.append(CheckChange(name, "improved", "FAIL", "PASS"))
            improved = True

    if regression:
        status: DiffStatus = "REGRESSION"
    elif drift:
        status = "DRIFT"
    elif improved:
        status = "IMPROVED"
    else:
        status = "UNCHANGED"
    return SnapshotDiff(
        provider=provider,
        mode=mode,
        baseline_runtime_version=str(left.get("runtime_version", "unknown")),
        current_runtime_version=str(right.get("runtime_version", "unknown")),
        status=status,
        changes=tuple(changes),
    )
