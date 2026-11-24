"""Hash-linked verification for local and Phoenix-published artifacts.

Verification checks byte identity only. It does not prove that a claim is true,
that a test actually ran, or that an external timestamp is independently confirmed.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import hashlib
import hmac
from pathlib import Path, PurePosixPath
import re
from typing import Any


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
_ALLOWED_STATUSES = {
    "TESTED_PENDING_REVIEW",
    "VERIFIED",
    "INDEPENDENTLY_VERIFIED",
    "BLOCKED",
    "REJECTED",
}


@dataclass(frozen=True)
class ReceiptVerification:
    valid: bool
    reason: str
    expected_sha256: str | None = None
    actual_sha256: str | None = None


@dataclass(frozen=True)
class ManifestVerification:
    valid: bool
    checked_files: int
    failures: tuple[str, ...]


def _resolve_artifact(root: Path, relative_path: str) -> Path:
    rel = PurePosixPath(relative_path)
    if rel.is_absolute() or not rel.parts or any(
        part in ("", ".", "..") for part in rel.parts
    ):
        raise ValueError("artifact path must be a confined relative path")

    current = root
    for part in rel.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError("symlinked artifact paths are not allowed")

    resolved = current.resolve(strict=True)
    if resolved != root and root not in resolved.parents:
        raise ValueError("artifact path escaped the evidence root")
    if not resolved.is_file():
        raise ValueError("artifact path is not a regular file")
    return resolved


def verify_file_digest(
    artifact_root: str | Path,
    relative_path: str,
    expected_sha256: str,
) -> ReceiptVerification:
    """Verify one artifact against a SHA-256 digest under a confined root."""
    if not isinstance(expected_sha256, str) or not _SHA256_RE.fullmatch(
        expected_sha256
    ):
        return ReceiptVerification(False, "invalid expected SHA-256")

    root = Path(artifact_root).expanduser().resolve(strict=True)
    try:
        artifact = _resolve_artifact(root, relative_path)
    except (OSError, ValueError) as exc:
        return ReceiptVerification(False, str(exc), expected_sha256, None)

    digest = hashlib.sha256()
    with artifact.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    actual = digest.hexdigest()
    if not hmac.compare_digest(actual, expected_sha256):
        return ReceiptVerification(False, "artifact SHA-256 mismatch", expected_sha256, actual)
    return ReceiptVerification(True, "artifact SHA-256 matches", expected_sha256, actual)


def verify_artifact_receipt(
    receipt: Mapping[str, Any],
    artifact_root: str | Path,
) -> ReceiptVerification:
    """Verify an omega_link receipt against the referenced artifact bytes."""
    if not isinstance(receipt, Mapping):
        return ReceiptVerification(False, "receipt must be a mapping")

    for field in ("repo", "claim", "artifact", "artifact_sha256", "commit", "status"):
        if not isinstance(receipt.get(field), str) or not receipt[field].strip():
            return ReceiptVerification(False, f"missing or invalid receipt field: {field}")

    if not _COMMIT_RE.fullmatch(receipt["commit"]):
        return ReceiptVerification(False, "invalid commit identifier")
    if receipt["status"] not in _ALLOWED_STATUSES:
        return ReceiptVerification(False, "unsupported receipt status")
    reproduced = receipt.get("independently_reproduced")
    if not isinstance(reproduced, bool):
        return ReceiptVerification(False, "independently_reproduced must be boolean")
    if receipt["status"] in {"VERIFIED", "INDEPENDENTLY_VERIFIED"} and not reproduced:
        return ReceiptVerification(False, "verified status requires independent reproduction")

    return verify_file_digest(
        artifact_root,
        receipt["artifact"],
        receipt["artifact_sha256"],
    )


def verify_phoenix_sha256_manifest(
    manifest_path: str | Path,
    artifact_root: str | Path,
) -> ManifestVerification:
    """Verify a standard Phoenix manifest: '<sha256>  <relative-path>' per line."""
    manifest = Path(manifest_path).expanduser().resolve(strict=True)
    root = Path(artifact_root).expanduser().resolve(strict=True)
    if not manifest.is_file():
        return ManifestVerification(False, 0, ("manifest is not a regular file",))

    failures: list[str] = []
    checked = 0
    for line_number, line in enumerate(
        manifest.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        if len(line) < 66:
            failures.append(f"line {line_number}: malformed manifest entry")
            continue
        expected = line[:64]
        separator = line[64:66]
        if not _SHA256_RE.fullmatch(expected):
            failures.append(f"line {line_number}: invalid SHA-256 digest")
            continue
        if separator == "  " or separator == " *":
            relative_path = line[66:]
        else:
            failures.append(f"line {line_number}: malformed manifest separator")
            continue
        if not relative_path:
            failures.append(f"line {line_number}: missing artifact path")
            continue
        result = verify_file_digest(root, relative_path, expected)
        checked += 1
        if not result.valid:
            failures.append(f"line {line_number} ({relative_path}): {result.reason}")

    if checked == 0:
        failures.append("manifest contains no artifact entries")
    return ManifestVerification(not failures, checked, tuple(failures))
