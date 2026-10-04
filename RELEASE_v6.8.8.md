# PS Scanner Quant v6.8.8 — Global-to-India Runtime Fairness

v6.8.8 addresses the remaining real-Mac passive-endpoint contention observed after the v6.8.7 algorithm-cache fix.

## Real-Mac evidence

v6.8.7 installed successfully. The ZIP checksum and archive integrity passed, Python 3.12.13 was selected, 306 local tests passed, the history-summary backfill indexed 4,905 files, the compact institutional summary was backfilled READY, the adaptive-algorithm cache was primed READY, Groww remained CONNECTED, and the service started as 6.8.7.

The v6.8.7 algorithm fix worked in production: `/api/algorithm` returned in about 0.67 seconds with `cache_ready=true`, `passive_cached=true`, `network_calls=false`, and `deep_institutional_payload=false`.

The production gate still failed elsewhere: performance reached its unchanged 2.5-second fail-closed budget after only 30 CLOSED rows, while health retained execution-critical state but its optional database snapshot was interrupted around 3.5 seconds. At that same point `market_snapshot` was IDLE and not hung.

## Root cause

The remaining full-breadth CPU path was the Global->India worker. Every five minutes, including weekends, it parsed detailed daily candle JSON into pandas DataFrames and recomputed the full feature set for every NSE equity before checking whether the symbol even had a plausible global-driver alignment.

That work was independent of `market_snapshot`, so the market-snapshot watchdog could be healthy while the process was still spending sustained CPU/GIL time in another background worker.

## Fix

The Global->India worker now uses the v6.8.6 compact history-summary index as a first-pass necessary-condition filter over the complete NSE equity universe.

Every symbol is still evaluated. There is no Top-N cap.

For each symbol the summary pass derives the exact close-only fields needed by the existing score formula: last close, 20-session return, SMA20/SMA50 trend, and global-driver alignment. A symbol is discarded only when it cannot mathematically reach the unchanged score threshold even after granting the maximum possible ADX contribution.

All survivors are then processed with the original detailed history, pandas features, fundamentals, institutional evidence, trade-intelligence gates, target geometry and publication rules.

The worker also yields cooperatively during long loops and publishes summary-vs-detail runtime telemetry.

## Unchanged contracts

No passive timeout was increased. No scanner threshold, target gate, risk rule, Static-IP scope, frozen identity, evidence gate, recommendation quota, or research universe rule was weakened.

Full NSE breadth remains mandatory.
