# PS Scanner handoff

Current source version: **6.8.12**.

The canonical source is the root of the dedicated `PS-Scanner-Quant` repository. Runtime state is intentionally not committed. On a Mac installation, runtime state remains under `~/Applications/PS_Scanner_Final/data`, logs under `~/Applications/PS_Scanner_Final/logs`, and local credentials under the secure runtime data path.

## v6.8.12 bounded Global→India and passive support delivery

The real-Mac v6.8.11 upgrade succeeded: 333 local tests passed, passive caches primed, Groww explicit verification returned CONNECTED, and the application started as 6.8.11 with preserved runtime state. Health remained passive during stress testing with zero request-path DB connections, subsystem refreshes and filesystem reads.

Acceptance still correctly failed. Global→India had evaluated all 3,390 NSE summaries but admitted 2,286 detailed candidates and exceeded its 600-second worker watchdog. The compressed support bundle reduced roughly 401.8 MB of retained content to 47.1 MB, but the live refresh took roughly 561 seconds and the 10-second localhost download transferred only about 10.6 MB.

v6.8.12 keeps the full-NSE summary pass and replaces the unbounded detailed stage with bounded resumable branch-and-bound. Pruning uses conservative maximum final scores and parser-equivalent compact close sequences; an incomplete pass never publishes or freezes a partial board.

The support bundle remains background-built and sanitized. Successful compressed bytes are preloaded into memory, the request serves that immutable payload with zero request-path filesystem reads, and fresh completed archives are not repeatedly rebuilt merely because a compression cycle exceeded the nominal worker interval. The installer still forces one fresh build while the old service is stopped.

No trading, evidence, risk, breadth, lifecycle, identity, Static-IP or strategy-promotion rule changes.

See `RELEASE_v6.8.12.md` and `ARCHITECTURE_AUDIT_v6.8.12.md`.

## v6.8.11 acceptance-gate and compressed-export fix

The real-Mac v6.8.10 upgrade succeeded: checksum/integrity passed, Python 3.12.13 was selected, 329 tests passed, Groww explicit verification returned CONNECTED, and passive Performance/International caches plus the support bundle primed successfully before launch.

The live-worker acceptance run proved the v6.8.10 contention fix. Eight health calls stayed sub-second with zero request-path DB connections, subsystem refreshes or filesystem reads. Performance returned COMPLETE for all 196 CLOSED rows from the passive cache using idx_recs_state_closed_perf_cover. International returned from its passive cache.

Two release-plumbing issues remained. The validator still required the obsolete passive_bounded Performance contract, creating a false negative. The support bundle was prebuilt but uncompressed (~394 MB on the production Mac), so the explicit 10-second localhost download acceptance test timed out after only a partial transfer.

v6.8.11 aligns the validator with passive_cached/background_precomputed semantics, derives expected VERSION from the installed source tree, validates International/support-export readiness, and compresses the prebuilt support archive with DEFLATE level 1 in the existing background/pre-launch producer.

No trading, evidence, risk, breadth, lifecycle, identity, Static-IP or strategy-promotion rule changes.

See `RELEASE_v6.8.11.md` and `ARCHITECTURE_AUDIT_v6.8.11.md`.

## v6.8.10 passive UI completion

The real-Mac v6.8.9 upgrade succeeded and validator returned ok=true. Under simultaneous live workers, however, health remained semantically correct but could still be scheduled for multiple seconds, Performance degraded after 31 loaded rows inside its 2.5-second passive budget, and International plus Export All Logs timed out.

v6.8.10 moves the remaining heavy website reads to background-produced complete snapshots. Health now reads no settings/filesystem/broker/history helper on the request path. Common Performance groupings come from one background CLOSED-ledger snapshot. International/Global-to-India is a completed cached page payload. Export All Logs serves a prebuilt sanitized ZIP. Global-to-India remains full breadth and now yields cooperatively more often.

No trading or evidence gate is loosened.

See `RELEASE_v6.8.10.md` and `ARCHITECTURE_AUDIT_v6.8.10.md`.

## v6.8.9 final product integration pass

