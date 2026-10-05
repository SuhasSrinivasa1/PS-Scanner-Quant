# PS Scanner Quant v6.8.14 — Tomorrow Readiness

## Purpose

v6.8.14 hardens the recovered production runtime for the next trading session without relaxing recommendation, learning, risk or execution gates.

## History hydration and Groww backoff

- Background daily/intraday/bootstrap hydration no longer retries the same 429 repeatedly.
- Background warmers yield immediately while the central Groww historical-data cooldown is active.
- The inter-request gap expands after consecutive 429s and decays only through successful requests.
- Default historical-data spacing is increased to 2.0 seconds.
- A symbol/interval returning HTTP 403 while the broker is otherwise CONNECTED is quarantined for a bounded interval instead of retried every cycle.
- Full NSE breadth is preserved. These changes alter pacing, not the research universe.

## Regime integrity during recovery

A market regime is no longer classified from a tiny post-recovery history sample.

- Until at least 5% of the NSE universe is history-ready, with a minimum of 50 and maximum requirement of 250 symbols, regime state is WARMING.
- Sparse-sample telemetry remains visible, including sample size, coverage percentage and minimum required sample.
- No fabricated RANGE/TREND state is produced from recovery fragments.

## Fundamentals noise control

Expected Yahoo unsupported-symbol results now persist in SQLite as a short-lived negative cache.

- The negative cache survives service restarts.
- Unsupported/404 symbols are not repeatedly treated as fresh warning events during every worker cycle.
- Missing fundamentals remain UNKNOWN; they are not converted into positive evidence.

## Recovery position reconciliation

v6.8.14 adds an explicit, localhost-only recovery baseline for external CNC session positions.

- Nothing is automatically acknowledged.
- Only CNC residual positions can be baselined.
- MIS or other non-CNC mismatches cannot be baselined.
- The baseline expires with the trading day.
- Any later broker quantity change becomes a hard mismatch again.
- No PS Scanner orders or fills are fabricated.

## Build provenance

CI now writes the exact Git commit into BUILD_COMMIT inside every installable package.

- /api/ping and /api/health expose the packaged build commit.
- The value is loaded once at process startup so passive health remains filesystem-free.

## Unchanged production invariants

- Full NSE equity-share breadth; no top-N universe cap.
- Static IP remains an execution-only control and is not changed by this release.
- Research remains independent of execution readiness.
- Maximum manual order notional remains ₹20,000.
- Maximum modeled rupee loss to stop remains ₹500.
- Minimum reward/risk policy remains unchanged.
- Weekly / Monthly / ETF executable sides remain LONG-only.
- Frozen recommendation identities remain immutable.
- No forced recommendation quota and no hindsight replacement.
- Challenger promotion remains OOS/holdout/cost/stability/multiple-testing/live-shadow evidence-gated.
