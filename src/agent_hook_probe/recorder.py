from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from pathlib import Path


def record(event: str, output_dir: Path, raw_input: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    try:
        payload: object = json.loads(raw_input)
        parse_error = None
    except json.JSONDecodeError as exc:
        payload = None
        parse_error = f"invalid JSON at line {exc.lineno} column {exc.colno}"

    record_data = {
        "event": event,
        "received_at_ns": time.time_ns(),
        "pid": os.getpid(),
        "payload": payload,
        "parse_error": parse_error,
    }
    path = output_dir / f"{record_data['received_at_ns']}-{uuid.uuid4().hex}.json"
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(record_data, ensure_ascii=False), encoding="utf-8")
    temp.replace(path)
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--event", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--protocol", choices=("generic", "antigravity"), default="generic")
    args = parser.parse_args(argv)
    record(args.event, args.output_dir, sys.stdin.read())
    if args.protocol == "antigravity" and args.event == "PreToolUse":
        response = {"decision": "allow"}
    elif args.protocol == "antigravity" and args.event == "Stop":
        response = {"decision": "stop"}
    else:
        response = {}
    sys.stdout.write(json.dumps(response, separators=(",", ":")) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
