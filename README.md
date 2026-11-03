> **Federation index:** [FEDERATION_INDEX.md](https://github.com/Zygros/conzet-sovereign-intelligence/blob/main/FEDERATION_INDEX.md)

# OMEGA-10 v0.1: Evidence Substrate

**Status banner:** OMEGA-10 v0.1: implementation and local test evidence; not independently reproduced.

Current tracked implementation: canonical JSON serialization, SHA-256 utilities, and a deterministic local Phoenix recovery benchmark with snapshot restoration, an append-only hash-chained event receipt, and a machine-readable result manifest. The shared core ledger/manifest/signing modules, Master Codex, red-team fixtures, HTC chamber, and demo modules are declared by package stubs or Makefile targets but are not present in the current tracked source tree; treat those capabilities as not implemented until their modules and tests are added.

## Quick start

```bash
make bootstrap
make test
make phoenix
```

## Not-yet-implemented targets

`make redteam`, `make htc`, and `make demo` remain placeholders until their referenced modules are present and tested. The current package initializer exports only source files that exist.

## Evidence discipline

- Every ledger mutation that breaks the chain fails verification.
- Codex entries start at DESIGNED unless executable evidence is linked.
- HTC never enables network or deployment by default.
- No production or independent-reproduction claims without artifacts.

## Related (Federation)

- **Map of all repos:** https://github.com/Zygros/sovereign-federation
- Outsider audit & plain catalog: https://github.com/Zygros/sovereign-federation/tree/main/docs
- Phoenix meta-archive: https://github.com/Zygros/PHOENIX-PROTOCOL-ULTIMATE
- Multi-AI bridge: https://github.com/Zygros/multi-ai-convergence-protocol

## License

MIT
