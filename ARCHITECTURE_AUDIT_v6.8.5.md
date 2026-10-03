# Architecture Audit v6.8.5 — professional evidence producers

v6.8.5 extends evidence coverage without narrowing full-NSE research breadth, adding synchronous network calls to passive endpoints, or promoting newly wired observations directly into live scoring.

## Producer / consumer architecture

### Benchmark history

`benchmark_history` is an independent background producer. It refreshes NIFTY 1-day and 5-minute history through the existing centrally paced Groww history pipeline. Equity scanners read that history with `allow_network=False` and use it only when the cached series is available.

This makes benchmark-relative strength deterministic and cache-first while preserving scanner independence.

### Institutional producer

The existing institutional worker remains the sole network owner for direct institutional/disclosure evidence. v6.8.5 extends its point-in-time snapshot with:

- NSE Full Bhavcopy + Security Deliverable data;
- NSE PIT Regulation 7(2) rows;
- selected NSE corporate-announcement classifications;
- bounded priority Groww option-chain / F&O context.

Scanner workers only read the cached institutional context through the evidence fabric.

### Delivery publication timing

A current-session security-delivery report is not assumed to exist during market hours. Until the post-market publication window, the producer asks for the prior completed NSE trading session. Missing reports remain errors/UNKNOWN rather than being synthesized.

### Derivatives budget

F&O collection is limited to priority underlyings that exist in the current Groww NSE F&O instrument master. It has both per-request transport timeouts and an aggregate wall-clock deadline. Partial success is retained and reported; the producer does not wait indefinitely for complete derivatives coverage.

## Scoring isolation

New v6.8.5 direct evidence is initially shadow-only. Trade Intelligence carries it in `shadow_evidence`, while the associated new filters set `score_enabled=False`. This ensures feed availability cannot change recommendation selection before its incremental predictive value has survived chronological OOS, holdout, cost, stability and live-shadow evidence requirements.

This is distinct from the existing v6.8.0 `INSTITUTIONAL_ACCUMULATION` Challenger family, whose established governance remains unchanged.

## Execution-depth boundary

Groww live quote depth is evaluated only inside the manual execution path. Planned quantity is compared with displayed opposite-side depth; insufficient displayed counterparty depth hard-blocks execution. Spread and circuit checks remain in the same live execution-quality gate.

This depth check is not placed in `/api/health`, `/api/sanity`, `/api/performance`, or cache-only research scans.

## Point-in-time semantics

- delivery snapshots record the source trading date;
- disclosure rows retain the direct NSE fields and capture timestamp;
- derivatives snapshots retain expiry, OI/volume/IV/basis and capture time;
- institutional ownership change is computed only from previously captured fundamental snapshots;
- no current observation is backfilled into an earlier recommendation decision.

## Full-breadth preservation

No new Top-N research universe is introduced. Full NSE equity discovery and scanning remain unchanged. Priority bounding applies only to expensive enrichment producers such as derivatives, not to recommendation-universe membership.

## Remaining explicit gaps

v6.8.5 does not claim:

- authoritative historical PIT disclosure/delivery coverage for dates before capture began;
- full Level-2 historical depth / market-impact reconstruction;
- authoritative Indian sector index / sector ETF mapping for every industry;
- a complete national macro-event database;
- a commercial investment-advisory onboarding/suitability/compliance platform.

Missing evidence remains `UNKNOWN` and cannot be silently interpreted as a pass.

## Preserved production controls

The v6.8.1 bounded-performance, v6.8.2 execution-critical health ordering, v6.8.3 dynamic installer version gate and v6.8.4 runtime-contention controls are preserved. Trading risk, frozen identities, Static-IP execution-only scope, broker reconciliation and evidence-governed strategy promotion are unchanged.
