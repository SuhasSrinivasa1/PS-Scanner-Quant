# PS Scanner Quant v6.8.16 — Finalist Runtime & Progress-Aware Worker Health

## Purpose

v6.8.16 fixes the live-market reliability issue observed on October 7, 2026 where the Production Command Center reported `ENGINE ATTENTION · hung: weekly, circuit`.

The production evidence showed two separate conditions:

- Circuit was alive and making forward progress through exact quote verification, so elapsed runtime alone produced a transient false-positive hang warning.
- Weekly had completed its 120-symbol scoring pass and entered `FINALIST_REFRESH`, where 46 finalists triggered repeated portfolio-correlation history parsing. The previous implementation reloaded the same daily histories for every finalist/peer pair and emitted no finalist-stage heartbeat.

## Finalist correlation runtime

The portfolio concentration gate is unchanged.

- Daily correlation evidence remains cache-only and uses the same 80-return / minimum-overlap thresholds.
- A scan-local correlation snapshot now loads each unique finalist/peer daily return series once.
- Finalist evaluation reuses those prepared series instead of reparsing identical history files for every pair.
- No portfolio hard block, correlation threshold, target gate, intelligence gate, frozen identity, or publication rule is weakened.

For the observed 46-finalist / 20-peer shape, the old path could parse roughly 1,840 history files. The new path is bounded by the number of unique finalist and live-peer symbols.

## Progress-aware worker health

Worker health now distinguishes total runtime from lack of progress.

- Scanners publish an in-memory heartbeat without adding SQLite work to the passive `/api/health` request path.
- Weekly/Monthly/Intraday scoring and finalist stages expose current stage, current item, processed count, remaining count, and last progress time.
- Circuit publishes heartbeat progress during full-NSE breadth screening and exact quote verification.
- A worker is marked `hung` only when it is still RUNNING, has exceeded its existing runtime threshold, and has also failed to make forward progress beyond a bounded stall grace.
- `runtime_over_threshold` remains visible separately for diagnostics.

The existing watchdog thresholds are not increased.

## Regression coverage

v6.8.16 adds regression tests proving that:

1. a multi-finalist portfolio correlation pass reads each unique history once and performs no additional history parsing during per-finalist cluster evaluation;
2. a long-running Weekly worker with a fresh finalist heartbeat is not labeled hung;
3. the same worker is labeled hung after its progress heartbeat becomes stale.

## Unchanged production invariants

- Full NSE equity-share breadth; no top-N research cap.
- Static IP remains execution-only.
- Broker reconciliation remains fail-closed.
- Maximum manual order notional remains ₹20,000.
- Maximum modeled loss to stop remains ₹500.
- Weekly / Monthly / ETF executable sides remain LONG-only.
- No forced recommendation quota.
- Frozen identities remain immutable.
- No hindsight replacement or fabricated recommendation.
- History/network producers remain centrally paced and scanners remain cache-first.
- Champion/Challenger promotion and point-in-time evidence rules are unchanged.
