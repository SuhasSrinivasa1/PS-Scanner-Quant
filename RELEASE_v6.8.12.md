# PS Scanner Quant v6.8.12 — Bounded Global→India & Passive Support Delivery

v6.8.12 is a narrow runtime-completion release based on the real-Mac v6.8.11 acceptance run.

## Real-Mac evidence from v6.8.11

The v6.8.11 upgrade itself succeeded:
- 333 local tests passed.
- history-summary, institutional, adaptive-algorithm, Performance and International caches primed successfully.
- Groww explicit verification returned CONNECTED.
- the application started as v6.8.11 with runtime data and the recommendation ledger preserved.

The health architecture remained healthy under the acceptance stress run: all eight requests stayed passive with zero request-path DB connections, subsystem refreshes and filesystem reads.

Two genuine runtime issues remained:
1. Global→India entered DETAIL_ENRICHMENT after evaluating all 3,390 NSE equity summaries but produced 2,286 detailed candidates. The worker exceeded its existing 600-second watchdog and the validator correctly reported it as hung.
2. Support-bundle compression reduced about 401.8 MB of retained content to about 47.1 MB, but the live background refresh itself took about 561 seconds. Because the worker cadence is five minutes, a cycle longer than its interval can restart almost immediately. During that live contention the explicit 10-second localhost download transferred only about 10.6 MB of the 47.1 MB archive.

Neither failure is addressed by increasing validator or HTTP timeouts.

## v6.8.12 changes

### Exact full-breadth Global→India work is bounded and resumable

The full NSE summary pass remains unconditional. There is no liquidity, market-cap or Top-N universe cap.

The detailed stage now:
- runs under an explicit per-cycle wall-clock budget below the worker watchdog;
- persists its in-process work cursor across worker cycles;
- orders detailed work by a mathematically conservative maximum possible final score;
- only skips a detailed candidate after that candidate can no longer enter the exact top result set for its side;
- never publishes or freezes a partial board;
- resumes the same full-breadth job on the next cycle when the budget expires.

The compact daily-history summary now follows the same H/L/C validity, timestamp coercion, sorting and duplicate-last rules as the authoritative candle parser. Therefore the close-only ret20/trend used by the pruning bound are derived from the same close sequence used by the detailed feature path.

### Support export is preloaded in memory and rebuilds are coalesced

The complete sanitized archive is still built and compressed off the HTTP request path.

After a successful build, the completed compressed bytes are loaded into memory. Startup restores the last complete archive into memory before HTTP service is considered ready. Export All Logs serves this immutable prebuilt memory snapshot, so clicking it performs:
- no database query;
- no log redaction;
- no ZIP construction or compression;
- no filesystem read.

The recurring support worker also skips rebuilding a still-fresh complete bundle. This prevents a long compression pass from immediately starting again merely because it exceeded the nominal worker interval.

The installer forces exactly one fresh support-bundle build while the previous service is stopped, preserving current-release diagnostics without introducing live contention.

## Unchanged contracts

No scanner cadence, full-NSE breadth, recommendation threshold, target/stop geometry, point-in-time evidence rule, institutional-evidence rule, frozen identity, append-only rule, Static-IP scope, Groww pacing, broker reconciliation, manual notional cap, stop-risk cap, minimum reward/risk, Indian SHORT hard exit or Champion/Challenger promotion rule changes in v6.8.12.
