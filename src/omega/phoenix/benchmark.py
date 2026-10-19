"""Deterministic, local-only recovery benchmark for Phoenix.

This benchmark is a bounded test fixture, not a production recovery service.
It writes synthetic component files and an append-only JSONL baseline journal,
corrupts a deterministic subset, restores them from the journal, and verifies
both recovery and journal immutability.
"""
from __future__ import annotations

import hashlib
import json
import random
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class PhoenixResult:
    seed: int
    n_components: int
    corrupt_fraction: float
    corrupted_components: int
    recovered_components: int
    recovery_rate: float
    append_only_history_preserved: bool
    passed: bool

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class PhoenixBenchmark:
    """Run a deterministic recovery test using only local files."""

    def __init__(
        self,
        root: Path,
        seed: int = 42,
        n_components: int = 100,
        corrupt_fraction: float = 0.90,
    ) -> None:
        if isinstance(n_components, bool) or not isinstance(n_components, int):
            raise ValueError("n_components must be an integer")
        if n_components < 1:
            raise ValueError("n_components must be at least 1")
        if not 0.0 <= corrupt_fraction <= 1.0:
            raise ValueError("corrupt_fraction must be between 0 and 1")
        self.root = Path(root)
        self.seed = int(seed)
        self.n_components = int(n_components)
        self.corrupt_fraction = float(corrupt_fraction)

    @staticmethod
    def _digest(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    def run(self) -> PhoenixResult:
        # Refuse any non-empty run directory, not merely one containing
        # Phoenix's own filenames. Unrelated prior evidence is evidence too.
        if self.root.exists() and any(self.root.iterdir()):
            raise FileExistsError(
                f"Benchmark path already contains data: {self.root}. "
                "Choose a fresh run directory to preserve prior evidence."
            )

        components_dir = self.root / "components"
        components_dir.mkdir(parents=True, exist_ok=True)
        journal = self.root / "phoenix-history.jsonl"

        baselines: dict[str, bytes] = {}
        with journal.open("xb") as history:
            for index in range(self.n_components):
                name = f"component-{index:05d}.bin"
                payload = f"phoenix:{self.seed}:component:{index}\n".encode()
                baselines[name] = payload
                (components_dir / name).write_bytes(payload)
                record = {
                    "index": index,
                    "path": name,
                    "sha256": self._digest(payload),
                    "payload_hex": payload.hex(),
                }
                history.write(
                    (json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n").encode()
                )
            history.flush()

        journal_before = journal.read_bytes()
        journal_digest_before = self._digest(journal_before)

        count_to_corrupt = int(self.n_components * self.corrupt_fraction)
        selected = set(random.Random(self.seed).sample(range(self.n_components), count_to_corrupt))
        for index in selected:
            name = f"component-{index:05d}.bin"
            (components_dir / name).write_bytes(f"CORRUPTED:{self.seed}:{index}\n".encode())

        # Recovery trusts only journal records whose payload hashes verify.
        recovered = 0
        for line in journal.read_text(encoding="utf-8").splitlines():
            record = json.loads(line)
            name = str(record["path"])
            payload = bytes.fromhex(str(record["payload_hex"]))
            if self._digest(payload) != record["sha256"]:
                continue
            target = components_dir / name
            if not target.exists() or target.read_bytes() != payload:
                target.write_bytes(payload)
                recovered += 1

        # Validate every component against its immutable baseline.
        restored_count = sum(
            1
            for name, expected in baselines.items()
            if (components_dir / name).exists()
            and (components_dir / name).read_bytes() == expected
        )
        recovery_rate = (
            1.0 if count_to_corrupt == 0 else min(1.0, recovered / count_to_corrupt)
        )
        history_preserved = (
            journal.exists()
            and self._digest(journal.read_bytes()) == journal_digest_before
            and journal.read_bytes() == journal_before
        )
        passed = (
            restored_count == self.n_components
            and recovery_rate >= 0.90
            and history_preserved
        )
        return PhoenixResult(
            seed=self.seed,
            n_components=self.n_components,
            corrupt_fraction=self.corrupt_fraction,
            corrupted_components=count_to_corrupt,
            recovered_components=recovered,
            recovery_rate=recovery_rate,
            append_only_history_preserved=history_preserved,
            passed=passed,
        )
