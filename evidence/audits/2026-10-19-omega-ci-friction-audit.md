# OMEGA-10 CI friction audit — 2026-10-19

## Observed workflow state
The evidence cross-link PR triggered two real workflow runs:
- Phoenix Audit run 6: FAILURE — https://github.com/Zygros/omega-10/actions/runs/39312093564
- CI run 13: FAILURE — https://github.com/Zygros/omega-10/actions/runs/39312093679

## Root cause confirmed from job logs
Both workflows test a repository tree where `src/omega/phoenix/__init__.py` imports `PhoenixBenchmark, PhoenixResult` from `.benchmark`, but `src/omega/phoenix/benchmark.py` is missing. Pytest collection fails with:
`ModuleNotFoundError: No module named 'omega.phoenix.benchmark'`.

The existing test `tests/test_phoenix.py` expects a `PhoenixBenchmark` with constructor arguments `seed`, `n_components`, and `corrupt_fraction`, and a `run()` result exposing `recovery_rate`, `append_only_history_preserved`, and `passed`. The correct fix is to restore or implement that intended module and test it, not to skip the test or remove the import.

The CI log also shows 12 Ruff findings, 11 auto-fixable. The workflow currently uses `ruff check src tests || true`, which masks lint failure. This is a secondary cleanup item, not the current pytest blocker.

## Action taken
Created issue #2 with the confirmed root cause and safe remediation plan:
https://github.com/Zygros/omega-10/issues/2

## Current status
Root cause identified and recorded. No code was changed to conceal the failure. The missing benchmark module was not fabricated because the existing public implementation/semantics were not present in the inspected repository tree. Remediation requires implementing the module against the existing test contract, then running CI before claiming resolution.

## Related evidence
- Scout duplicate-signal audit PR: https://github.com/Zygros/conzet-sovereign-intelligence/pull/27
- Omega-10 evidence cross-link PR: https://github.com/Zygros/omega-10/pull/1
