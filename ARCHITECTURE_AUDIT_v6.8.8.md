# Architecture Audit v6.8.8 — Global-to-India Full-Breadth Contention

The v6.8.7 real-Mac run proved the adaptive-algorithm endpoint was no longer the source of request-path contention: it returned in about 0.67 seconds from a compact cache. Performance and health still missed their strict budgets while market_snapshot was IDLE.

Code audit found a separate full-breadth worker: Global->India rebuilt detailed pandas features from cached daily history for all ~3,390 NSE equities every five minutes, including weekends.

v6.8.8 converts that path to a two-stage design:

1. Full-universe compact summary pass over every NSE equity.
2. Detailed candle/feature enrichment only for symbols that can still satisfy the unchanged score gate.

The first pass is not a heuristic rank or Top-N filter. It is a mathematical necessary-condition test using exact close-derived ret20/trend and an upper bound that grants the maximum possible ADX score contribution. Therefore any symbol capable of passing the original detailed score formula remains eligible for detailed evaluation.

Explicit `time.sleep(0)` cooperative yields are inserted between bounded symbol batches so passive API threads are not starved during long research loops.

Telemetry records full-universe count, summary-ready count, detailed-survivor count, detailed-parsed count, parse ratio, elapsed time and the no-Top-N policy.

All execution, risk, lifecycle, frozen-book, point-in-time evidence and learning contracts remain unchanged.
