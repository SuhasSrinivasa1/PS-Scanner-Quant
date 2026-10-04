# Architecture Audit v6.8.9 — Final Tandem/Ownership/Support Pass

## Production evidence entering this audit

The real-Mac v6.8.8 install was successful. The v6.8.8 validator showed passive health, sanity, algorithm and performance operating correctly in one pass, including COMPLETE performance over 196 CLOSED rows on `idx_recs_state_closed_perf_cover`.

A manual health call made shortly afterward overlapped with two full-breadth background workers:
- `market_snapshot` at `HISTORY_SUMMARY`;
- `global_india` at `FULL_BREADTH_SUMMARY_PREFILTER`.

The passive health request then spent about three seconds and its optional DB snapshot was interrupted. Because algorithm and performance had already been fixed and market_snapshot was not hung, the remaining defect was duplicated background evidence work plus an HTTP health path that still attempted a DB snapshot during contention.

## Audit findings

### 1. Passive health still depended on live DB scheduling
This was the remaining reliability defect. A passive endpoint should not need to win a SQLite/Python scheduling race against full-breadth research.

**v6.8.9:** health uses a background-produced DB snapshot. The HTTP route opens zero DB connections. Snapshot staleness is explicit and blocks execution rather than trusting stale daily-order/reconciliation state.

### 2. Full-breadth history-summary evidence was decoded repeatedly
Market snapshot and Global->India could independently read/decode the same persisted history summaries within seconds.

**v6.8.9:** the full snapshot is cached in memory for 30 seconds. Full breadth is preserved; only duplicate observation work is removed.

### 3. Evidence existed across the application but book-specific roles were implicit
Technical, institutional, news, event, sector and global observations already existed, but their intended role differed by horizon and was not centrally visible.

**v6.8.9:** a declarative evidence-combination profile defines primary/confirming/macro roles by book. Institutional activity is explicitly prohibited from becoming a standalone trigger. Commodity/FX dependencies are mapped by industry. Existing validated scoring remains authoritative; the new combination state is context/audit and is used only as an additional quality requirement for append discoveries until incremental OOS evidence supports more.

### 4. Frozen books stopped discovery after the initial contract
This protected identity but prevented the user-requested “full week/full month view” where a later genuinely stronger opportunity may be appended.

**v6.8.9:** initial identities remain immutable while later discoveries are append-only under stricter gates and bounded counts. No deletion, replacement or quota fill is introduced.

### 5. Global->India prediction horizon and execution horizon were conflated
The prior Global->India lane was next-session oriented. The final product requirement is a weekly prediction set, while Indian short execution must remain same-day only.

**v6.8.9:** prediction records are weekly; bearish weekly records are research-only for direct execution. The order-preview backend and UI both block direct execution from `GLOBAL_INDIA_SHORT`. Same-day short lanes remain the only execution path.

### 6. Operational evidence export was fragmented
Long-term weekly/daily review would require manually collecting multiple files and endpoint payloads.

**v6.8.9:** one sanitized support bundle exports all retained application logs and the major audit ledgers from the UI.

## Resulting architecture

One observation can now feed many consumers:
- Groww/NSE/global producers acquire evidence;
- shared caches/fabric normalize it;
- book-specific evidence profiles establish horizon relevance;
- existing intelligence/risk gates decide eligibility;
- immutable initial slates establish period accountability;
- stricter append gates may add later discoveries;
- outcome/performance/algorithm layers learn from every retained identity;
- one support bundle exports the evidence needed to audit the system later.

No trading threshold, risk cap, Static-IP boundary, full-breadth rule or evidence-integrity rule is weakened by this release.
