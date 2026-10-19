from pathlib import Path

import pytest

from omega.phoenix.benchmark import PhoenixBenchmark


def test_phoenix_recovers_corruption_and_preserves_history(tmp_path: Path):
    result = PhoenixBenchmark(
        tmp_path / "phoenix", seed=123, n_components=100, corrupt_fraction=0.90
    ).run()

    assert result.recovery_rate >= 0.90
    assert result.recovered_components == result.corrupted_components
    assert result.append_only_history_preserved is True
    assert result.passed is True


def test_phoenix_zero_corruption_is_a_valid_noop(tmp_path: Path):
    result = PhoenixBenchmark(
        tmp_path / "clean", seed=7, n_components=5, corrupt_fraction=0.0
    ).run()

    assert result.recovery_rate == 1.0
    assert result.recovered_components == 0
    assert result.append_only_history_preserved is True
    assert result.passed is True


@pytest.mark.parametrize(
    ("n_components", "corrupt_fraction"),
    [(0, 0.5), (-1, 0.5), (10, -0.1), (10, 1.1)],
)
def test_phoenix_rejects_invalid_configuration(
    tmp_path: Path, n_components: int, corrupt_fraction: float
):
    with pytest.raises(ValueError):
        PhoenixBenchmark(
            tmp_path / "invalid",
            n_components=n_components,
            corrupt_fraction=corrupt_fraction,
        )


def test_phoenix_does_not_overwrite_existing_evidence(tmp_path: Path):
    root = tmp_path / "existing"
    root.mkdir()
    (root / "prior-evidence.txt").write_text("preserve me", encoding="utf-8")

    with pytest.raises(FileExistsError):
        PhoenixBenchmark(root, n_components=2).run()

    assert (root / "prior-evidence.txt").read_text(encoding="utf-8") == "preserve me"