The real-Mac v6.8.8 upgrade succeeded: checksum/integrity passed, 311 local tests passed, Groww stayed CONNECTED, v6 data/ledger was preserved, history-summary backfill indexed 4,936 files, institutional compact state was READY, and the algorithm cache was READY.

The v6.8.8 validator returned ok=true. Passive algorithm status was ~9ms internally and performance completed all 196 CLOSED rows on idx_recs_state_closed_perf_cover in ~50ms during validation. A later manual health request during simultaneous market_snapshot HISTORY_SUMMARY and Global->India FULL_BREADTH_SUMMARY_PREFILTER work still took ~3s and interrupted its optional DB snapshot. This isolated the final runtime contention to duplicated background summary work plus health still opening a live DB snapshot.

v6.8.9 makes /api/health DB-free on the request path. A background health-snapshot worker produces the execution-critical DB observation; a stale snapshot explicitly fails execution closed. The persisted full-NSE history-summary observation is shared in memory for a short TTL, preventing duplicate 3k+ symbol decode passes by overlapping workers.

Final product changes:
- one-click sanitized Export All Logs bundle from the UI;
- explicit book-specific tandem evidence profiles, including industry-aware oil/gold/silver/copper/USDINR/global-sector context;
- institutional evidence is never a standalone trade trigger;
- Weekly, ETF and International initial slates target Monday 09:00 IST;
- Monthly initial slate targets 09:00 IST on the first NSE trading day;
- initial identities never disappear or rank-replace;
- later candidates may append only under stricter score + CONFIRMED/STRONG tandem evidence, with daily/period bounds;
- Global->India is a weekly prediction ledger; bearish weekly records are research-only for direct execution;
- Indian SHORT execution remains same-day MIS with hard exit 15:00 IST.

See `RELEASE_v6.8.9.md` and `ARCHITECTURE_AUDIT_v6.8.9.md`.

## v6.8.7 passive adaptive-algorithm cache

The real Mac v6.8.6 upgrade succeeded: SHA/integrity checks passed, 298 local tests passed, the 4,869-file history-summary backfill completed in about 5.6 seconds, Groww remained CONNECTED, and the application started as 6.8.6. Full-NSE breadth reached CURRENT for all 3,390 equities. The v6.8.6 WATP correction also worked in production: the institutional producer was READY, 163 returned large-deal rows carried a usable price, delivery covered 3,262 securities, F&O positioning completed without exhausting its wall-clock budget, and there were no institutional producer errors.

The production acceptance gate still failed for a different reason. `GET /api/algorithm` timed out repeatedly. The route called `trading_algorithm.status()`, which rebuilt `snapshot(record=False)` inline; that snapshot embedded `institutional_intelligence.cached_status()`, i.e. the full deep institutional payload including thousands of delivery rows and hundreds of large deals. A client timeout does not necessarily cancel the synchronous server-side thread, so validator retries could stack several expensive algorithm builds. The subsequent direct performance call then reached the unchanged 2.5-second fail-closed budget after only 26 CLOSED rows, and health's optional DB snapshot was interrupted near its budget even though `market_snapshot` was IDLE and not hung.

v6.8.7 makes `/api/algorithm` a pure passive cached view. The deep institutional producer now also emits a bounded summary state; algorithm snapshots embed only that summary. The installer backfills the compact institutional summary from the last persisted deep snapshot and precomputes the algorithm cache while the service is stopped. FastAPI primes that persisted cache synchronously before starting the engine, and subsequent algorithm recomputation happens only in background workers. The validator now requires `cache_ready=true`, `passive_cached=true`, no network calls, and no deep institutional payload.

No passive timeout is increased. No full-NSE breadth cap, scanner cadence reduction, risk relaxation, Static-IP scope change, frozen-book identity change, evidence fabrication, or automatic promotion of shadow evidence is introduced.

See `RELEASE_v6.8.7.md` and `ARCHITECTURE_AUDIT_v6.8.7.md`.

## v6.8.6 persisted history-summary runtime hardening

The real Mac v6.8.5 install succeeded, all 290 local tests passed, Groww remained connected, and post-install validation returned `ok=true`. It also proved the v6.8.4 watchdog fix: `market_snapshot` was progressing in `BREADTH_DISCOVERY` and was not hung. A direct performance request made during that same startup workload still hit the 2.5-second fail-closed budget, however, while only 81 CLOSED rows had been loaded. Production evidence showed the remaining hot path: market breadth and regime still independently reparsed thousands of daily-history JSON files, while sector breadth performed additional cached-history feature work.

