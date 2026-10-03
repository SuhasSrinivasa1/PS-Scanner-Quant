# Architecture Audit v6.8.3 — installer acceptance gate

v6.8.3 does not change trading architecture or research semantics. It corrects only the installer acceptance contract.

## Confirmed invariants

- Static IP remains order-execution only.
- Research and recommendation generation do not require Static IP.
- Groww position reconciliation remains fail-closed.
- ₹20,000 maximum manual notional and ₹500 modeled stop-risk cap remain unchanged.
- Minimum reward/risk remains 1.5.
- Frozen Weekly/Monthly identity, no rank replacement, and no quota fabrication remain unchanged.
- v6.8.1 bounded performance analytics and covering-index fix remain unchanged.
- v6.8.2 execution-critical health snapshot ordering/indexes remain unchanged.
- Point-in-time evidence, VOID handling, and Champion/Challenger promotion controls remain unchanged.

## Installer finding

The only defect was a stale literal runtime-version comparison inside the post-launch installer health checks. The new contract derives expected version from the installed source and applies it consistently to both service-health and final Groww-connected acceptance checks.

Rollback-on-failure remains enabled.
