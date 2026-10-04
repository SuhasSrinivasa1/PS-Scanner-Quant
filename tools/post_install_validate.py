#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))
from psscanner_quant.constants import VERSION

BASE="http://127.0.0.1:8765"


def fail(message):
    print("FAIL:",message,file=sys.stderr)
    raise SystemExit(1)


def request_json(path, *, method="GET", timeout=6.0, attempts=4):
    last=None
    for attempt in range(max(1,int(attempts))):
        try:
            req=urllib.request.Request(BASE+path,method=method)
            with urllib.request.urlopen(req,timeout=float(timeout)) as r:
                return json.load(r)
        except Exception as exc:
            last=exc
            if attempt+1 < attempts:
                time.sleep(0.5*(attempt+1))
    fail(f"{method} {path} failed after {attempts} attempts: {last}")


def get(path, *, timeout=6.0, attempts=4):
    return request_json(path,timeout=timeout,attempts=attempts)


ping=get("/api/ping",timeout=2,attempts=3)
if ping.get("version")!=VERSION:fail(f"runtime version is not {VERSION}")

health_started=time.monotonic()
health=get("/api/health",timeout=3,attempts=4)
health_elapsed=time.monotonic()-health_started
if health.get("engine_alive") is not True:fail("engine supervisor is not alive")
contract=health.get("health_contract") or {}
if contract.get("network_calls") is not False:fail("health endpoint is not passive/network-free")
if contract.get("history_pacer_nonblocking") is not True:fail("health endpoint may wait behind history pacer")
if health_elapsed>8:fail(f"health endpoint retries exceeded bounded validation budget: {health_elapsed:.1f}s")

life=get("/api/lifecycle",timeout=4)
if life.get("policy_version")!="V680_SHARED_EVIDENCE_FABRIC_ADAPTIVE_ALGORITHM":fail("lifecycle contract is not v6.8.0")

fabric=get("/api/evidence/fabric",timeout=4)
if fabric.get("policy")!="V680_ONE_OBSERVATION_MANY_CONSUMERS":fail("shared evidence fabric policy missing")
if fabric.get("mode")!="SHARED_PRODUCERS_CACHE_ONLY_CONSUMERS":fail("scanner evidence fabric is not producer/consumer mode")
algorithm_started=time.monotonic()
algorithm=get("/api/algorithm",timeout=3,attempts=2)
algorithm_elapsed=time.monotonic()-algorithm_started
if algorithm.get("policy")!="V680_ADAPTIVE_EVIDENCE_GATED_TRADING_ALGORITHM":fail("adaptive algorithm policy missing")
target=algorithm.get("accuracy_target") or {}
if abs(float(target.get("target") or 0)-0.80)>1e-9:fail("algorithm 80% evidence target missing")
if target.get("guaranteed") is not False:fail("algorithm must never represent the 80% target as guaranteed")
algorithm_contract=algorithm.get("algorithm_contract") or {}
if algorithm.get("cache_ready") is not True:fail("algorithm passive cache is not ready")
if algorithm_contract.get("passive_cached") is not True:fail("algorithm endpoint is not cache-only")
if algorithm_contract.get("network_calls") is not False:fail("algorithm endpoint may perform network work")
if algorithm_contract.get("deep_institutional_payload") is not False:fail("algorithm endpoint embeds deep institutional evidence")
if algorithm_elapsed>4:fail(f"algorithm passive cache exceeded bounded validation budget: {algorithm_elapsed:.1f}s")

sanity_started=time.monotonic()
sanity=get("/api/sanity",timeout=4,attempts=4)
sanity_elapsed=time.monotonic()-sanity_started
sanity_contract=sanity.get("sanity_contract") or {}
if sanity_contract.get("deep_quick_check_inline") is not False:fail("sanity endpoint still performs deep quick_check inline")
if sanity_elapsed>16:fail(f"sanity endpoint retries exceeded bounded validation budget: {sanity_elapsed:.1f}s")
if sanity.get("database_runtime_checks_complete") is not True:
    fail("bounded runtime database sanity checks did not complete: "+str(sanity.get("database_runtime_error") or sanity.get("database_runtime_check")))
if sanity.get("weekly_monthly_collisions"):fail("Weekly/Monthly overlapping frozen-period identity collision detected")
if sanity.get("old_intraday_live_rows"):fail("old Intraday LIVE rows remain")
if sanity.get("old_circuit_live_rows"):fail("old Circuit LIVE rows remain")
if sanity.get("dead_workers"):fail("dead workers: "+",".join(sanity["dead_workers"]))
if sanity.get("hung_workers"):fail("hung workers: "+",".join(sanity["hung_workers"]))

# Deep SQLite integrity is deliberately not part of /api/sanity. Reuse a verified
# backup if one exists; otherwise create + restore-verify one with an explicit long budget.
backups=get("/api/maintenance/backups",timeout=4)
deep=backups.get("last") or {}
if deep.get("restore_verified") is not True or str(deep.get("quick_check") or "").lower()!="ok":
    deep=request_json("/api/maintenance/backup-now",method="POST",timeout=120,attempts=1)