v6.8.6 removes that repeated runtime decode cost. The installer backfills a compact SQLite `history_summaries` index while the service is stopped. Every subsequent history persistence keeps it current. Full-NSE breadth, regime classification and sector breadth consume the compact summary instead of reparsing all candle files. Detailed candle JSON remains authoritative for scanners, replay and learning. The same production audit also found NSE large-deal rows carrying price in `watp`; v6.8.6 normalizes WATP so value-weighted direct-deal evidence is retained.

No full-NSE universe cap, scanner cadence reduction, risk relaxation, Static-IP scope change, frozen-book identity change, evidence backfill fabrication or automatic promotion of v6.8.5 shadow evidence is introduced.

See `RELEASE_v6.8.6.md` and `ARCHITECTURE_AUDIT_v6.8.6.md`.

## v6.8.5 professional evidence completion

v6.8.5 audits the requested professional analyst / institutional-flow capabilities against the actual current code. It carries forward the v6.8.0 shared evidence fabric, FII/DII + large-deal context, OBV/CMF/MFI accumulation features, institutional Challenger strategy and adaptive algorithm rather than duplicating them.

The release adds a centrally paced NIFTY benchmark-history producer so scanner relative strength is consistently benchmarked; point-in-time NSE security-delivery, PIT Regulation 7(2), and relevant corporate-announcement evidence; bounded priority Groww option-chain/F&O positioning; prospective institutional-ownership change telemetry; and an execution-only displayed market-depth quantity gate. Newly wired delivery/disclosure/derivatives/sector-proxy evidence remains shadow/advisory and excluded from live scoring until incremental out-of-sample value is demonstrated.

Historical data before capture began is not fabricated. Full historical Level-2 depth, universal Indian sector-index mapping, broader macro-event coverage, and a separate commercial advisory onboarding/suitability/compliance platform remain explicit gaps.

See `RELEASE_v6.8.5.md` and `ARCHITECTURE_AUDIT_v6.8.5.md`.

## v6.8.4 bounded full-breadth runtime contention

v6.8.4 addresses the separate runtime-load defect found after the v6.8.3 Mac install succeeded. The production runtime reported version 6.8.3, engine alive, Groww connected, execution-critical health state available, and position reconciliation verified, but sustained background load later caused health to exceed a 10-second client deadline, bounded performance to degrade before completing the CLOSED-row aggregation, and `market_snapshot` to exceed its watchdog threshold.

The fix keeps full NSE breadth. Groww LTP batching now has a hard aggregate wall-clock budget with partial-success telemetry; the 90-second daily/intraday warmers use bounded rotating priority pools instead of reparsing the entire cache; heavy warmers are staggered away from initial market snapshot; and market-snapshot internal stage telemetry identifies LTP/breadth/regime stalls. No trading threshold, risk control, evidence rule, frozen identity, Static-IP scope, or Champion/Challenger policy is changed.

See `RELEASE_v6.8.4.md` and `ARCHITECTURE_AUDIT_v6.8.4.md`.

## v6.8.3 installer health-gate reliability

v6.8.3 fixes the v6.8.2 Mac upgrade rollback caused by stale hard-coded `6.8.1` comparisons in the installer's post-launch health checks. The installer now derives the expected runtime version from the newly installed source and uses that same value for both service-health and final Groww-connected acceptance. No runtime trading policy changes are included.

See `RELEASE_v6.8.3.md` and `ARCHITECTURE_AUDIT_v6.8.3.md`.

## v6.8.2 clean-baseline / bounded health execution snapshot

v6.8.2 carries forward the fully production-validated v6.8.1 performance fix and adds one concrete bounded-health reliability hardening before migration to a dedicated public PS Scanner repository.

The health snapshot now reads the daily manual-order count and persisted reconciliation/system state before optional historical telemetry. New indexes support the 24-hour trade-decision aggregation and daily order-count expression. This prevents a grown historical decision ledger from consuming the passive one-second health SQL budget before execution-critical diagnostic fields are available.

