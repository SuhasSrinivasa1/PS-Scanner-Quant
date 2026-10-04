# PS Scanner Quant v6.8.6 — Persisted History Summary Runtime Hardening

v6.8.6 is a production-runtime reliability and evidence-correctness patch on top of v6.8.5.

The real Mac v6.8.5 upgrade itself succeeded: all 290 local tests passed, Groww authentication remained connected, the new institutional producer was READY, database restore verification passed, and the post-install validator returned `ok=true`. The v6.8.4 watchdog correction also held: `market_snapshot` was actively progressing through `BREADTH_DISCOVERY` and was not marked hung.

A direct passive performance request during the same startup workload still reached its 2.5-second fail-closed budget after loading only 81 CLOSED rows. That exposed a remaining CPU/decode contention path that v6.8.4 had not removed.

## Root cause

The full-market worker still did redundant historical-cache work:

1. `full_breadth_discovery_snapshot` parsed the daily and 5-minute JSON cache for every NSE equity.
2. `regime.classify` then parsed the daily cache for every NSE equity again.
3. sector breadth separately reconstructed Pandas/features from cached daily history.

On the production universe of 3,390 equities, this repeated JSON/Pandas work could consume substantial Python CPU/GIL time during startup even though the passive performance SQL itself was already indexed and narrow.

## Fix: compact persisted history summaries

v6.8.6 adds an additive SQLite `history_summaries` table keyed by symbol and interval. It stores only what broad-market consumers need:

- cached row count;
- recent daily closes (up to 60);
- cache mtime;
- update timestamp.

Detailed JSON candle caches remain authoritative for scanners, point-in-time replay, feature generation, backtests and learning.

The installer backfills this index from existing local history files **while the service is stopped**, before LaunchAgent startup. New history writes update the summary automatically.

The market-snapshot worker then performs one compact summary read and shares it between:

- full-NSE breadth/readiness;
- market regime classification.

Sector breadth also consumes the compact summary rather than rebuilding full DataFrames for its small breadth feature set.

This does not introduce a Top-N research universe, reduce scanner cadence, or skip any NSE equity from breadth evaluation.

## Large-deal price correctness

The real v6.8.5 institutional response showed NSE large-deal rows with the disclosed weighted-average trade price under `watp`, while the normalized record emitted `price: 0.0` and `value_rupees: null`.

v6.8.6 accepts NSE `watp` / `WATP` / weighted-average-price aliases in addition to existing price fields. Direct bulk/block deal value-weighted evidence therefore retains the disclosed price instead of silently collapsing to zero.

## Sector snapshot continuity

The last complete sector breadth snapshot is persisted and restored during supervisor bootstrap. Passive health still performs no network calls and does not trigger a sector rebuild.

## Preserved contracts

Unchanged:

- full NSE equity-share breadth;
- v6.8.4 hard aggregate LTP wall-clock budget;
- passive performance 2.5-second fail-closed budget;
- passive health one bounded DB snapshot / no network;
- Static IP is order-execution only;
- Groww position reconciliation is fail-closed;
- ₹20,000 maximum manual notional;
- ₹500 modeled stop-risk cap;
- minimum R/R 1.5;
- same-day Indian SHORT hard exit;
- frozen Weekly/Monthly identity;
- no rank replacement or quota fabrication;
- VOID exclusion from trading-performance denominators;
- Champion/Challenger evidence gates;
- v6.8.5 delivery/disclosure/derivatives evidence remains shadow-only until incremental OOS validation.

## Regression coverage

v6.8.6 verifies that:

- the additive history-summary schema exists;
- full-breadth evaluation no longer reparses candle files;
- regime consumes the same summary snapshot;
- sector breadth uses compact summary features;
- market snapshot shares one summary read across breadth and regime;
- NSE WATP is normalized into direct large-deal value;
- the installer backfills summaries before LaunchAgent startup.

## Canonical repository

Canonical source: `SuhasSrinivasa1/PS-Scanner-Quant`.
