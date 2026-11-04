"""Deterministic local Phoenix recovery benchmark with an append-only evidence ledger.

This benchmark exercises local snapshot, corruption, recovery, and hash verification.
It does not exercise external agents, network services, distributed storage, or production deployment.
"""

from __future__ import annotations

import json
import random
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from omega.core.canonical import canonical_dumps
from omega.core.hashing import sha256_hex

SCHEMA = "omega-phoenix-recovery/1.0"
GENESIS = "0" * 64


@dataclass(frozen=True)
class PhoenixResult:
    schema: str
    run_id: str
    output_dir: str
    seed: int
    n_components: int
    corrupt_fraction: float
    corrupted_count: int
    recovered_count: int
    recovery_rate: float
    append_only_history_preserved: bool
    ledger_valid: bool
    all_components_verified: bool
    baseline_manifest_sha256: str
    ledger_sha256: str
    passed: bool
    errors: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def verify_ledger(records: list[dict[str, Any]]) -> bool:
    """Verify sequence, previous-hash links, and event-content hashes."""
    previous = GENESIS
    for sequence, record in enumerate(records, start=1):
        if record.get("sequence") != sequence:
            return False
        if record.get("previous_hash") != previous:
            return False
        body = {key: value for key, value in record.items() if key != "hash"}
        expected = sha256_hex(canonical_dumps(body))
        if record.get("hash") != expected:
            return False
        previous = record["hash"]
    return True


