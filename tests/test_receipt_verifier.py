import hashlib
import json
from pathlib import Path

import pytest

from omega.phoenix.receipts import (
    verify_artifact_receipt,
    verify_phoenix_sha256_manifest,
)
from scripts import omega_link


def make_receipt(root: Path, relative_path: str, status: str = "TESTED_PENDING_REVIEW"):
    artifact = root / relative_path
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    return {
        "repo": "phoenix-stack",
        "claim": "Phoenix artifact test",
        "commit": "a" * 40,
        "artifact": relative_path,
        "artifact_sha256": digest,
        "linked_at": "2026-11-23T00:00:00Z",
        "status": status,
        "independently_reproduced": False,
    }


def test_receipt_verifies_phoenix_artifact_bytes(tmp_path: Path):
    artifact = tmp_path / "runs" / "45062559484" / "opportunity-scout.json"
    artifact.parent.mkdir(parents=True)
    artifact.write_text('{"run_id":45062559484,"records":101}\n', encoding="utf-8")
    receipt = make_receipt(tmp_path, "runs/45062559484/opportunity-scout.json")
    result = verify_artifact_receipt(receipt, tmp_path)
    assert result.valid is True
    assert result.expected_sha256 == result.actual_sha256


def test_tampered_phoenix_artifact_is_rejected(tmp_path: Path):
    artifact = tmp_path / "runs" / "result.json"
    artifact.parent.mkdir()
    artifact.write_text('{"passed":true}\n', encoding="utf-8")
    receipt = make_receipt(tmp_path, "runs/result.json")
    artifact.write_text('{"passed":false}\n', encoding="utf-8")
    result = verify_artifact_receipt(receipt, tmp_path)
    assert result.valid is False
    assert result.reason == "artifact SHA-256 mismatch"


def test_phoenix_sha256_manifest_verifies_and_rejects_tampering(tmp_path: Path):
    first = tmp_path / "opportunity-scout.json"
    second = tmp_path / "verification-receipts.json"
    first.write_text('{"records":101}\n', encoding="utf-8")
    second.write_text('{"receipts":98}\n', encoding="utf-8")
    manifest = tmp_path / "manifest.sha256"
    manifest.write_text(
        f"{hashlib.sha256(first.read_bytes()).hexdigest()}  {first.name}\n"
        f"{hashlib.sha256(second.read_bytes()).hexdigest()}  {second.name}\n",
        encoding="utf-8",
    )
    valid = verify_phoenix_sha256_manifest(manifest, tmp_path)
    assert valid.valid is True
    assert valid.checked_files == 2

    second.write_text('{"receipts":97}\n', encoding="utf-8")
    tampered = verify_phoenix_sha256_manifest(manifest, tmp_path)
    assert tampered.valid is False
    assert len(tampered.failures) == 1
    assert "SHA-256 mismatch" in tampered.failures[0]


def test_manifest_preserves_literal_leading_asterisk_paths(tmp_path: Path):
    text_mode = tmp_path / "*literal.txt"
    binary_mode = tmp_path / "*binary.txt"
    text_mode.write_text("text-mode payload\\n", encoding="utf-8")
    binary_mode.write_text("binary-mode payload\\n", encoding="utf-8")
    text_digest = hashlib.sha256(text_mode.read_bytes()).hexdigest()
    binary_digest = hashlib.sha256(binary_mode.read_bytes()).hexdigest()
    manifest = tmp_path / "manifest.sha256"
    manifest.write_text(
        f"{text_digest}  *literal.txt\\n"
        f"{binary_digest} **binary.txt\\n",
        encoding="utf-8",
    )

    result = verify_phoenix_sha256_manifest(manifest, tmp_path)
    assert result.valid is True
    assert result.checked_files == 2

    text_mode.write_text("tampered\\n", encoding="utf-8")
    tampered = verify_phoenix_sha256_manifest(manifest, tmp_path)
    assert tampered.valid is False
    assert any("*literal.txt" in failure for failure in tampered.failures)


def test_receipt_rejects_path_traversal(tmp_path: Path):
    receipt = {
        "repo": "phoenix-stack",
        "claim": "escape test",
        "commit": "a" * 40,
        "artifact": "../outside.json",
        "artifact_sha256": "0" * 64,
        "status": "TESTED_PENDING_REVIEW",
        "independently_reproduced": False,
    }
    result = verify_artifact_receipt(receipt, tmp_path)
    assert result.valid is False
    assert "confined relative path" in result.reason


def test_verified_status_requires_independent_reproduction(tmp_path: Path):
    artifact = tmp_path / "proof.json"
    artifact.write_text('{"proof":"hash-only"}\n', encoding="utf-8")
    receipt = make_receipt(tmp_path, "proof.json", status="VERIFIED")
    result = verify_artifact_receipt(receipt, tmp_path)
    assert result.valid is False
    assert "independent reproduction" in result.reason


def test_omega_link_appends_a_verifiable_phoenix_receipt(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    artifact = tmp_path / "phoenix" / "run.json"
    artifact.parent.mkdir()
    artifact.write_text('{"run_id":45062559484,"passed":true}\n', encoding="utf-8")
    monkeypatch.setattr(omega_link, "git_head", lambda: "b" * 40)

    omega_link.link("phoenix/run.json", "Phoenix run artifact", repo="phoenix-stack")

    ledger = tmp_path / "EVIDENCE_LEDGER.jsonl"
    receipt = json.loads(ledger.read_text(encoding="utf-8").splitlines()[0])
    result = verify_artifact_receipt(receipt, tmp_path)
    assert result.valid is True
    assert receipt["repo"] == "phoenix-stack"
    assert receipt["status"] == "TESTED_PENDING_REVIEW"


def test_omega_link_rejects_artifacts_outside_repository_root(tmp_path: Path, monkeypatch):
    repository = tmp_path / "repo"
    outside = tmp_path / "outside.json"
    repository.mkdir()
    outside.write_text('{"external":true}\n', encoding="utf-8")
    monkeypatch.chdir(repository)
    monkeypatch.setattr(omega_link, "git_head", lambda: "c" * 40)
    with pytest.raises(ValueError, match="inside the current repository root"):
        omega_link.link(str(outside), "outside artifact")
