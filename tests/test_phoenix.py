"""Tests for the local Phoenix recovery benchmark."""

import json
from pathlib import Path

import pytest

from omega.phoenix.benchmark import PhoenixBenchmark, verify_ledger


def test_phoenix_recovery(tmp_path: Path):
    bench = PhoenixBenchmark(tmp_path / "phoenix", seed=123, n_components=100, corrupt_fraction=0.90)
    result = bench.run()
    assert result.recovery_rate >= 0.90
    assert result.append_only_history_preserved is True
    assert result.ledger_valid is True
    assert result.all_components_verified is True
    assert result.corrupted_count == 90
    assert result.recovered_count == 90
    assert result.passed is True
    receipt = json.loads((Path(result.output_dir) / "result.json").read_text(encoding="utf-8"))
    assert receipt["passed"] is True


def test_ledger_tampering_is_detected(tmp_path: Path):
    result = PhoenixBenchmark(tmp_path / "phoenix", seed=7, n_components=8, corrupt_fraction=0.5).run()
    ledger_path = Path(result.output_dir) / "events.jsonl"
    records = [json.loads(line) for line in ledger_path.read_text(encoding="utf-8").splitlines()]
    assert verify_ledger(records) is True
    records[0]["payload"]["seed"] = 999
    assert verify_ledger(records) is False


def test_zero_corruption_is_a_valid_cycle(tmp_path: Path):
    result = PhoenixBenchmark(tmp_path / "phoenix", seed=1, n_components=5, corrupt_fraction=0).run()
    assert result.corrupted_count == 0
    assert result.recovery_rate == 1.0
    assert result.passed is True


@pytest.mark.parametrize("kwargs", [
    {"n_components": 0},
    {"n_components": -1},
    {"corrupt_fraction": -0.1},
    {"corrupt_fraction": 1.1},
    {"seed": True},
])
def test_invalid_configuration_is_rejected(tmp_path: Path, kwargs):
    with pytest.raises(ValueError):
        PhoenixBenchmark(tmp_path / "phoenix", **kwargs)
