# GitHub Action

Agent Hook Probe ships a composite GitHub Action so repositories can gate on saved hook-contract snapshots or run a live provider probe on an already prepared runner.

## Offline regression gate

Offline `diff` is the safest default for ordinary pull-request CI because it does not launch a provider, consume model usage, or require credentials.

```yaml
- uses: Tomdachs/agent-hook-probe@v0.5.1
  with:
    operation: diff
    baseline: .github/agent-hook-probe/codex-exec-baseline.json
    current: artifacts/codex-exec-current.json
```

The step succeeds for `UNCHANGED` or `IMPROVED`, fails for `REGRESSION` or `DRIFT`, and returns a setup failure for invalid or incompatible snapshots.

## Outputs and Job Summary

Every successful parse publishes five Action outputs: `status`, `provider`, `mode`, `runtime_version`, and `changes`. The same privacy-minimized metadata is appended to the GitHub Job Summary. Regression comparisons also include their normalized change rows in the summary.

```yaml
- id: hook-contract
  uses: Tomdachs/agent-hook-probe@v0.5.1
  with:
    operation: diff
    baseline: .github/agent-hook-probe/codex-exec-baseline.json
    current: artifacts/codex-exec-current.json

- run: echo "Hook status: ${{ steps.hook-contract.outputs.status }}"
```

`changes` is the number of classified snapshot changes. For live probe mode it is `0` unless a baseline comparison is requested. The outputs contain only normalized report metadata; raw hook payloads are never written to `$GITHUB_OUTPUT` or the Job Summary.

## Live probe

Live mode deliberately does not install, upgrade, or authenticate a provider CLI. Pin and prepare the provider in earlier workflow steps or use a pre-authenticated self-hosted runner, then invoke the action:

```yaml
- uses: Tomdachs/agent-hook-probe@v0.5.1
  with:
    operation: probe
    provider: codex
    surface: exec
    baseline: .github/agent-hook-probe/codex-exec-baseline.json
    save_snapshot: artifacts/codex-exec-current.json
```

For Antigravity set `provider: antigravity`; `surface` is Codex-only. `model` and `timeout` are optional. Set `json: true` when machine-readable logs are useful.

## Authentication boundary

The action never accepts a credential input and never copies provider auth files. Provider authentication remains the caller's responsibility and should use a provider-supported flow appropriate for that runner. This keeps the action from becoming a secret-transport mechanism.

Interactive browser login is not performed by the action. If a hosted runner cannot be authenticated non-interactively under the provider's supported model, use offline `diff` there and run live probes on an appropriate pre-authenticated runner instead.

## Snapshot artifacts

`save_snapshot` writes only the privacy-minimized snapshot into the caller workspace. The action does not upload it automatically. If retention is wanted, add the repository's normal artifact-upload step explicitly so retention policy remains under the caller's control.

The action intentionally does not expose `--keep-fixture`; raw hook records can contain provider session identifiers, prompts, commands, and transcript paths and are not appropriate as a default CI artifact.

## Supply-chain notes

The composite action pins its own `setup-uv` dependency to an immutable commit. Consumers can reference the convenient release tag shown above or pin Agent Hook Probe itself to a commit SHA when their policy requires immutable third-party action references.
