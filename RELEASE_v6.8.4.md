# PS Scanner Quant v6.8.4

v6.8.4 is a narrow runtime-contention reliability patch on top of v6.8.3. It does not change trading thresholds, recommendation gates, full-NSE research breadth, frozen-book identity, evidence semantics, risk sizing, broker reconciliation, or Static-IP scope.

## Production finding

The real Mac v6.8.3 install succeeded and the service reported the correct runtime version, a live engine, connected Groww authentication, a valid execution-critical health snapshot, and verified position reconciliation. Post-install validation then exposed a separate runtime-load defect:

- `/api/health` could exceed a 10-second client deadline;
- `/api/performance?group_by=book&limit=1000` returned truthful `DEGRADED_BOUNDED` telemetry after loading only a small prefix of rows;
- the supervisor reported `market_snapshot` as hung.

The failure was reproducible after the initial startup burst, so it was not treated as a validator-only timing problem.

## Root causes

1. Full-NSE LTP refresh batches up to 50 symbols per Groww request. At the current ~3.4k NSE equity universe this is roughly 68 sequential requests. Each request had its own timeout, but the complete sweep had no total wall-clock deadline. A degraded network/broker path could therefore keep the market-snapshot worker alive far beyond its intended runtime.
2. The recurring daily and intraday history warmers repeatedly reparsed thousands of cached JSON files every 90 seconds merely to rebuild missing/readiness and activity-priority lists. This duplicated work already owned by the full-breadth discovery snapshot and created unnecessary CPU/disk contention with passive health/performance requests.
3. Heavy warmers began within seconds of the first market snapshot, amplifying startup contention.
4. Worker telemetry exposed only `RUNNING`, not the internal market-snapshot stage, making LTP vs breadth vs regime stalls indistinguishable.

## Fix

- Groww full-NSE LTP batching now has a hard overall wall-clock budget with partial-success semantics. Per-request timeouts remain bounded; when the global deadline is reached, the completed quote subset is kept and telemetry reports `budget_exhausted`.
- Daily/intraday history warmers now inspect bounded rotating priority pools instead of reparsing the entire NSE cache on every short cadence. Active recommendations, newly listed names, cached movers, and rotating full-universe coverage remain prioritized.
- The full NSE universe remains unchanged: rotation eventually reaches every symbol and no top-N research cap is introduced.
- Daily warmer readiness reuses the dedicated current full-breadth snapshot when available rather than launching a second full-universe cache scan.
- Maintenance and daily-history warmers retain their existing recurring intervals but start at staggered phases after service launch.
- `market_snapshot` now exposes internal stages: `UNIVERSE`, `LTP_REFRESH`, `BREADTH_DISCOVERY`, `REGIME_CLASSIFICATION`, and `PUBLISH`.
- Passive performance analytics remain fail-closed and bounded; no timeout is inflated and partial statistics are still never presented as complete.

## Regression coverage

v6.8.4 adds tests that verify:

- the full-NSE LTP sweep terminates on its global wall-clock budget and reports partial success;
- recurring history warmers use bounded rotation rather than full-cache reparsing;
- market-snapshot stage telemetry is exposed;
- heavy startup warmers are staggered;
- the current runtime version is 6.8.4.

## Safety invariants

Unchanged:
- Static IP is order-execution only;
- Groww position reconciliation remains fail-closed;
- ₹20,000 maximum manual-order notional;
- ₹500 modeled stop-risk cap;
- minimum reward/risk 1.5;
- same-day Indian SHORT hard exit at 15:00 IST;
- Weekly/Monthly frozen identity and no rank replacement/backfill fabrication;
- VOID exclusion from trading-performance denominators;
- Champion/Challenger promotion remains evidence-gated;
- passive health/performance paths make no broker/network calls.

## Canonical repository

Canonical source: `SuhasSrinivasa1/PS-Scanner-Quant`.