Static IP remains execution-only. An unset Static IP is an expected execution blocker, not a scanner/research defect.

The installer prefers an already-installed Python 3.12/3.11/3.10, rebuilds the disposable .venv cleanly, and retains a conditional urllib3 compatibility pin for legacy Python 3.9 / Apple LibreSSL environments. It does not install or modify system Python.

See `RELEASE_v6.8.2.md` and `ARCHITECTURE_AUDIT_v6.8.2.md`.

## v6.8.1 bounded performance analytics reliability

v6.8.1 is a narrow reliability patch for the production Mac timeout on `/api/performance?group_by=book&limit=1000`. The root cause was an unbounded passive analytics design: normal 10-second SQLite lock waiting, a full-row CLOSED scan ordered by an unindexed close-time expression, and unnecessary decoding of large feature/rationale/audit JSON before grouping.

The passive API now uses one bounded WAL snapshot, a short busy timeout, a SQLite progress handler plus CPU deadline, narrow SQL projection, and CLOSED-order indexes. If the complete requested aggregation cannot finish inside the passive budget, it returns explicit `DEGRADED_BOUNDED` telemetry with no partial statistics. Internal learning analytics remain complete and are not put on the passive API budget. No network calls or global database locks were added.

The v6.8 producer/consumer evidence fabric, scanner cadences, lifecycle policy, point-in-time semantics, Champion/Challenger contract, risk and execution gates are unchanged. Circuit continues to use exact Groww quotes only after cached full-market coarse screening identifies evidence-triggered candidates.

## v6.8.0 shared evidence fabric / adaptive algorithm

v6.8.0 changes orchestration from independent evidence fetching toward shared external-data producers plus independent cache-only scanner consumers. It preserves existing scanner cadences while centralizing priority quotes, global context, fundamentals, sector breadth, news, earnings events, institutional data and bounded U.S. transport. The adaptive algorithm surface is a versioned view of the validated strategy manifest plus all current recommendation books; daily Champion promotion/decay changes the manifest automatically.

Institutional intelligence adds official NSE FII/FPI–DII market activity and large-deal observations plus CMF/MFI/OBV/RVOL and point-in-time ownership. Direct disclosure and inferred accumulation are kept semantically separate. The new institutional strategy family is seeded CHALLENGER-only.

The 80% accuracy requirement is represented as an evidence target, not a promise. Actual resolved target-hit/directional rates and Wilson 95% intervals are exposed. The application never manufactures an 80% value.

## v6.7.3 execution-cache / health-latency hardening

v6.7.3 is the final reliability pass after the successful v6.7.2 production validation. The background broker probe now refreshes Static-IP state, public-IP detection has an independent fallback provider, the health route derives execution readiness from a single bounded SQLite snapshot plus in-memory caches, and broker-position mismatch telemetry explicitly records Groww's quantity-minus-carry-forward semantics. Position mismatches remain fail-closed.

## v6.7.2 bounded sanity / deep database verification

v6.7.2 is a narrow follow-up to v6.7.1. Runtime `/api/sanity` no longer performs an inline `PRAGMA quick_check` on the live production ledger. Runtime sanity uses a wall-clock-bounded SQLite progress handler and short connection timeouts. Deep database integrity remains mandatory during post-install validation through SQLite backup → isolated restore → `PRAGMA quick_check`, with an explicit long-running maintenance budget.

## v6.7.1 health/validation reliability

v6.7.1 is a narrow reliability patch on top of v6.7.0. It does not change recommendation selection, trading thresholds, target/stop logic, execution permission, or learning policy. It makes `/api/health` passive and bounded, prevents it from waiting behind the Groww history pacer lock, bounds cached execution-readiness DB reads, and fixes the post-install validator so the new diagnostics/execution/backup checks are actually initialized and retried.

## v6.7.0 production-integrity architecture

Start with `ARCHITECTURE_AUDIT_v6.7.0.md` and `RELEASE_v6.7.0.md`. The v6.6.1 audit remains the frozen-identity/search-exhaustion baseline. The central runtime lifecycle definition is `psscanner_quant/lifecycle.py`; historical analytics are in `psscanner_quant/analytics.py`.

