# PS Scanner Quant v6.8.18 — Website Correctness

## Scope

v6.8.18 is a website/UI correctness release. It does not change recommendation generation, research gates, Groww pacing, risk sizing, frozen-book identity, recovery policy, or execution safety.

## Corrected website semantics

The production command center now treats each domain independently:

- **Research engine** — reflects the engine supervisor and worker health.
- **Background workers** — `UNKNOWN/WARMING`, `PROGRESSING`, `STALLED`, and `DEAD` are distinct states.
- **Groww** — `UNKNOWN_NOT_PROBED` is shown as **PROBING**, not a red authentication failure.
- **Static IP** — not configured is amber; a configured mismatch is red because order execution is fail-closed.
- **Execution** — has its own top-level READY / WARMING / LOCKED state and blocker detail. An execution lock does not imply research failure.
- **Recovery lanes** — interrupted/recovery/preparing states are warnings, not engine failures; actual ERROR/FAILED/DEAD/HUNG/STALL states remain red.
- **Frozen-book shortages** — only positive shortages are counted and the recovery status is shown explicitly.
- **Health refresh failures** — no longer overwrite the Groww pill with an unrelated "HEALTH ERROR" state.
- **Recommendation order buttons** — show the actual first execution blocker with all blockers in the tooltip instead of always masking behind Static IP.

## Existing v6.8.17 behavior retained

Daily-history hydration remains progress-aware. Runtime above the expected threshold while the worker is making progress is BUSY/PROGRESSING, not HUNG.

## Unchanged safety invariants

- Full NSE equity-share breadth remains enabled.
- ETF and equity paths remain separate.
- Static IP remains execution-only.
- Broker position reconciliation remains fail-closed.
- Maximum manual notional remains ₹20,000.
- Maximum modeled risk-to-stop remains ₹500.
- Minimum R/R remains enforced.
- Frozen recommendation identities remain immutable.
- No recommendation fabrication or hindsight replacement is introduced.
- Champion/Challenger evidence governance is unchanged.
