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
The missing module has now been implemented on the PR branch and acceptance tests have been added. The first CI attempt exposed and helped fix an evidence-preservation edge case. A new CI run is required to verify the corrected implementation.

## Cascading remediation update

Implemented `src/omega/phoenix/benchmark.py` as a deterministic, local-only recovery fixture:
- creates synthetic component baselines and a SHA-256-verified JSONL history;
- deterministically corrupts the configured fraction;
- restores components only from journal records whose payload hash verifies;
- checks every component against its baseline and verifies the history bytes are unchanged;
- refuses to start in a non-empty run directory, preserving unrelated prior evidence.

Added `tests/test_phoenix_benchmark.py` for the 90% corruption acceptance path, zero-corruption no-op, invalid configuration, and non-overwrite behavior.

The first CI attempt exposed one additional defect: the initial non-overwrite guard checked only Phoenix's component directory and journal, not unrelated files already in the run directory. That test failed (7 passed, 1 failed in Phoenix Audit); the guard has now been strengthened to reject any non-empty run directory.

## Verification boundary
- Implementation and regression test are committed on the PR branch.
- Regression-driven correction committed: `adccaf94da6d147577754db6a6da47eb44d47612`.
- **Phoenix Audit run 14 passed:** https://github.com/Zygros/omega-10/actions/runs/39313132034
- **CI run 17 passed on Python 3.11 and 3.12:** https://github.com/Zygros/omega-10/actions/runs/39313132199. Both test jobs completed pytest successfully.
- The earlier failed run 16 exposed the non-overwrite edge case and remains part of the audit trail; it is not represented as a passing run.
- Ruff is still configured with `|| true`, so CI's green status does not establish that lint findings are resolved.


## Related evidence
- Scout duplicate-signal audit PR: https://github.com/Zygros/conzet-sovereign-intelligence/pull/27
- Omega-10 evidence cross-link PR: https://github.com/Zygros/omega-10/pull/1
