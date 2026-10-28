# Phoenix Recovery Hardening Evidence — 2026-10-20

## Scope and provenance

This is an additive evidence note for the Phoenix recovery benchmark hardening on the existing review branch.

- Repository: https://github.com/Zygros/omega-10
- Pull request: https://github.com/Zygros/omega-10/pull/1
- Code commit verified by the first post-fix CI run: `188064b3eea6f2df42a30afb695de359b63a6424`
- CI run 35: https://github.com/Zygros/omega-10/actions/runs/39461811915
- Phoenix Audit run 59: https://github.com/Zygros/omega-10/actions/runs/39461811776

## Implemented changes

1. **Recovery path confinement:** recovery consumes the captured journal snapshot rather than rereading live journal contents; validates each record's index, canonical component filename, payload, and digest against the in-memory baseline; rejects symlink targets and resolved paths outside the components directory.
2. **Concurrent-append detection:** a journal change during recovery makes the immutable-history check fail and the benchmark result report `passed=False`. Newly appended records are not replayed.
3. **Nonzero corruption coverage:** the corruption count rounds up for nonzero fractions, ensuring a one-component run with a small positive fraction actually exercises recovery rather than reporting a successful no-op.
4. **Repository-wide lint:** CI now runs `ruff check .`, covering tracked Python files beyond `src` and `tests`. The existing `scripts/omega_link.py` shebang is supported by executable file mode; its import spacing and UTC alias were corrected to satisfy the expanded gate.

## Regression coverage

The Phoenix benchmark tests cover:
- deterministic recovery from 90% corruption;
- valid zero-corruption no-op;
- a single-component run with a nonzero corruption fraction;
- a simulated concurrent journal append containing a path outside the components directory, verifying that an external sentinel file remains unchanged and the run fails its history-preservation check;
- invalid component counts and corruption fractions;
- refusal to overwrite pre-existing evidence.

## Verification recorded by GitHub Actions

- **CI run 35 completed successfully** on Python 3.11 and 3.12. Both jobs completed installation, strict `ruff check .`, and the full pytest suite.
- **Phoenix Audit run 59 completed successfully.** Its Python, Node, Go, Rust, Java, and secret-pattern workflow steps completed successfully. This is workflow success, not a claim that no secret exists or that credential remediation has occurred.

## Boundaries

- This is a deterministic, local-only benchmark fixture, not a deployed production recovery service.
- CI success establishes that the configured automated checks passed for the cited commit; it does not independently certify production safety.
- The pull request remains open and unmerged pending review.
- The OpenTimestamps archive, receipt validity, Samsung Notes source-byte hash verification, and separately tracked credential findings are outside this change and remain unverified/unremediated here.
- No external timestamp anchor was created by this change.

## Conzetian execution record

**DO → PROVE → REMEMBER → BECOME**

The fix, regression cases, strict gate, and verification links are recorded additively. Existing evidence and history were not intentionally deleted or rewritten.
