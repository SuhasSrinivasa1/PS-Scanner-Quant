# PS Scanner Quant v6.8.15 — ETF Hydration & Funnel Truthfulness

## Purpose

v6.8.15 fixes a production-readiness gap found in the v6.8.14 support bundle: the ETF instrument universe was discovered, but ETF daily-history caches were never populated because ETFs are intentionally excluded from the stock universe and the existing ETF warmer was not scheduled.

The release also makes the website distinguish a real zero from missing/unreported scanner telemetry.

## ETF history readiness

- A dedicated ETF daily-history producer now runs independently in the scheduler.
- ETF history requests use the same central Groww pacer, provider cooldown and background/no-repeat-429 contract as stock hydration.
- ETF scanning remains cache-only and never blocks the request path on network calls.
- ETF symbols remain separate from the full NSE stock universe.
- The ETF scanner now reports standardized funnel telemetry: universe total, scan scope, processed, history-ready, raw eligible, publication-ready and published.
- When ETF instruments exist but none has cached history yet, status is ETF_HISTORY_WARMING rather than pretending there was a completed zero-opportunity scan.

## Website funnel semantics

- An explicit backend zero is displayed as 0.
- Missing/unreported telemetry is displayed as —.
- The Research Funnel shows the actual scanner status and explains the distinction.
- No recommendation is invented to make the counters non-zero.

## Operational diagnostics

- /api/scan/status remains canonical.
- /api/scans/status is retained as a compatibility alias for operational scripts.

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
