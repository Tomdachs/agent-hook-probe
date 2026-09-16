# Safety model

The purpose of Agent Hook Probe is to verify an automation boundary without weakening a different one.

## Disposable ownership

Every provider fixture lives in a newly created temporary Git repository and contains only probe-owned hook configuration, recorder output, and canary content. It is removed after analysis unless `--keep-fixture` is supplied.

Codex hook definitions are passed as per-invocation session config rather than written into the user's Codex home or repository. Antigravity hook definitions are written only to the disposable repository's `.agents/hooks.json`; the probe never edits the user's `~/.gemini/antigravity-cli/settings.json` or `~/.gemini/config/hooks.json`.

## Provider permission boundaries

Codex requires non-managed hooks to be reviewed and trusted. Its official hook documentation provides `--dangerously-bypass-hook-trust` for one-off automation that already vets the hook source. The probe uses that flag only for the complete hook definition it generated immediately before launch. It never passes `--dangerously-bypass-approvals-and-sandbox`, and the canary command stays inside `workspace-write`.

The Antigravity adapter uses a read-only `view_file` canary. During the 1.2.4 release smoke, a `write_file` request was soft-denied in headless mode even after the disposable directory was explicitly added to the workspace, so the probe does not depend on write permission. It passes `--add-dir` for only the temporary fixture, enables `--sandbox`, and never passes `--dangerously-skip-permissions`.

## Authentication

Agent Hook Probe does not read, copy, migrate, print, or persist provider credentials. Providers must already be authenticated according to their own supported flow. Missing authentication is reported as setup error code `2`, not as a hook conformance failure.

## Sensitive data

Raw hook payloads can contain working paths, the probe prompt, tool arguments, session or conversation ids, and transcript paths. They remain inside the disposable fixture and are not copied to text or JSON reports. A retained fixture is therefore debugging material, not a support-safe report.

The probe does not inspect auth files, environment secret values, browser state, SSH material, or existing project content.
