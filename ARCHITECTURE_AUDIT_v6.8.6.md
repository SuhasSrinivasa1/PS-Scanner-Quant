# Architecture Audit v6.8.6 — persisted breadth/regime summaries

v6.8.6 closes the remaining startup-contention path observed on the production Mac without weakening passive endpoint budgets or narrowing research breadth.

## Production evidence

The v6.8.5 installer completed successfully and preserved the runtime ledger/state. The local suite ran 290 tests successfully, Groww was CONNECTED, the application reported version 6.8.5, and the validator returned `ok=true` with deep database restore verification.

During the validator, performance completed 196 CLOSED rows using `idx_recs_state_closed_perf_cover` in roughly 337 ms. A direct request seconds later, while startup workers were active, truthfully returned `DEGRADED_BOUNDED` after reaching the unchanged 2.5-second budget. The sampled market-snapshot worker was in `BREADTH_DISCOVERY` and `hung=false`.

This combination establishes that the SQL/index design works but Python-side startup contention can still starve the passive request.

## Shared summary boundary

The new `history_summaries` table is an operational derivative of the authoritative local candle cache. It does not replace historical evidence.

Each row contains bounded metadata needed by broad consumers. Detailed scanners continue to read full histories according to their existing cache/network policy.

At install/upgrade time, existing history files are decoded once while the service is stopped. At runtime, `_persist_history` synchronizes the relevant summary row whenever a history cache is refreshed.

## Full-NSE semantics

Full breadth remains exact at the universe boundary: every current Groww NSE equity-share symbol is iterated by the market-breadth pass. Missing summary/history remains missing; no rows are fabricated and no symbol is dropped for market cap, liquidity or history depth.

Readiness counts and mover calculations use the compact indexed summaries. Symbols without sufficient history remain limited-history names and continue through the existing enrichment rotation.

## Regime semantics

Regime classification receives the same daily summary snapshot as breadth. It therefore does not perform a second full-universe candle decode. If the summary database is temporarily unavailable, the worker may expose the prior complete regime as stale rather than manufacturing a new regime from incomplete inputs.

## Sector semantics

Sector breadth computes only the fields it actually consumes—recent returns, SMA20/SMA50 trend and breadth percentages—from recent closes already present in the compact summary. It no longer constructs full feature DataFrames for sector peers.

The last complete sector snapshot is persisted and restored during non-passive supervisor bootstrap. Passive health never triggers network or rebuild work.

## Institutional correctness

NSE bulk-deal payloads observed in production use `watp` for weighted-average trade price. v6.8.6 maps that field into normalized `price` and `value_rupees`. Direct disclosure and inferred accumulation evidence remain semantically separate.

## Safety invariants

No trading threshold, risk sizing rule, execution permission, static-IP rule, broker reconciliation rule, frozen identity, lifecycle rule, evidence-gating rule or passive endpoint budget is relaxed.

The release is specifically designed so production responsiveness improves because duplicate CPU work is removed, not because safety timeouts are increased.
