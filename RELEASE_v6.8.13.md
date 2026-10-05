# PS Scanner Quant v6.8.13 — Production Recovery & Operations UI

## Purpose

v6.8.13 converts the v6.8.12 recommendation-recovery work into a production-ready recovery release after the October 5 operating incident.

## Recommendation engine integrity

The v6.8.12 recovery commits remain intact:

- Intraday uses bounded rotating full-cached-breadth recovery rather than a 3,400+ symbol serial deep pass.
- Candidate publication has explicit accounting for published, duplicate identity, deadline, cutoff and insertion outcomes.
- Global→India and future-period books distinguish frozen forecast identity from executable-session activation.
- Pre-activation outcomes are VOID rather than contaminating learning, regardless of whether the prior result was WIN, LOSS or MISS.
- ETF and International expose complete rejection/recovery funnels.
- Shared evidence domains are batch-primed to avoid N×SQLite scanner work.
- Unsupported Yahoo fundamental symbols are negatively cached.
- Support-bundle rebuilds fail safely when free disk is insufficient.

No research, risk or execution gate is relaxed.

## Fresh disaster-recovery installation

The installer now supports a genuinely missing `~/Applications/PS_Scanner_Final` directory.

Fresh mode:

- installs application code and initializes runtime state cleanly;
- runs the complete regression suite before service activation;
- installs a RunAtLoad + KeepAlive LaunchAgent;
- runs the production post-install validator;
- does not require an old credential file to exist;
- keeps manual execution fail-closed until Groww credentials are configured;
- provides `CONFIGURE_GROWW.command` for local, chmod-600 secret setup.

Upgrade mode retains the existing data/ledger preservation behavior.

## Professional operations UI

The UI now includes a persistent Production Command Center with:

- engine/worker health;
- NSE universe and history readiness;
- shared evidence-fabric freshness;
- resolved learning accuracy/sample count;
- frozen-book recovery shortages;
- per-lane scanner status chips;
- explicit ACTIVE vs PREPARED lifecycle state;
- a visible research funnel from universe → processed → history-ready → raw eligible → publication-ready → published;
- recovery/shortage messaging without forced quotas;
- clearer execution locks and fresh-install credential guidance.

Prepared forecasts remain visible but cannot expose an order button before a legitimate executable-session entry exists.

## Preserved invariants

- Full NSE equity-share breadth; no top-N universe cap.
- Research independent of Static IP / execution readiness.
- Manual maximum notional ₹20,000.
- Maximum modeled rupee loss to predefined stop ₹500.
- Minimum reward/risk policy unchanged.
- Weekly / Monthly / ETF executable side remains LONG-only.
- Frozen identities are immutable; recovery never uses hindsight replacement.
- Champion promotion remains OOS/holdout/cost/stability/multiple-testing/live-shadow evidence-gated.
- Passive health/performance/international/support contracts remain bounded and cache-first.
