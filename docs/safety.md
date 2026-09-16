# Safety model

The purpose of Agent Hook Probe is to verify an automation boundary without weakening a different one.

## Disposable ownership

Every fixture file written by the Codex adapter lives in a newly created temporary repository. Hook definitions are passed as per-invocation session config rather than written into the user's Codex home or repository. The only requested shell side effect is a canary file in that repository. The fixture is removed after analysis unless `--keep-fixture` is supplied.

## Hook trust versus sandbox bypass

Codex requires non-managed hooks to be reviewed and trusted. Its official hook documentation provides `--dangerously-bypass-hook-trust` for one-off automation that already vets the hook source. The probe qualifies narrowly because it generates the complete hook definition itself immediately before launching Codex.

This flag does not grant filesystem or network access to the model-generated command. The probe continues to select Codex `workspace-write` mode and never passes `--dangerously-bypass-approvals-and-sandbox`.

## Sensitive data

Raw hook payloads can contain working paths, the probe prompt, shell input, session ids, and transcript paths. They remain inside the disposable fixture and are not copied to text or JSON reports. A retained fixture is therefore debugging material, not a support-safe report.

The probe does not read auth files, environment secrets, browser state, SSH material, or existing project content.
