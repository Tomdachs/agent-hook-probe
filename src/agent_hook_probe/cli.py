from __future__ import annotations

import argparse
import json
import sys

from . import __version__
from .antigravity import AntigravityProbeSetupError, probe_antigravity
from .codex import ProbeSetupError, probe_codex, probe_codex_tui
from .model import ProbeReport


def render_text(report: ProbeReport) -> str:
    lines = [
        f"Agent Hook Probe {report.probe_version}",
        f"Runtime: {report.runtime_version}",
        f"Mode:    {report.mode}",
        "",
    ]
    for check in report.checks:
        detail = f" — {check.detail}" if check.detail else ""
        result = (
            f"{check.status:4}  {check.name:24} expected {check.expected}, "
            f"observed {check.observed}{detail}"
        )
        lines.append(result)
    lines.extend(("", f"Result: {report.result}"))
    if report.fixture_path:
        lines.append(f"Fixture kept at: {report.fixture_path}")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agent-hook-probe",
        description="Verify that coding-agent lifecycle hooks actually fire.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="provider")
    codex = subparsers.add_parser("codex", help="probe Codex CLI hooks with a disposable fixture")
    codex.add_argument("--json", action="store_true", help="emit a privacy-minimized JSON report")
    codex.add_argument("--model", help="override the model used for the one minimal probe turn")
    codex.add_argument(
        "--surface",
        choices=("exec", "tui"),
        default="exec",
        help="Codex execution surface to probe (default: exec)",
    )
    codex.add_argument("--timeout", type=int, default=180, help="Codex turn timeout in seconds")
    codex.add_argument(
        "--keep-fixture",
        action="store_true",
        help="keep raw disposable hook records",
    )
    codex.add_argument("--codex", dest="codex_executable", help="path to a Codex CLI executable")

    antigravity = subparsers.add_parser(
        "antigravity", help="probe Antigravity CLI hooks with a disposable fixture"
    )
    antigravity.add_argument(
        "--json", action="store_true", help="emit a privacy-minimized JSON report"
    )
    antigravity.add_argument("--model", help="override the model used for the minimal probe turn")
    antigravity.add_argument(
        "--timeout", type=int, default=180, help="Antigravity turn timeout in seconds"
    )
    antigravity.add_argument(
        "--keep-fixture",
        action="store_true",
        help="keep raw disposable hook records",
    )
    antigravity.add_argument(
        "--agy", dest="agy_executable", help="path to an Antigravity CLI executable"
    )
    return parser


def _error(message: str, json_output: bool) -> int:
    if json_output:
        print(json.dumps({"result": "ERROR", "error": message}, indent=2))
    else:
        print(f"Agent Hook Probe: ERROR: {message}", file=sys.stderr)
    return 2


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.provider not in {"codex", "antigravity"}:
        parser.print_help()
        return 2
    if args.timeout < 1:
        return _error("--timeout must be at least 1 second", args.json)
    try:
        if args.provider == "codex":
            probe = probe_codex_tui if args.surface == "tui" else probe_codex
            report = probe(
                codex_executable=args.codex_executable,
                model=args.model,
                timeout=args.timeout,
                keep_fixture=args.keep_fixture,
            )
        else:
            report = probe_antigravity(
                agy_executable=args.agy_executable,
                model=args.model,
                timeout=args.timeout,
                keep_fixture=args.keep_fixture,
            )
    except (ProbeSetupError, AntigravityProbeSetupError) as exc:
        return _error(str(exc), args.json)
    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print(render_text(report))
    return 0 if report.result == "PASS" else 1
