from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

CheckStatus = Literal["PASS", "FAIL"]


@dataclass(frozen=True)
class CheckResult:
    name: str
    status: CheckStatus
    expected: str
    observed: str
    detail: str = ""

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class ProbeReport:
    schema_version: str
    probe_version: str
    provider: str
    runtime_version: str
    mode: str
    checks: tuple[CheckResult, ...]
    result: Literal["PASS", "FAIL"]
    duration_ms: int
    fixture_path: str | None = None

    def to_dict(self) -> dict[str, object]:
        data: dict[str, object] = {
            "schema_version": self.schema_version,
            "probe_version": self.probe_version,
            "provider": self.provider,
            "runtime_version": self.runtime_version,
            "mode": self.mode,
            "checks": [check.to_dict() for check in self.checks],
            "result": self.result,
            "duration_ms": self.duration_ms,
        }
        if self.fixture_path is not None:
            data["fixture_path"] = self.fixture_path
        return data
