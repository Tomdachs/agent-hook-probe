# Regression snapshots

Research and implementation snapshot: 2026-09-16.

Regression snapshots preserve the privacy-minimized hook-conformance result from one provider execution surface so a later runtime can be compared without treating a version-string change as a failure by itself.

## Snapshot schema

A snapshot contains `snapshot_schema_version`, `captured_at`, and a normalized `report`. The report keeps provider, runtime version, execution mode, check names, expected/observed summaries, overall result, and duration. It deliberately excludes retained fixture paths and all raw hook records.

## Comparison rules

Snapshots must have the same provider and execution mode. Runtime version changes are informational. Check changes are classified as follows:

- `PASS -> FAIL`: regression;
- removed check: regression;
- added check: contract drift;
- changed `expected` text: contract drift;
- `FAIL -> PASS`: improvement;
- no contract/status changes: unchanged.

A comparison exits `1` for regression or drift so it can gate CI. Unchanged and improvement exit `0`. Invalid schema or provider/mode mismatch exits `2`.

## Typical workflow

```bash
agent-hook-probe codex --surface tui --save-snapshot codex-tui.json
agent-hook-probe codex --surface tui --baseline codex-tui.json --save-snapshot codex-tui-new.json
agent-hook-probe diff codex-tui.json codex-tui-new.json
```

Use `--overwrite-snapshot` only when intentionally replacing an existing snapshot.
