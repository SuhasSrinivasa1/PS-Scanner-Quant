# PS Scanner Quant v6.8.17 — Website Worker Health Reliability

## Production issue

During the live NSE session, the Production Command Center intermittently showed:

`ENGINE · ATTENTION · hung: daily_history`

The v6.8.16 health model could distinguish progress-aware scanner workers such as Weekly and Circuit, but the background daily-history producer was not mapped into that heartbeat fabric. With the installed 64-symbol warm batch, a legitimate paced cycle can run longer than the inherited 360-second runtime threshold. Once it crossed that threshold, the absence of a daily-history heartbeat made the UI and validator classify it as hung even when it was still advancing and later completed successfully.

## v6.8.17 fix

- Daily-history hydration emits an in-memory heartbeat at prepare, fetch, per-symbol completion, rate-limit deferral, and completion stages.
- The passive health endpoint maps `daily_history` to that heartbeat without adding request-path SQLite, filesystem, or network work.
- `runtime_over_threshold` remains visible, but `hung=true` requires stale forward progress beyond the existing stall grace.
- Each worker exposes stage, processed/remaining counts, current item, progress age, and progress detail.
- The web command center shows:
  - ONLINE when workers are healthy;
  - BUSY in amber for long-running workers that are still advancing;
  - ATTENTION in red only for dead or genuinely stalled workers.
- The System Health page renders a worker table instead of requiring users to interpret raw JSON.
- Support export status exposes generated age and incident-capture freshness. The UI warns before downloading a prebuilt bundle older than 15 minutes.
- The support ZIP response includes generated-at and age headers.

## Unchanged invariants

No changes are made to recommendation generation, target gates, portfolio correlation gates, NSE breadth, Groww pacing/backoff, frozen recommendation identities, append-only recovery, Static-IP execution-only scope, broker reconciliation, ₹20,000 maximum notional, ₹500 modeled stop-risk cap, R/R requirements, or Champion/Challenger evidence governance.