v6.7.0 completes the production-integrity roadmap on top of v6.6.1. It adds execution-only broker permission checks, position reconciliation, decision-to-fill attribution, first-class no-trade diagnostics, deterministic stored-input production replay, point-in-time audit envelopes, verified SQLite backup/restore, experiment governance and evidence-gated time-of-day/behavior cohorts. No live recommendation threshold is loosened and cohort analytics do not auto-activate as trading gates.

v6.6.1 was a first-principles follow-up to the v6.6.0 restructure. It fixes four integrity gaps found by re-reading the implementation rather than trusting the prior handoff: Weekly/Monthly exclusion now follows overlapping frozen-period identity even after early closure; zero-live Intraday recovery accumulates complete-pass funnel evidence before it may claim no qualified opportunity; ETF missed-freeze recovery is bounded to the live NSE session; and every short-lived SQLite connection explicitly reasserts synchronous=NORMAL.

Active pages are now current-period views, not history views:
- Intraday: current NSE session only.
- Weekly: current relevant NSE week.
- Monthly: current relevant month.
- ETF: current relevant NSE week.
- Circuit Radar: current same-day session plus current next-session forecast lane.
- International: current relevant US weekly book plus current/next Global→India forecast session.
- Older rows remain in SQLite and are exposed through Performance & History, never deleted merely because they leave the active UI.

The v6.6.0 audit found and corrected two recommendation-volume accounting defects without weakening safety: strategy-family diversity was acting as an unvalidated publication veto in two layers, and Intraday scanned at score 72 but silently refused publication below 76. Family diversity is now advisory/shadow until validated out of sample. Intraday's effective threshold remains 76 but exists in exactly one visible funnel stage.

Weekly/Monthly symbol mutual exclusion is enforced both by the application transaction and SQLite INSERT/UPDATE triggers. Same-session Intraday and Circuit identities have deterministic rollover closure. International external-history transport remains subprocess-bounded with no stale fallback. Missed-freeze recovery never fabricates a five-name book.

Performance and learning treat WIN/LOSS/MISS as trading evidence and report VOID/data-integrity rows separately. Wilson confidence intervals are exposed so tiny samples cannot masquerade as established edge. Daily strategy decay excludes VOID rows.

Scanner workers remain independent domain threads, while external observations are owned by shared evidence producers and reused across lanes. Health/sanity use bounded snapshots; worker telemetry exposes state, timing, stage, progress, rejection counters, timeout/hung state, recovery state and watchdog restart count.

## Safety contract

Do not weaken hard risk, freshness, liquidity, data-quality, target-feasibility, execution-permission, Groww budget, stop-risk or order-safety gates to force recommendation counts. Never fabricate names, use stale prices, reconstruct hindsight books, replace frozen identities to improve results, or count VOID/data errors as wins.

Static IP is an order-execution control only. It must not gate recommendation research/publication.

## Validation

Run:

```bash
python -m unittest discover -s tests -v
python3 tools/post_install_validate.py
```

The dedicated `.github/workflows/ci.yml` runs the regression suite on Ubuntu and macOS, validates embedded UI JavaScript and zsh syntax, and builds `PS_Scanner_Quant_v6.8.3.zip` only after tests pass.


## v6.8.1 final production validation

Real-Mac validation completed successfully on 2026-10-03 after installation of the final CI artifact.

- 269 local tests passed.
- `tools/post_install_validate.py` returned `ok=true`.
- Runtime and deep restored-database checks passed.
- Groww remained connected and the existing v6 ledger/state was preserved.
- `/api/performance?group_by=book&limit=1000` returned a complete bounded result over 196 CLOSED rows using `idx_recs_state_closed_perf_cover`; observed internal elapsed time was about 11 ms on the direct check.
- Static-IP execution state was unavailable during the check and the market was closed, so order execution remained fail-closed as designed. Research/publication remained independent of Static IP.
- Monthly, ETF, and International shortage/recovery telemetry remained explicit; no quota fabrication or frozen-book replacement was performed.

The Mac runtime currently uses Python 3.9 linked to LibreSSL 2.8.3, which causes a non-fatal urllib3 v2 compatibility warning. No observed Groww/test/validator failure resulted from it in this release.
