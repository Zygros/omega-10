# Strict Ruff Gate Restoration and Phoenix CI Evidence — 2026-11-04

## Result

OMEGA-10 PR #5, `ci: restore strict repository-wide Ruff gate`, was merged into `main` as commit `5259035a273ca616ba4b2f9477e6d8ff815fbb1b`.

The workflow no longer masks lint failures with `|| true`. The 15 Ruff findings exposed by the restored gate were corrected, with type-validation semantics made explicit and regression tests expanded.

## Changes

- Restored the blocking command `ruff check src tests`.
- Sorted package imports and exported-name lists in the core, demonstrator, HTC, memory, and red-team package initializers.
- Replaced the float self-comparison / infinity tuple with `math.isfinite` in canonical JSON normalization.
- Updated the SHA-256 file-path annotation to `str | Path`, consistent with the package's Python >=3.11 requirement.
- Used `datetime.UTC` for timezone-aware benchmark timestamps.
- Changed invalid `seed` and `corrupt_fraction` types to raise `TypeError`; out-of-range numeric values continue to raise `ValueError`.
- Removed the redundant `int(round(...))` cast.
- Expanded invalid-configuration regression coverage to distinguish type errors from range errors.

## Verification before merge

On tested PR head `879467e39d472b2dde4b185a9514121e7ad832f8`:

- [CI run 41905659058](https://github.com/Zygros/omega-10/actions/runs/41905659058) passed on Python 3.11 and 3.12.
- [Phoenix Audit 41905659162](https://github.com/Zygros/omega-10/actions/runs/41905659162) passed.
- Both Python matrix jobs reported `All checks passed!` from Ruff and **11 passed** from pytest.
- Each job ran the deterministic local Phoenix benchmark: 420 components, 210 corrupted, 210 recovered, 1.0 recovery rate, append-only history preserved, ledger valid, all component hashes verified.

## Verification after merge

The push-to-main workflows on merge commit `5259035a273ca616ba4b2f9477e6d8ff815fbb1b` also passed:

- [Post-merge CI 41905813986](https://github.com/Zygros/omega-10/actions/runs/41905813986): both Python 3.11 and 3.12 jobs succeeded, including strict Ruff, 11 pytest cases per version, and the Phoenix benchmark.
- [Post-merge Phoenix Audit 41905813695](https://github.com/Zygros/omega-10/actions/runs/41905813695): success.

## Independently rehashed post-merge artifacts

Both GitHub Actions artifacts were downloaded and their ZIP SHA-256 values independently recalculated.

| Runtime | Artifact ID | GitHub / independently recalculated ZIP SHA-256 |
|---|---:|---|
| Python 3.11 | `13360865085` | `fb7b54f3ee98923fce85bbc52db973be0a8183c3f8b4f33cb394edf21bf6b04f` |
| Python 3.12 | `13360320907` | `e992ff7ce70656b2565a6078ab170e3004409040cd73e1bfbfbf332ffb5a23b7` |

For each archive, independent inspection confirmed:

- 420 baseline component entries.
- 6 ledger events.
- Result receipt reports 210/210 recovery, `passed=true`, valid ledger, append-only prefix preserved, and all component hashes verified.
- The six-event ledger hash chain independently recalculated as valid.

## Failure history retained

The first strict-gate CI run, [41904139345](https://github.com/Zygros/omega-10/actions/runs/41904139345), correctly failed because the formerly masked Ruff findings became blocking. The log reported 15 findings: 11 fixable with the safe auto-fix set, one optional unsafe fix, and three requiring deliberate code changes. The issues were corrected rather than restoring the `|| true` bypass. The final PR-head and post-merge runs passed.

## Boundaries

This evidence establishes repository-level CI and a deterministic local recovery fixture. It does not establish distributed recovery, external-agent participation, production deployment, or independent reproduction on a separate machine. The benchmark's 100% recovery result is limited to the 210 corrupted components in these specific runs.
