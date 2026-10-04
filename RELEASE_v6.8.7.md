# PS Scanner Quant v6.8.7 — Passive Adaptive-Algorithm Cache

v6.8.7 is a passive-API reliability patch on top of v6.8.6.

## Real-Mac evidence

The v6.8.6 upgrade itself succeeded. The installable ZIP matched its published SHA-256, archive integrity passed, Python 3.12.13 was selected, 298 local tests passed, Groww remained CONNECTED, the history-summary migration indexed 4,869 existing cache files, and the service started as version 6.8.6.

v6.8.6 also fixed the intended data issues:

- full-NSE breadth was CURRENT across 3,390 equities;
- market_snapshot was IDLE/not hung at the sampled validation point;
- sector breadth later reported 20 ready industries;
- institutional status was READY with no producer errors;
- 163 large-deal rows carried a usable normalized price;
- delivery evidence covered 3,262 securities;
- priority F&O positioning completed without exhausting its hard wall-clock budget.

The remaining production failure was independent of those fixes:

- post-install validation timed out on `GET /api/algorithm`;
- the immediately following passive performance request reached the unchanged 2.5-second fail-closed budget after only 26 rows;
- health returned execution-critical state but its optional DB snapshot was interrupted near its wall-clock budget.

## Root cause

`/api/algorithm` called `trading_algorithm.status()`, and `status()` rebuilt `snapshot(record=False)` inline.

That snapshot performed multiple database reads and embedded `institutional_intelligence.cached_status()`, which is the complete deep point-in-time institutional dataset: delivery rows for thousands of securities, hundreds of large-deal records, disclosures, derivatives and other evidence.

The problem was amplified by HTTP timeout semantics. When the validator abandoned a synchronous request, the server-side worker thread could continue computing/serializing it. Retrying the endpoint could therefore leave several expensive algorithm snapshots running concurrently, creating the CPU/JSON/SQLite pressure observed immediately afterward by performance and health.

## v6.8.7 fix

### Compact institutional summary

The institutional producer now also maintains a bounded summary containing only algorithm/status metadata:

- producer status and capture time;
- large-deal count and count with normalized prices;
- delivery security count;
- insider/regulatory disclosure counts;
- derivative producer status;
- compact FII/FPI and DII flow summary;
- producer errors and policy metadata.

The full deep snapshot remains unchanged and continues to be available from `/api/institutional` and point-in-time storage. No evidence is discarded from the institutional research layer.

### Pure passive `/api/algorithm`

Algorithm recomputation now happens only in background/offline paths. `status()` returns the last complete in-memory cache and never calls `snapshot()`, network providers, or deep institutional decoding from the request path.

The cached response explicitly publishes:

- `cache_ready`;
- `algorithm_contract.passive_cached=true`;
- `algorithm_contract.network_calls=false`;
- `algorithm_contract.deep_institutional_payload=false`;
- `algorithm_contract.background_refresh_only=true`.

### Upgrade-time priming

While the service is stopped, the installer:

1. backfills the existing history-summary index;
2. derives the compact institutional summary from the last persisted deep snapshot;
3. computes and persists one compact algorithm status snapshot.

At FastAPI startup, that compact status is loaded before the engine begins scheduling background workers. The first user/API request therefore does not pay an algorithm rebuild cost.

### Validator hardening

The post-install validator now requires the adaptive-algorithm endpoint to be cache-ready and to satisfy the passive compact contract. It also uses a tighter bounded request so a regression cannot silently reintroduce long inline algorithm work.

## Unchanged safety and research contracts

v6.8.7 does not increase the passive performance or health budgets and does not weaken any trading rule.

Unchanged:

- full Groww NSE equity-share universe;
- no market-cap/liquidity Top-N research cap;
- v6.8.6 persisted history summaries for breadth/regime/sector;
- v6.8.4 aggregate LTP hard wall-clock budget;
- passive performance 2.5-second fail-closed budget;
- passive health bounded/no-network behavior;
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
- newly added institutional evidence remains shadow/advisory until incremental OOS validation.

## Canonical repository

Canonical source: `SuhasSrinivasa1/PS-Scanner-Quant`.
