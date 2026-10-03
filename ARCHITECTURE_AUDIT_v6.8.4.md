# Architecture Audit v6.8.4 — bounded full-breadth runtime contention

v6.8.4 addresses production runtime contention without narrowing the research universe or loosening any trading control.

## Confirmed production evidence

The v6.8.3 Mac runtime reached the correct version and engine state with Groww connected and execution reconciliation verified. Under sustained background load, passive health exceeded the client deadline, bounded performance degraded before completing the small CLOSED-row set, and `market_snapshot` exceeded its watchdog threshold.

## Architectural findings

### Full-NSE quote transport

The broker LTP implementation split the full NSE universe into 50-symbol batches but only bounded each individual request. A full sweep therefore had no aggregate deadline. The worker timeout was observational only and could not cancel a still-running network loop.

v6.8.4 adds an aggregate wall-clock deadline and preserves completed quote batches on timeout. Research remains fail-soft on partial market snapshots; execution remains independently fail-closed.

### Cache warmers

The 90-second history warmers performed O(N) JSON reparsing over the whole NSE cache to decide which small batch to hydrate. That was redundant with the dedicated full-breadth discovery producer and could contend with SQLite/Python work needed by passive APIs.

v6.8.4 changes only enrichment scheduling: bounded rotating pools cover the same full universe over time while active/new/mover priorities remain first. No symbol is excluded from research by rank, market cap, or liquidity.

### Startup phase separation

Heavy cache warmers are phase-shifted away from the initial full-market snapshot. Their recurring cadences are unchanged.

### Observability

The market-snapshot worker now reports its active internal stage so future stalls can be localized without guessing.

## Unchanged invariants

- Full NSE equity-share discovery remains authoritative and uncapped.
- Static IP remains `ORDER_EXECUTION_ONLY`.
- Broker reconciliation remains fail-closed.
- Manual notional/risk caps remain ₹20,000 / ₹500.
- Minimum reward/risk remains 1.5.
- Indian multi-session executable books remain LONG-only.
- Frozen Weekly/Monthly identity remains enforced by application and SQLite interlocks.
- No rank replacement, quota fabrication, or historical backfill is introduced.
- Point-in-time evidence and Champion/Challenger governance are unchanged.
- Passive `/api/health`, `/api/sanity`, and `/api/performance` remain network-free and bounded.
- Performance degradation remains explicit and never publishes partial statistics as complete.