if deep.get("restore_verified") is not True:fail("SQLite backup restore verification failed")
if str(deep.get("quick_check") or "").lower()!="ok":fail("SQLite backup quick_check failed")

for book in ("INTRADAY","WEEKLY","MONTHLY","ETF","CIRCUIT","CIRCUIT_NEXTDAY","INTERNATIONAL"):
    data=get("/api/book/"+book,timeout=6)
    pk=str(data.get("period_key") or "")
    bad=[r for r in (data.get("closed") or []) if str(r.get("period_key") or "")!=pk]
    if bad:fail(f"{book} active payload leaked {len(bad)} historical-period CLOSED rows")

perf=get("/api/performance?group_by=book&limit=1000",timeout=6)
policy=perf.get("outcome_policy") or {}
perf_contract=perf.get("performance_contract") or {}
if "excluded" not in str(policy.get("voids") or "").lower():fail("performance VOID exclusion policy missing")
if perf.get("complete") is not True:fail("performance endpoint returned degraded telemetry: "+str(perf.get("degraded_reason") or perf.get("status")))
if perf_contract.get("passive_cached") is not True:fail("performance endpoint is not using the passive cached contract")
if perf_contract.get("background_precomputed") is not True:fail("performance endpoint was not background-precomputed")
if perf_contract.get("request_path_db_connections") != 0:fail("performance endpoint used request-path database work")
if perf_contract.get("network_calls") is not False:fail("performance endpoint must not make network calls")
if perf_contract.get("partial_rows_published") is not False:fail("performance endpoint may publish partial rows")
if perf_contract.get("selected_index")!="idx_recs_state_closed_perf_cover":fail("performance passive cache did not use the covering index")

international=get("/api/international/board",timeout=4,attempts=3)
international_contract=international.get("cache_contract") or {}
if international_contract.get("ready") is not True:fail("International passive cache is not ready")
if international_contract.get("passive_cached") is not True:fail("International endpoint is not cache-only")
if international_contract.get("request_path_db_connections") != 0:fail("International endpoint used request-path database work")
if international_contract.get("network_calls") is not False:fail("International endpoint may perform network work")

support=get("/api/support/export/status",timeout=3,attempts=3)
if support.get("ready") is not True:fail("support export is not ready")
if support.get("last_error"):fail("support export background build failed: "+str(support.get("last_error")))
if support.get("compression")!="DEFLATE_LEVEL_1":fail("support export is not using background DEFLATE compression")
if support.get("payload_ready") is not True:fail("support export memory payload is not ready")
if support.get("request_path_filesystem_reads") != 0:fail("support export may read the filesystem on click")
support_path=Path(str(support.get("path") or ""))
if not support_path.exists():fail("support export file does not exist")
try:
    with zipfile.ZipFile(support_path,"r") as z:
        bad=z.testzip()
except Exception as exc:
    fail("support export is not a valid ZIP: "+str(exc))
if bad:fail("support export ZIP contains a corrupt member: "+str(bad))
compressed=int(support.get("size_bytes") or 0)
uncompressed=int(support.get("uncompressed_size_bytes") or 0)
if compressed<=0 or uncompressed<=0:fail("support export size telemetry is missing")
if compressed>=uncompressed:fail("support export compression did not reduce retained log/audit size")

diag=get("/api/diagnostics/no-trade?limit=4",timeout=6)
execution=get("/api/execution/analytics?limit=20",timeout=6)

print(json.dumps({
    "ok":True,
    "version":ping.get("version"),
    "lifecycle":life.get("policy_version"),
    "database_runtime":sanity.get("database_runtime_check"),
    "database_deep_quick_check":deep.get("quick_check"),
    "database_restore_verified":deep.get("restore_verified"),
    "workers":len(health.get("workers") or {}),
    "health_elapsed_seconds":round(health_elapsed,3),
    "sanity_elapsed_seconds":round(sanity_elapsed,3),
    "health_contract":contract,
    "sanity_contract":sanity_contract,
    "evidence_fabric_policy":fabric.get("policy"),
    "algorithm_version":algorithm.get("algorithm_version"),
    "algorithm_accuracy_target":target,
    "algorithm_elapsed_seconds":round(algorithm_elapsed,3),
    "algorithm_contract":algorithm_contract,
    "performance_rows_scanned":perf.get("rows_scanned"),
    "performance_contract":perf_contract,
    "international_cache_contract":international_contract,
    "support_export":{"size_bytes":compressed,"uncompressed_size_bytes":uncompressed,
                      "compression_ratio":support.get("compression_ratio"),"compression":support.get("compression"),
                      "payload_ready":support.get("payload_ready"),"payload_bytes":support.get("payload_bytes"),
                      "request_path_filesystem_reads":support.get("request_path_filesystem_reads")},
    "diagnostic_books":len(diag.get("books") or {}),
    "execution_orders_scanned":execution.get("orders_scanned"),
    "backup_policy":backups.get("policy"),
    "frozen_book_shortages":sanity.get("frozen_book_shortages") or {},
},indent=2))
