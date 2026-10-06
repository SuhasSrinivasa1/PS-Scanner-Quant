# PS Scanner Quant v6.8.15 — ETF Hydration, Funnel Truthfulness & Frozen Status Consistency

## Purpose

v6.8.15 fixes the production-readiness gap found in the v6.8.14 support bundle: the ETF instrument universe was discovered, but ETF daily-history caches were never populated because ETFs are intentionally excluded from the stock universe and the existing ETF warmer was not scheduled.

The release also makes the website distinguish a real zero from missing/unreported scanner telemetry, and preserves truthful CIRCUIT_NEXTDAY publication state after the freeze window closes.

## ETF history readiness

- A dedicated ETF daily-history producer now runs independently in the scheduler.
- ETF history requests use the same central Groww pacer, provider cooldown and background/no-repeat-429 contract as stock hydration.
- ETF scanning remains cache-only and never blocks the request path on network calls.
- ETF symbols remain separate from the full NSE stock universe.
- The ETF scanner now reports standardized funnel telemetry: universe total, scan scope, processed, history-ready, raw eligible, publication-ready and published.
- When ETF instruments exist but none has cached history yet, status is ETF_HISTORY_WARMING rather than pretending there was a completed zero-opportunity scan.
- Regression coverage now writes a real cache at the production canonical ETF history path and proves the production scanner resolves it as history-ready without mocking the history path or cache reader.

## CIRCUIT_NEXTDAY frozen-status consistency

The production contradiction was caused by a later no-op cycle, not by missing recommendations. The cycle created a fresh status payload with published=0 and returned FREEZE_WINDOW_CLOSED after 15:30 before consulting the persisted target-session slate.

The worker now reads the persisted non-VOID target-session recommendations first. If a frozen slate already exists it reports ALREADY_FROZEN with the truthful persisted publication count, shortage/recovery fields and a separate window_status. It does not delete, replace, backfill or republish the existing frozen identities.

A regression test seeds five persisted LIVE CIRCUIT_NEXTDAY recommendations, executes the real after-close cycle, and proves that status remains published=5 while the five database rows remain unchanged.

## Website funnel semantics

- An explicit backend zero is displayed as 0.
- Missing/unreported telemetry is displayed as —.
- The Research Funnel shows the actual scanner status and explains the distinction.
- No recommendation is invented to make the counters non-zero.

## Operational diagnostics

- /api/scan/status remains canonical.
- /api/scans/status is retained as a compatibility alias for operational scripts.

## Market-snapshot latency audit

No timeout increase or speculative locking/concurrency change is introduced. Current main already uses the compact persisted history_summaries snapshot with a short SQLite busy timeout and in-memory reuse during market_snapshot/HISTORY_SUMMARY instead of reparsing full candle caches. The previously observed worker recovered without a restart, so the evidence does not justify another latency code change in this patch.

## Unchanged production invariants

- Full NSE equity-share breadth; no top-N cap.
- Static IP remains execution-only.
- Research remains independent of execution readiness.
- Maximum manual order notional remains ₹20,000.
- Maximum modeled rupee loss to stop remains ₹500.
- Weekly / Monthly / ETF executable sides remain LONG-only.
- No forced recommendation quota.
- Frozen identities remain immutable and no hindsight replacement is introduced.
- History requests remain centrally paced and fail-soft under Groww rate limits.