class PhoenixBenchmark:
    """Run a bounded, deterministic local recovery experiment."""

    def __init__(
        self,
        workspace: str | Path,
        *,
        seed: int = 42,
        n_components: int = 420,
        corrupt_fraction: float = 0.5,
    ) -> None:
        if isinstance(seed, bool) or not isinstance(seed, int):
            raise TypeError("seed must be an integer")
        if isinstance(n_components, bool) or not isinstance(n_components, int) or n_components < 1:
            raise ValueError("n_components must be a positive integer")
        if isinstance(corrupt_fraction, bool) or not isinstance(corrupt_fraction, (int, float)):
            raise TypeError("corrupt_fraction must be an int or float")
        if not 0 <= float(corrupt_fraction) <= 1:
            raise ValueError("corrupt_fraction must be in [0, 1]")
        self.workspace = Path(workspace)
        self.seed = seed
        self.n_components = n_components
        self.corrupt_fraction = float(corrupt_fraction)

    @staticmethod
    def _append_event(
        ledger_path: Path,
        records: list[dict[str, Any]],
        event: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        previous = records[-1]["hash"] if records else GENESIS
        body = {
            "schema": SCHEMA,
            "sequence": len(records) + 1,
            "timestamp": datetime.now(UTC).isoformat(),
            "event": event,
            "payload": payload,
            "previous_hash": previous,
        }
        record = dict(body, hash=sha256_hex(canonical_dumps(body)))
        with ledger_path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(canonical_dumps(record) + "\n")
        records.append(record)
        return record

    def _new_run_dir(self) -> tuple[str, Path]:
        self.workspace.mkdir(parents=True, exist_ok=True)
        run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        candidate = self.workspace / f"run-{run_id}"
        suffix = 1
        while candidate.exists():
            candidate = self.workspace / f"run-{run_id}-{suffix}"
            suffix += 1
        candidate.mkdir(parents=True, exist_ok=False)
        return candidate.name, candidate

    def run(self) -> PhoenixResult:
        run_id, run_dir = self._new_run_dir()
        components_dir = run_dir / "components"
        snapshots_dir = run_dir / "snapshots"
        components_dir.mkdir()
        snapshots_dir.mkdir()
        ledger_path = run_dir / "events.jsonl"
        ledger_path.touch(exist_ok=False)

        rng = random.Random(self.seed)
        manifest_components: list[dict[str, str]] = []
        original_hashes: dict[str, str] = {}
        for index in range(self.n_components):
            component_id = f"component-{index:06d}"
            payload = {
                "component_id": component_id,
                "seed": self.seed,
                "value": f"{rng.getrandbits(256):064x}",
            }
            raw = (canonical_dumps(payload) + "\n").encode("utf-8")
            component_path = components_dir / f"{component_id}.json"
            snapshot_path = snapshots_dir / f"{component_id}.json"
            component_path.write_bytes(raw)
            snapshot_path.write_bytes(raw)
            component_hash = sha256_hex(raw)
            original_hashes[component_id] = component_hash
            manifest_components.append({"component_id": component_id, "sha256": component_hash})

        manifest = {
            "schema": "omega-phoenix-baseline/1.0",
            "seed": self.seed,
            "n_components": self.n_components,
            "corrupt_fraction": self.corrupt_fraction,
            "components": manifest_components,
        }
        manifest_path = run_dir / "baseline_manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        manifest_sha256 = sha256_hex(canonical_dumps(manifest))

        records: list[dict[str, Any]] = []
        self._append_event(ledger_path, records, "benchmark.started", {
            "seed": self.seed,
            "n_components": self.n_components,
            "corrupt_fraction": self.corrupt_fraction,
        })
        self._append_event(ledger_path, records, "snapshot.created", {
            "component_count": self.n_components,
            "baseline_manifest_sha256": manifest_sha256,
        })
        immutable_prefix = ledger_path.read_bytes()

        corrupt_count = round(self.n_components * self.corrupt_fraction)
        selected = sorted(rng.sample(range(self.n_components), corrupt_count)) if corrupt_count else []
        corrupted_ids = [f"component-{index:06d}" for index in selected]
        for component_id in corrupted_ids:
            component_path = components_dir / f"{component_id}.json"
            damaged = {"component_id": component_id, "corrupted": True, "seed": self.seed}
            component_path.write_text(canonical_dumps(damaged) + "\n", encoding="utf-8")
        self._append_event(ledger_path, records, "corruption.injected", {
            "corrupted_count": len(corrupted_ids),
            "component_ids": corrupted_ids,
        })

        recovered_ids: list[str] = []
        for component_id in corrupted_ids:
            component_path = components_dir / f"{component_id}.json"
            snapshot_path = snapshots_dir / f"{component_id}.json"
            component_path.write_bytes(snapshot_path.read_bytes())
            if sha256_hex(component_path.read_bytes()) == original_hashes[component_id]:
                recovered_ids.append(component_id)
        self._append_event(ledger_path, records, "recovery.applied", {
            "recovered_count": len(recovered_ids),
            "component_ids": recovered_ids,
        })

        all_components_verified = all(
            sha256_hex((components_dir / f"{component_id}.json").read_bytes()) == expected_hash
            for component_id, expected_hash in original_hashes.items()
        )
        recovery_rate = len(recovered_ids) / len(corrupted_ids) if corrupted_ids else 1.0
        append_only_history_preserved = ledger_path.read_bytes().startswith(immutable_prefix)
        self._append_event(ledger_path, records, "verification.completed", {
            "all_components_verified": all_components_verified,
            "recovery_rate": recovery_rate,
            "append_only_history_preserved": append_only_history_preserved,
        })
        ledger_valid_before_finish = verify_ledger(records)
        passed = all_components_verified and append_only_history_preserved and ledger_valid_before_finish
        self._append_event(ledger_path, records, "benchmark.finished", {
            "passed": passed,
            "ledger_valid_before_finish": ledger_valid_before_finish,
        })

        stored_records = [
            json.loads(line)
            for line in ledger_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        ledger_valid = verify_ledger(stored_records)
        ledger_sha256 = sha256_hex(ledger_path.read_bytes())
        errors: list[str] = []
        if not all_components_verified:
            errors.append("one or more component hashes did not recover")
        if not append_only_history_preserved:
            errors.append("initial ledger history prefix changed")
        if not ledger_valid:
            errors.append("event ledger hash chain failed verification")
        passed = passed and ledger_valid

        result = PhoenixResult(
            schema=SCHEMA,
            run_id=run_id,
            output_dir=str(run_dir),
            seed=self.seed,
            n_components=self.n_components,
            corrupt_fraction=self.corrupt_fraction,
            corrupted_count=len(corrupted_ids),
            recovered_count=len(recovered_ids),
            recovery_rate=recovery_rate,
            append_only_history_preserved=append_only_history_preserved,
            ledger_valid=ledger_valid,
            all_components_verified=all_components_verified,
            baseline_manifest_sha256=manifest_sha256,
            ledger_sha256=ledger_sha256,
            passed=passed,
            errors=tuple(errors),
        )
        (run_dir / "result.json").write_text(
            json.dumps(result.to_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return result

