# PS Scanner Quant v6.8.15 — Web UI Reliability

v6.8.15 is a narrow website/runtime-observability release. It does not change scanner gates, risk limits, recommendation thresholds, execution rules, Static IP policy, frozen-book semantics, or learning/promotion policy.

## Runtime evidence

The v6.8.14 support bundle showed the application APIs returning successfully, but the browser command center repeatedly requested passive integrity and algorithm views at the same cadence as lightweight health polling. That made the browser a needless source of SQLite/CPU work while a tab remained open. Safari also generated repeated 404 requests for browser icons.

## Changes

- Keep lightweight `/api/health` refreshes at 15 seconds.
- Refresh bounded `/api/sanity` and passive `/api/algorithm` telemetry no more than once per minute during normal dashboard polling.
- Pause background health/book polling while the browser tab is hidden; refresh immediately when it becomes visible again.
- Prevent overlapping health, telemetry, and book refreshes.
- Add per-request browser timeouts with a visible connection banner instead of silent blank/stale views.
- Report worker state as WARMING when the worker snapshot is empty instead of incorrectly displaying ONLINE.
- Use the actual health-snapshot age in the command center.
- Treat a configured-but-not-yet-probed Groww cache as VERIFYING rather than an authentication failure.
- Serve favicon and Apple touch-icon requests so Safari no longer emits repeated 404s.
- Preserve no-store behavior for the live HTML and API views.

## Unchanged production contracts

- FULL NSE BREADTH; no top-N universe cap.
- Research remains independent of Static IP.
- Static IP remains order-execution only.
- Manual maximum notional remains ₹20,000.
- Maximum modeled rupee risk to stop remains ₹500.
- Minimum RR remains 1.5.
- Indian multi-session execution remains LONG-only; bearish horizon signals remain research-only.
- Frozen identities, point-in-time evidence, WAL/concurrency, and evidence-gated learning remain unchanged.
