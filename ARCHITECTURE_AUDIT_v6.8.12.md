# Architecture Audit v6.8.12 — Runtime Completion Without Breadth Reduction

## Production findings

The real-Mac v6.8.11 acceptance run proved the passive request architecture but exposed two background-work completion problems.

Global→India remained a full-breadth job but its necessary summary prefilter still admitted 2,286 detailed candidates from the 3,390-share NSE universe. Detailed cached-history parsing and evidence evaluation then exceeded the 600-second worker watchdog. The validator's hung-worker result was therefore a correct fail-closed signal.

The support bundle compressed successfully to roughly 11.7% of retained source size, but a live refresh took roughly 561 seconds. With a 300-second recurrence, the generic worker loop could schedule another refresh almost immediately after an overrun. That heavy CPU/I/O contention coincided with a 10-second localhost export downloading only a partial archive.

## Global→India design

v6.8.12 preserves the full-NSE breadth invariant.

Every symbol is evaluated by the compact summary stage. Survivors become detailed work items with conservative final-score ceilings. Work items are processed in ceiling order under a bounded per-cycle budget. Once a side has its required exact candidate set, a remaining item may be skipped only if its maximum possible final score cannot enter that set.

The compact close sequence now uses parser-equivalent H/L/C validity, timestamp ordering and duplicate resolution. This makes the close-only summary fields used by the bound consistent with the detailed parser.

If the wall-clock budget expires, the job records bounded continuation state and returns without publishing a partial board. The same job resumes next cycle. Frozen recommendations are produced only from a complete board.

## Support-export design

Bundle generation remains background/offline work. v6.8.12 adds:
- a minimum refresh age so a still-fresh completed bundle is reused;
- an in-memory immutable payload loaded after build and at application startup;
- a response path that serves the memory payload rather than opening the ZIP file on click;
- explicit telemetry that request-path filesystem reads are zero.

A failed future refresh does not invalidate the last completed archive.

## Safety review

No trading, scoring, evidence, target, stop, risk, execution, lifecycle, identity, breadth or strategy-governance threshold is relaxed. Static IP remains ORDER EXECUTION ONLY.
