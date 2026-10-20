import hashlib
import json
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


def test_nonzero_corruption_fraction_exercises_single_component(tmp_path: Path):
    result = PhoenixBenchmark(
        tmp_path / "single", seed=7, n_components=1, corrupt_fraction=0.01
    ).run()

    assert result.corrupted_components == 1
    assert result.recovered_components == 1
    assert result.recovery_rate == 1.0
    assert result.passed is True


def test_concurrent_journal_append_cannot_escape_components_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    root = tmp_path / "phoenix"
    escaped = tmp_path / "escaped.txt"
    escaped.write_text("preserve this file", encoding="utf-8")
    original_write_bytes = Path.write_bytes
    injected = False
    payload = b"unexpected payload"
    malicious_record = {
        "index": 0,
        "path": "/".join(["..", "..", "escaped.txt"]),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "payload_hex": payload.hex(),
    }

    def append_after_snapshot(path: Path, data: bytes) -> int:
        nonlocal injected
        if not injected and path.name.startswith("component-") and data.startswith(
            b"CORRUPTED:"
        ):
            with (root / "phoenix-history.jsonl").open("ab") as history:
                history.write(
                    (json.dumps(malicious_record, sort_keys=True) + "\n").encode()
                )
            injected = True
        return original_write_bytes(path, data)

    monkeypatch.setattr(Path, "write_bytes", append_after_snapshot)
    result = PhoenixBenchmark(
        root, seed=123, n_components=10, corrupt_fraction=0.9
    ).run()

    assert injected is True
    assert escaped.read_text(encoding="utf-8") == "preserve this file"
    assert result.append_only_history_preserved is False
    assert result.passed is False


@pytest.mark.parametrize(
    ("n_components", "corrupt_fraction", "exception"),
    [
        (0, 0.5, ValueError),
        (-1, 0.5, ValueError),
        (1.9, 0.5, TypeError),
        (True, 0.5, TypeError),
        (10, -0.1, ValueError),
        (10, 1.1, ValueError),
    ],
)
def test_phoenix_rejects_invalid_configuration(
    tmp_path: Path,
    n_components: int,
    corrupt_fraction: float,
    exception: type[Exception],
):
    with pytest.raises(exception):
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
