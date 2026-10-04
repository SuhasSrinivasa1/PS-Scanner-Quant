# Architecture Audit v6.8.11 — Acceptance Contract Alignment

## Production finding

v6.8.10 solved the live request-path contention identified in v6.8.9. The production Mac demonstrated fast pure-memory health, complete passive Performance, and a responsive cached International board.

The post-install validator nevertheless failed because its Performance assertion still described the superseded bounded-live implementation rather than the v6.8.10 background-precomputed implementation.

Separately, prebuilding the support bundle solved request-time generation but ZIP_STORED left the transfer payload at roughly the full retained-text size. On the production Mac the archive was ~394 MB and could not complete the explicit 10-second localhost acceptance transfer.

## Corrective design

v6.8.11 keeps the v6.8.10 architecture and changes only the release/diagnostic layer.

The validator now checks the actual passive-cache contract and also validates International and support-export readiness. Expected runtime version is read from the installed source instead of repeated as a validator literal.

The support archive is compressed during the existing background/pre-launch build using low-cost DEFLATE level 1. Compression remains completely off the HTTP request path. The request still serves an already-complete file.

## Safety review

No trading, evidence, ranking, risk, execution, lifecycle, breadth, or strategy-promotion behavior changes. Static IP remains an ORDER EXECUTION ONLY control.
