#!/usr/bin/env python3
"""Run a bounded, reproducible memory-mapped ring-buffer microbenchmark.

This measures Python-level validated record cycles, not durable-storage IOPS.
It uses only the Python standard library and creates a temporary backing file.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import mmap
import os
import platform
import statistics
import struct
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA = "omega-10/mmap-ring-benchmark/v1"
RECORD = struct.Struct("<QQQ")
MASK64 = (1 << 64) - 1
GUARD_MASK = 0xA5A5A5A55A5A5A5A
MULTIPLIER = 0x9E3779B185EBCA87
MAX_CYCLES_PER_ROUND = 10_000_000
MAX_WARMUP_CYCLES = 1_000_000
MAX_SLOTS = 1_000_000
MAX_ROUNDS = 20
MAX_TOTAL_MEASURED_CYCLES = 50_000_000
MAX_TOTAL_WARMUP_CYCLES = 10_000_000


def validate_config(cycles: int, warmup: int, slots: int, rounds: int) -> None:
    """Reject invalid or unbounded configurations before creating any file."""
    values = {
        "cycles": cycles,
        "warmup": warmup,
        "slots": slots,
        "rounds": rounds,
    }
    for name, value in values.items():
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError(f"{name} must be an integer")

    if not 1 <= cycles <= MAX_CYCLES_PER_ROUND:
        raise ValueError(
            f"cycles must be between 1 and {MAX_CYCLES_PER_ROUND}"
        )
    if not 0 <= warmup <= MAX_WARMUP_CYCLES:
        raise ValueError(f"warmup must be between 0 and {MAX_WARMUP_CYCLES}")
    if not 1 <= slots <= MAX_SLOTS:
        raise ValueError(f"slots must be between 1 and {MAX_SLOTS}")
    if not 1 <= rounds <= MAX_ROUNDS:
        raise ValueError(f"rounds must be between 1 and {MAX_ROUNDS}")
    if cycles * rounds > MAX_TOTAL_MEASURED_CYCLES:
        raise ValueError(
            "cycles multiplied by rounds exceeds "
            f"{MAX_TOTAL_MEASURED_CYCLES} measured cycles"
        )
    if warmup * rounds > MAX_TOTAL_WARMUP_CYCLES:
        raise ValueError(
            "warmup multiplied by rounds exceeds "
            f"{MAX_TOTAL_WARMUP_CYCLES} warm-up cycles"
        )


def _record_cycle(mapping: mmap.mmap, sequence: int, slots: int) -> None:
    """Write one fixed-size record, read it back, and validate all fields."""
    offset = (sequence % slots) * RECORD.size
    expected = (
        sequence & MASK64,
        (sequence ^ GUARD_MASK) & MASK64,
        ((sequence * MULTIPLIER) ^ (sequence >> 7)) & MASK64,
    )
    RECORD.pack_into(mapping, offset, *expected)
    observed = RECORD.unpack_from(mapping, offset)
    if observed != expected:
        raise RuntimeError(
            f"record integrity failure at sequence {sequence}: "
            f"expected={expected!r} observed={observed!r}"
        )


def _git_head() -> str | None:
    """Return the checked-out revision when the script runs inside a Git repo."""
    project_root = Path(__file__).resolve().parents[1]
    try:
        result = subprocess.run(
            ["git", "-C", str(project_root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip() or None


def run_benchmark(
    *,
    cycles: int = 100_000,
    warmup: int = 10_000,
    slots: int = 4_096,
    rounds: int = 3,
    invocation: list[str] | None = None,
) -> dict[str, Any]:
    """Run the bounded mmap benchmark and return a machine-readable receipt."""
    validate_config(cycles, warmup, slots, rounds)

    started_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    mapped_bytes = slots * RECORD.size
    round_seconds: list[float] = []
    round_rates: list[float] = []
    measured_cycles = cycles * rounds
    sequence = 0
    flush_seconds = 0.0

    with tempfile.TemporaryDirectory(prefix="omega10-mmap-ring-") as temp_dir:
        backing_path = Path(temp_dir) / "ring.bin"
        with backing_path.open("w+b") as backing:
            backing.truncate(mapped_bytes)
            with mmap.mmap(
                backing.fileno(), mapped_bytes, access=mmap.ACCESS_WRITE
            ) as mapping:
                for _ in range(rounds):
                    for _ in range(warmup):
                        _record_cycle(mapping, sequence, slots)
                        sequence += 1

                    round_start_ns = time.perf_counter_ns()
                    for _ in range(cycles):
                        _record_cycle(mapping, sequence, slots)
                        sequence += 1
                    elapsed_ns = max(1, time.perf_counter_ns() - round_start_ns)
                    elapsed = elapsed_ns / 1_000_000_000
                    round_seconds.append(elapsed)
                    round_rates.append(cycles / elapsed)

                flush_start_ns = time.perf_counter_ns()
                mapping.flush()
                flush_seconds = (
                    time.perf_counter_ns() - flush_start_ns
                ) / 1_000_000_000

    source_path = Path(__file__).resolve()
    source_sha256 = hashlib.sha256(source_path.read_bytes()).hexdigest()
    environment = {
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor() or None,
        "logical_cpu_count": os.cpu_count(),
    }
    median_rate = statistics.median(round_rates)
    return {
        "schema": SCHEMA,
        "status": "PASS",
        "classification": "local-reproducible-microbenchmark",
        "started_at_utc": started_at,
        "source": {
            "script": "scripts/mmap_ring_benchmark.py",
            "sha256": source_sha256,
            "git_head": _git_head(),
            "github_workflow_sha": os.environ.get("GITHUB_SHA"),
        },
        "environment": environment,
        "configuration": {
            "cycles_per_round": cycles,
            "warmup_cycles_per_round": warmup,
            "rounds": rounds,
            "ring_slots": slots,
            "record_size_bytes": RECORD.size,
            "mapped_bytes": mapped_bytes,
            "total_measured_cycles": measured_cycles,
            "total_warmup_cycles": warmup * rounds,
        },
        "results": {
            "round_elapsed_seconds": round_seconds,
            "round_validated_cycles_per_second": round_rates,
            "median_validated_cycles_per_second": median_rate,
            "minimum_validated_cycles_per_second": min(round_rates),
            "maximum_validated_cycles_per_second": max(round_rates),
            "record_writes_during_measurement": measured_cycles,
            "record_reads_during_measurement": measured_cycles,
            "record_access_calls_during_measurement": measured_cycles * 2,
            "final_mmap_flush_seconds_excluded_from_throughput": flush_seconds,
        },
        "integrity": {
            "all_measured_records_valid": True,
            "verification_failures": 0,
            "validation": (
                "Every measured cycle writes a 24-byte record, reads it back, "
                "and compares all three uint64 fields."
            ),
        },
        "measurement_contract": {
            "one_validated_cycle": (
                "One struct.pack_into write followed by one struct.unpack_from "
                "read and an equality check of all three record fields."
            ),
            "timed_region": (
                "Record writes, reads, and comparisons only. Excludes warm-up, "
                "mapping setup, final mmap.flush, and report serialization."
            ),
            "backing_store": (
                "Temporary file in the operating system's default temporary "
                "directory; it is removed after the run."
            ),
            "durability": (
                "No per-record fsync. One final mmap.flush is timed separately; "
                "stable-storage durability is not asserted."
            ),
            "scope_limits": [
                "Not durable-storage IOPS or disk IOPS.",
                "Not CPU instructions per second.",
                "Not network, GPU, distributed, or production throughput.",
                (
                    "Not directly comparable with an IOPS claim unless that "
                    "claim uses this exact operation contract and environment."
                ),
                "This run is not an independent reproduction or certification.",
            ],
        },
        "invocation": invocation if invocation is not None else sys.argv[:],
    }


def persist_report(report: dict[str, Any], output_path: Path) -> dict[str, str]:
    """Create a new report and SHA-256 sidecar without overwriting evidence."""
    output = Path(output_path)
    sidecar = Path(f"{output}.sha256")
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists() or sidecar.exists():
        raise FileExistsError(
            "Refusing to overwrite existing evidence; choose a new output path: "
            f"{output}"
        )

    payload = (json.dumps(report, indent=2, sort_keys=True) + "\n").encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()
    with output.open("xb") as handle:
        handle.write(payload)
    with sidecar.open("x", encoding="utf-8") as handle:
        handle.write(f"{digest}  {output.name}\n")
    return {"report": str(output), "sha256_sidecar": str(sidecar), "sha256": digest}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Measure validated write/read cycles on a temporary memory-mapped "
            "ring buffer. This is not a disk-IOPS benchmark."
        )
    )
    parser.add_argument("--cycles", type=int, default=100_000)
    parser.add_argument("--warmup", type=int, default=10_000)
    parser.add_argument("--slots", type=int, default=4_096)
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument(
        "--output",
        type=Path,
        help="optional new JSON report path; a .sha256 sidecar is also written",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    invocation = [str(Path(__file__).relative_to(Path.cwd()))] + (
        argv if argv is not None else sys.argv[1:]
    )
    try:
        report = run_benchmark(
            cycles=args.cycles,
            warmup=args.warmup,
            slots=args.slots,
            rounds=args.rounds,
            invocation=invocation,
        )
        evidence = None
        if args.output is not None:
            evidence = persist_report(report, args.output)
        print(json.dumps(report, indent=2, sort_keys=True))
        if evidence is not None:
            print(
                "evidence_files="
                f"{evidence['report']},{evidence['sha256_sidecar']};"
                f"sha256={evidence['sha256']}",
                file=sys.stderr,
            )
        return 0
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
