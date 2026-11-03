# Verification Status

## Current evidence boundary

This repository contains implementation and local test infrastructure. A passing local run is not the same as independent reproduction, production certification, or security certification.

## Required evidence for claims

For every benchmark or capability claim, record:

1. exact commit SHA;
2. environment and dependency versions;
3. command used;
4. fixtures/datasets and parameters;
5. raw or machine-readable output artifact;
6. pass/fail result;
7. independent reproduction or review when claimed as verified.

## Release labels

- **Implemented** — code exists.
- **Tested** — current test execution is recorded.
- **Benchmarked** — reproducible benchmark artifacts exist.
- **Verified** — independent reproduction/review exists.
- **Prototype** — partial or experimental implementation.
- **Designed** — specification without sufficient implementation evidence.
- **Historical** — preserved material, not a current capability claim.

Do not upgrade a claim's status without adding the corresponding evidence artifact.

## 2026-11-03 source inventory correction

The tracked source tree currently implements canonical JSON serialization, SHA-256 helpers, and the local Phoenix recovery benchmark. The shared `core/ledger.py`, `core/manifest.py`, `core/signing.py`, `memory/codex.py`, `htc/chamber.py`, `redteam/fixtures.py`, and `demonstrator/demo.py` modules are not present in the current tree even though earlier package initializers or Makefile targets referenced them. The `omega.core` initializer now exports only the implemented canonical/hash primitives so imports do not fail on absent modules.

The Phoenix benchmark's event ledger is a benchmark-local hash chain. It is not a replacement claim for the missing shared `AppendOnlyLedger`, signing, or run-manifest APIs.

**Current local benchmark status:** implemented and covered by deterministic tests; CI will run `make phoenix` and upload the machine-readable run directory. This is local recovery-fixture evidence, not independent reproduction, distributed recovery, production certification, or live AI execution.