# PS Scanner Quant v6.8.5 — Professional Evidence Completion

v6.8.5 is an evidence-quality release on top of the v6.8.4 runtime-contention hardening. It audits the professional analyst / institutional-flow requests against the current application, preserves the capabilities already delivered in v6.8.0, and closes the remaining implementable gaps with point-in-time producers and execution-only controls.

It does **not** fabricate unavailable data, convert unvalidated observations directly into live scoring, or turn PS Scanner into a client-onboarding / investment-advisory compliance platform.

## What was already present

The audit confirmed that v6.8.4 already retained the major v6.8.0 work:

- shared evidence fabric with cache-only scanner consumers;
- background news and event producers;
- official NSE FII/FPI–DII market-flow context;
- NSE large-deal observations;
- OBV, CMF, MFI and relative-volume accumulation/distribution evidence;
- point-in-time institutional ownership snapshots;
- `INSTITUTIONAL_ACCUMULATION` as a Challenger strategy family;
- evidence-gated Champion promotion / suspension;
- adaptive algorithm versioning and truthful 80% evidence-target reporting;
- full-NSE equity-share breadth, risk/execution controls and point-in-time audit envelopes.

Those features are carried forward rather than duplicated.

## New v6.8.5 evidence producers

### NIFTY benchmark-relative strength

A dedicated background history producer now keeps cached NIFTY daily and 5-minute history current through the same centrally paced Groww history path used elsewhere. Scanner workers remain cache-only and pass the benchmark series into feature generation, so `relative_strength20` is no longer merely an optional field with no consistent producer.

### NSE security-wise delivery evidence

The institutional producer captures the latest published NSE security-level deliverable quantity / delivery percentage from the official Full Bhavcopy + Security Deliverable report. During the trading session it requests the prior completed session rather than a same-day report that has not yet been published.

Delivery evidence is timestamped in the institutional point-in-time snapshot. Historical periods before v6.8.5 capture are not backfilled or invented.

### NSE insider / promoter and regulatory disclosures

The institutional producer captures recent NSE SEBI PIT Regulation 7(2) disclosure rows and classifies relevant NSE corporate announcements for:

- pledge / encumbrance disclosures;
- insider disclosures;
- SAST / material ownership-change disclosures;
- selected governance-risk disclosures such as fraud, forensic review, insolvency/default, auditor resignation, show-cause, penalty or regulatory action.

Direct disclosures are kept distinct from inferred OHLCV accumulation. Absence of a recent disclosure is not treated as evidence that governance risk is safe.

### Groww F&O positioning

For a bounded set of priority symbols that actually have NSE F&O instruments, the background institutional producer captures:

- call / put open interest;
- PCR by open interest;
- call / put volume and volume PCR;
- near-ATM call / put implied volatility;
- put-minus-call IV skew;
- total-OI change versus the prior point-in-time snapshot;
- nearest-future quote and futures basis where available.

The producer uses Groww option-chain and F&O quote data, is priority-bounded, and has a hard aggregate wall-clock budget. It does not launch an unbounded derivatives sweep across the market.

### Live displayed market depth at execution

Manual order preview / execution now evaluates Groww displayed bid/ask depth in addition to the existing live spread and circuit-limit checks. If the planned order quantity exceeds displayed opposite-side depth, execution fails closed.

This is an **execution-only** network check. Passive health, sanity, performance analytics and research scanners remain network-free/cache-only according to their existing contracts.

## Shadow-first scoring contract

The newly added v6.8.5 delivery, insider/regulatory, derivatives and external sector-proxy evidence is exposed to Trade Intelligence as shadow/advisory evidence. It is deliberately excluded from live score arithmetic until incremental out-of-sample value is demonstrated through the existing evidence-governance process.

The pre-existing v6.8.0 institutional accumulation signal continues under its existing Challenger/Champion governance. v6.8.5 does not grant newly wired data an automatic live-trading advantage merely because the feed now exists.

## Ownership-change evidence

Institutional ownership change is now explicitly surfaced from successive point-in-time fundamental snapshots when at least two differing captured values exist. It remains prospective-only: the application will not use today's ownership figure to manufacture historical ownership changes.

## What intentionally remains a gap

The following remain explicit rather than fabricated:

- complete historical point-in-time fundamentals before the original capture system existed;
- complete historical insider / promoter / pledge / delivery evidence before v6.8.5 capture;
- authoritative Indian sector-index or sector-ETF history mapping for every industry;
- full historical Level-2 order-book / market-impact data beyond live displayed Groww depth;
- a broader authoritative CPI/GDP/macro-release registry beyond the currently seeded / captured event sources;
- a commercial advisory compliance stack for investor onboarding, suitability, consent, disclosures, registration and grievance handling.

The last item is a separate product/regulatory system, not a scanner feature, and is not represented as completed by v6.8.5.

## Runtime safeguards

v6.8.5 preserves v6.8.4 contention controls. New producers are bounded:

- NIFTY history uses the centralized Groww history pacer;
- delivery is one bounded report fetch per institutional refresh;
- NSE disclosure calls are background-only and bounded;
- F&O positioning is priority-limited with a hard aggregate wall-clock budget;
- scanners consume the resulting caches and do not synchronously call these sources.

## Unchanged safety invariants

- Static IP remains order-execution only.
- Groww position reconciliation remains fail-closed.
- Manual order notional remains capped at ₹20,000.
- Modeled stop-risk remains capped at ₹500.
- Minimum reward/risk remains 1.5.
- Indian same-day SHORT hard exit remains 15:00 IST.
- Weekly/Monthly frozen identity and no rank replacement remain unchanged.
- No recommendation is fabricated to fill a quota.
- VOID remains outside the trading-performance denominator.
- Champion/Challenger promotion remains evidence-gated.
- Passive `/api/health`, `/api/sanity` and `/api/performance` remain broker/network-free.

## Regression coverage

v6.8.5 adds regression coverage for benchmark-relative strength wiring, official delivery/disclosure source contracts, Groww option-chain/F&O access, aggregate derivatives budgeting, shadow-only score isolation, live displayed-depth execution blocking, and research-framework gap reporting.
