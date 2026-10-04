# PS Scanner Quant v6.8.9 — Final Product Integration Pass

v6.8.9 is the final product-direction pass requested after the successful v6.8.8 real-Mac install.

## What the v6.8.8 Mac evidence proved

v6.8.8 installed successfully on the real Mac with 311 tests passing, Groww connected, the preserved ledger intact, history summaries backfilled, the institutional compact summary READY, and the passive algorithm cache primed.

The validator completed successfully. Algorithm status was effectively instantaneous and passive. Performance scanned all 196 CLOSED rows using the covering index and completed. A later health request made while market_snapshot and Global->India were both processing full-breadth summaries still experienced optional DB snapshot interruption. That last overlap showed that duplicated background summary work, not the algorithm or performance query itself, remained the final passive-health contention source.

## Runtime/health architecture

- `/api/health` is now DB-free on the request path.
- A dedicated background health-snapshot worker refreshes the execution-critical daily order count, selected system state, health-event summary, recommendation counts, decision counts, fundamental summary and event summary.
- HTTP health consumes only the last complete background snapshot.
- A stale (>20 seconds) health snapshot fails execution closed instead of trusting an old daily order count.
- The full-NSE `history_summaries` observation now has a 30-second shared in-memory cache so market/regime/sector/Global->India workers do not repeatedly decode the same 3k+ symbol SQLite observation within one burst.
- No passive timeout is increased.

## One-click Export All Logs

The website now exposes a common **Export All Logs** button and a second copy on System Health.

The generated ZIP contains:
- all retained files under the application's `logs/` directory;
- health-event audit rows;
- scan-run audit rows;
- trade-decision journal rows;
- recommendation ledger rows;
- strategy-validation rows;
- algorithm-version rows;
- institutional snapshot rows;
- sanitized system-state rows;
- a manifest with software version and export timestamp.

Credentials and settings are not included. Known credential values are redacted from raw service-log text and secret-named structured fields are redacted from database exports.

## Indicators and strategies working in tandem

v6.8.9 adds an explicit book-specific evidence-combination contract without inventing a new unvalidated score.

Examples:
- **Intraday**: fresh trend/VWAP, relative volume and liquidity are primary; institutional/accumulation, candles, news/events and sector breadth confirm.
- **Circuit**: fresh price/volume, verified band/order imbalance and deadline capacity are primary; institutional activity, candles, catalyst evidence and execution permission confirm.
- **Weekly**: daily trend/momentum, target-capacity geometry and NIFTY relative strength are primary; institutional history, sector leadership, news/events and candles confirm.
- **Monthly**: fundamentals, long-horizon trend and target-capacity are primary; institutional ownership/history, sector breadth, news/events and cash-flow quality confirm.
- **Global->India**: cross-asset driver, Indian daily confirmation and industry mapping are primary; institutional/accumulation, sector breadth and news/events confirm.

Industry-aware dependency context now surfaces relevant oil, natural gas, gold, silver, copper, USDINR, DXY and mapped global-sector observations when available.

Institutional activity is **never a standalone trigger**. The combination label is visible/auditable and may gate later append discoveries, but it does not silently replace the existing validated intelligence weights. Any future promotion of a new interaction into the main score still requires incremental out-of-sample evidence.

## Recommendation ownership and append-only lifecycle

For Weekly, Monthly, ETF and International:
- the initial slate is an immutable `INITIAL_FREEZE`;
- the preferred deadline is Monday 09:00 IST for weekly books and 09:00 IST on the first NSE trading day for Monthly;
- missed freezes retain deterministic recovery without gate relaxation;
- earlier recommendations are never deleted, recycled, rank-replaced or cosmetically backfilled;
- later high-conviction discoveries may be added as `APPEND_DISCOVERY`;
- append candidates require the original target/risk/intelligence gates, a higher score threshold and CONFIRMED/STRONG tandem evidence;
- appends are bounded per day and per period;
- every recommendation remains in the ledger and every valid resolved outcome feeds learning.

This implements “own every recommendation”: a loss is not erased, a win is not replaced, and a later discovery does not rewrite the original slate.

## Global -> India

Global->India is now a weekly prediction ledger keyed by NSE Monday:
- initial slate target: Monday 09:00 IST;
- later stronger candidates append only;
- prediction identities remain auditable through the week;
- bullish weekly calls may remain delivery research;
- bearish weekly calls are research-only for execution purposes.

The Indian SHORT safety invariant is unchanged: an actual Indian short must originate from a same-day MIS lane and hard-exit by 15:00 IST. Direct order previews from `GLOBAL_INDIA_SHORT` are blocked in both UI and backend.

## Unchanged safety/integrity contracts

- full NSE breadth;
- no arbitrary Top-N universe cap;
- no quota fabrication;
- no rank replacement;
- point-in-time evidence;
- WAL SQLite with no process-wide Python DB lock;
- Static IP gates order execution only;
- Groww reconciliation remains fail-closed;
- ₹20,000 maximum manual notional;
- ₹500 modeled risk-to-stop cap;
- minimum R/R 1.5;
- VOID excluded from trading-performance denominator;
- Champion/Challenger promotion remains evidence-gated.
