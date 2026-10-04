# PS Scanner Quant v6.8.11 — Acceptance Gate & Compressed Support Export

v6.8.11 is a narrow release-plumbing fix based on the real-Mac v6.8.10 acceptance run.

## Real-Mac evidence from v6.8.10

The v6.8.10 upgrade itself succeeded:
- SHA-256 matched and ZIP integrity passed.
- Python 3.12.13 was selected.
- 329 local tests passed.
- history-summary, institutional, adaptive-algorithm, passive Performance and passive International caches primed successfully before launch.
- Groww explicit verification returned CONNECTED.
- runtime data, credentials, recommendation ledger and strategy state were preserved.
- the application started as 6.8.10.

The live-worker acceptance run also proved the v6.8.10 contention fix:
- eight consecutive /api/health calls stayed sub-second;
- health reported zero request-path DB connections, zero request-path subsystem refreshes, zero filesystem reads and fresh execution snapshots;
- /api/performance returned COMPLETE for all 196 CLOSED rows from the passive cache using idx_recs_state_closed_perf_cover;
- /api/international/board returned from the passive cache with zero request-path DB/network work.

Two release-plumbing defects remained:
1. tools/post_install_validate.py still required the obsolete v6.8.1 passive_bounded contract even though v6.8.10 intentionally replaced the common Performance request with passive_cached/background_precomputed semantics.
2. the prebuilt support export was ZIP_STORED. On the production Mac it was ~394 MB; the background build succeeded, but a 10-second localhost acceptance download transferred only ~6 MB before curl timed out.

## v6.8.11 changes

### Validator matches the current architecture
The validator derives VERSION from the installed source tree instead of hard-coding the release number.

For the common Performance endpoint it now requires:
- complete=true;
- passive_cached=true;
- background_precomputed=true;
- request_path_db_connections=0;
- network_calls=false;
- partial_rows_published=false;
- idx_recs_state_closed_perf_cover.

The validator also checks:
- International cache ready/passive/DB-free/network-free;
- support export ready with no background error;
- DEFLATE level-1 compression;
- valid ZIP central directory/member integrity;
- nonzero compressed/uncompressed size telemetry;
- compressed size smaller than retained uncompressed content.

### Support bundle is compressed off-request
The background/pre-install support builder now uses ZIP_DEFLATED at compression level 1.

This keeps the important v6.8.10 property: no log redaction, audit-table query or compression happens when the user clicks Export All Logs. The HTTP route still serves the last complete prebuilt file. A failed refresh never replaces the previous complete archive.

The bundle continues to contain all retained application logs plus sanitized audit ledgers, while excluding credentials/settings and redacting known secret values.

## Unchanged safety and research contracts

No scanner cadence, full-NSE breadth, recommendation threshold, target/stop geometry, point-in-time evidence rule, institutional-evidence rule, frozen identity, append-only policy, Static-IP scope, broker reconciliation rule, manual notional cap, stop-risk cap, minimum reward/risk, Indian SHORT hard exit, or Champion/Challenger promotion rule changes in v6.8.11.
