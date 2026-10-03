# PS Scanner Quant v6.8.3

v6.8.3 is a narrow installer-reliability patch on top of the audited v6.8.2 clean baseline.

## Root cause

The v6.8.2 application, dependencies, Python 3.12 virtual environment, regression suite, and LaunchAgent plist all validated successfully on the production Mac. The installer then rejected the newly launched service because two post-launch acceptance checks still compared the runtime-reported version against the stale literal `6.8.1`.

That caused a healthy v6.8.2 service to fail the installer health gate and triggered the installer rollback path.

## Fix

- the installer now derives `EXPECTED_VERSION` from the newly installed `psscanner_quant.constants.VERSION`;
- both the first service-health gate and the final health+Groww gate compare against that dynamically derived version;
- no future patch bump requires editing a hidden hard-coded version in the health gate;
- the rollback behavior remains unchanged and fail-safe;
- all v6.8.2 health-query indexes, bounded performance analytics, Static-IP execution-only policy, risk limits, frozen-book rules, evidence fabric, and audit integrity controls are unchanged.

## Validation

A dedicated regression test verifies:
- runtime version is 6.8.3;
- the installer derives expected version from installed source;
- both health gates use the same dynamic expected version;
- stale v6.8.1 acceptance checks cannot reappear silently.

The v6.8.2 production attempt that exposed this defect had already completed all 274 tests successfully before the stale post-launch gate rejected the service.

## Canonical repository

Canonical source: `SuhasSrinivasa1/PS-Scanner-Quant`. The prior monorepo is retained only as historical backup.
