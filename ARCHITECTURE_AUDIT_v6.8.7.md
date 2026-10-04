# Architecture Audit v6.8.7 — Passive Algorithm Boundary

v6.8.7 closes a request-path architecture violation exposed by real production validation.

## Observed failure

The v6.8.6 Mac runtime was healthy enough to complete installation, preserve state, connect to Groww, populate full-NSE breadth, and produce institutional evidence. Nevertheless, the post-install validator repeatedly timed out on `/api/algorithm`. After those retries, `/api/performance` degraded at its fixed wall-clock budget and the optional health DB snapshot was interrupted.

Because `market_snapshot` was IDLE and not hung at that point, the remaining pressure was not the v6.8.4/v6.8.6 market-history path.

## Request-path violation

The adaptive-algorithm route was nominally a status endpoint but performed production work inline:

`/api/algorithm -> trading_algorithm.status() -> snapshot(record=False)`.

The snapshot:

- queried the active strategy manifest;
- queried CLOSED recommendation accuracy evidence;
- queried current LIVE outputs;
- queried persisted evidence-fabric domains;
- loaded the complete institutional snapshot;
- assembled/serialized the resulting nested payload.

The full institutional object can contain thousands of delivery entries and hundreds of direct-deal records. It is appropriate for the explicit institutional endpoint and point-in-time store, but not for a passive status surface.

Repeated client-side timeouts can also overlap server-side synchronous work because abandoning the HTTP connection does not guarantee cancellation of the Python worker function.

## Architectural correction

### Producer owns computation

`trading_algorithm.refresh()` remains the producer. It creates the adaptive algorithm snapshot and persists audit history in the background.

### Consumer is cache-only

`trading_algorithm.status()` now only reads the already-computed in-memory cache. If no cache has been primed yet it returns an immediate bounded WARMING structure rather than computing inline.

No database or provider call is made from the normal cached status path.

### Persisted restart cache

A compact algorithm status payload is stored under `adaptive_algorithm_status_cache`. Installation primes it while the service is stopped. Application startup loads it synchronously before starting scheduler threads. This eliminates the first-request thundering-herd risk.

### Deep/summary institutional split

The deep institutional snapshot remains the authoritative point-in-time evidence object.

A new bounded summary is separately maintained for algorithm/status consumers. It intentionally excludes:

- per-symbol delivery maps;
- full large-deal arrays;
- full disclosure arrays;
- per-symbol derivative maps.

It retains counts/status/flows needed for operational algorithm context.

## Failure semantics

The API exposes `cache_ready`. A missing cache is reported as WARMING; it is never disguised as a complete adaptive snapshot.

The post-install validator requires a ready passive cache. Thus installation cannot be declared production-ready merely because the endpoint returns HTTP 200.

## Interaction with performance and health

This release does not make performance or health more permissive.

The expected improvement comes from eliminating expensive work and retry pile-up elsewhere in the same process. Performance still fails closed at 2.5 seconds with no partial publication, and health still protects execution-critical state before optional telemetry.

## Invariants

No research breadth, cadence, recommendation gate, target feasibility rule, risk limit, execution gate, broker reconciliation rule, Static-IP rule, frozen identity, lifecycle semantics, or evidence-promotion criterion is relaxed.
