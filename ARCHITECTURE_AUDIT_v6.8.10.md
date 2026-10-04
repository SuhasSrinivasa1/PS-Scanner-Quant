# Architecture Audit v6.8.10 — Passive Read-Path Completion

## Finding

v6.8.9 correctly removed SQLite from /api/health, but the real-Mac live-worker run proved that "zero DB" was not sufficient to guarantee a passive request. Health still invoked several cached helper functions at request time, Performance still aggregated the ledger synchronously, International still composed multiple recommendation/state queries synchronously, and Export still read/redacted/compressed all retained evidence synchronously.

The common architectural defect was request-time ownership of work whose result can safely be produced ahead of the request.

## Resolution

v6.8.10 applies one rule to all website observability surfaces:

**background produces complete immutable snapshots; HTTP reads the last complete snapshot.**

Health snapshots subsystem telemetry as well as DB state. Performance produces all common groupings from one CLOSED-ledger snapshot. International produces one page payload. Support export produces one complete sanitized ZIP. Failed refreshes preserve the prior complete object; missing snapshots return explicit warming/degraded states instead of hanging.

Global-to-India full breadth is preserved. The worker yields cooperatively more often rather than reducing symbols or gates.

## Safety

No trading eligibility threshold, horizon target, stop, order-risk limit, evidence validity rule, identity-freeze rule, Static-IP boundary or broker reconciliation contract changes in this release.
