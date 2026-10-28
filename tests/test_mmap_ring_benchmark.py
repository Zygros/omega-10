from __future__ import annotations

import hashlib
import json
from pathlib import Path
from runpy import run_path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT_ROOT / "scripts" / "mmap_ring_benchmark.py"
RUNNER = run_path(str(SCRIPT), run_name="mmap_ring_benchmark_under_test")
run_benchmark = RUNNER["run_benchmark"]
persist_report = RUNNER["persist_report"]
validate_config = RUNNER["validate_config"]


def test_benchmark_validates_every_measured_record_cycle() -> None:
    report = run_benchmark(
        cycles=500,
        warmup=12,
        slots=7,
        rounds=2,
        invocation=["test-mmap-ring-benchmark"],
    )

    assert report["schema"] == "omega-10/mmap-ring-benchmark/v1"
    assert report["status"] == "PASS"
    assert report["configuration"]["total_measured_cycles"] == 1_000
    assert report["results"]["record_writes_during_measurement"] == 1_000
    assert report["results"]["record_reads_during_measurement"] == 1_000
    assert report["results"]["record_access_calls_during_measurement"] == 2_000
    assert report["integrity"]["all_measured_records_valid"] is True
    assert report["integrity"]["verification_failures"] == 0
    assert len(report["results"]["round_validated_cycles_per_second"]) == 2
    assert report["results"]["median_validated_cycles_per_second"] > 0
    assert report["source"]["sha256"] == hashlib.sha256(SCRIPT.read_bytes()).hexdigest()
    assert "Not durable-storage IOPS or disk IOPS." in (
        report["measurement_contract"]["scope_limits"]
    )
    assert report["measurement_contract"]["durability"].startswith(
        "No per-record fsync."
    )


def test_evidence_report_is_hashed_and_never_silently_overwritten(
    tmp_path: Path,
) -> None:
    output = tmp_path / "mmap-ring.json"
    report = run_benchmark(
        cycles=100,
        warmup=5,
        slots=3,
        rounds=1,
        invocation=["test-evidence-report"],
    )
    receipt = persist_report(report, output)

    report_bytes = output.read_bytes()
    saved_report = json.loads(report_bytes)
    digest, stored_name = Path(receipt["sha256_sidecar"]).read_text().split(
        "  ", maxsplit=1
    )
    assert saved_report == report
    assert digest == hashlib.sha256(report_bytes).hexdigest()
    assert digest == receipt["sha256"]
    assert stored_name.strip() == output.name

    with pytest.raises(FileExistsError, match="Refusing to overwrite"):
        persist_report(report, output)
    assert output.read_bytes() == report_bytes


def test_invalid_or_excessive_configuration_is_rejected() -> None:
    invalid_configurations = (
        (0, 0, 1, 1),
        (1, -1, 1, 1),
        (1, 0, 0, 1),
        (1, 0, 1, 21),
        (10_000_000, 0, 1, 6),
    )
    for configuration in invalid_configurations:
        with pytest.raises(ValueError):
            validate_config(*configuration)
