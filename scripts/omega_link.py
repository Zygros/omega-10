#!/usr/bin/env python3
"""Append a SHA-256 artifact receipt to a local evidence ledger.

Run from the target repository root:
  python3 scripts/omega_link.py <artifact-path> "<claim>"

This records a commit and artifact digest. It does not itself run tests, prove the
claim, or create a cryptographically hash-chained ledger.
"""
import datetime
import hashlib
import json
import pathlib
import subprocess
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from omega.phoenix.receipts import verify_artifact_receipt


def git_head():
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.PIPE
    ).strip()

def artifact_hash(path):
    return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()

def link(artifact_path, claim, repo="omega-10"):
    repo_root = pathlib.Path.cwd().resolve()
    artifact = pathlib.Path(artifact_path)
    if not artifact.is_absolute():
        artifact = repo_root / artifact
    artifact = artifact.resolve(strict=True)
    if not artifact.is_file():
        raise FileNotFoundError(f"Artifact does not exist: {artifact}")
    try:
        relative_artifact = artifact.relative_to(repo_root).as_posix()
    except ValueError as exc:
        raise ValueError("artifact must be inside the current repository root") from exc
    entry = {
        "repo": repo,
        "claim": claim,
        "commit": git_head(),
        "artifact": relative_artifact,
        "artifact_sha256": artifact_hash(artifact),
        "linked_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "status": "TESTED_PENDING_REVIEW",
        "independently_reproduced": False,
    }
    verification = verify_artifact_receipt(entry, repo_root)
    if not verification.valid:
        raise ValueError(f"receipt verification failed: {verification.reason}")
    ledger = pathlib.Path("EVIDENCE_LEDGER.jsonl")
    with ledger.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, sort_keys=True) + "\n")
    print(json.dumps(entry, indent=2))
    print(f"Appended receipt to {ledger}.")
    print("This records provenance; it does not automatically establish that the claim passed a test.")
    print("Independent reproduction is still required for VERIFIED status.")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print('usage: omega_link.py <artifact> "<claim>"', file=sys.stderr)
        sys.exit(2)
    try:
        link(sys.argv[1], sys.argv[2])
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)
