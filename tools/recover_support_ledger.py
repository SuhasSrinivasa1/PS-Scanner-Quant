#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))

from psscanner_quant.constants import IST
from psscanner_quant.db import DB_PATH, init_db
from psscanner_quant.strategy_library import seed_library

POLICY="V6812_SUPPORT_LEDGER_RECOVERY_NO_FABRICATED_EVIDENCE"
EXPORTS={
    "recommendations":"diagnostics/recommendations.jsonl",
    "trade_decisions":"diagnostics/trade_decisions.jsonl",
    "scan_runs":"diagnostics/scan_runs.jsonl",
    "strategy_validation_runs":"diagnostics/strategy_validation_runs.jsonl",
    "algorithm_versions":"diagnostics/algorithm_versions.jsonl",
    "institutional_snapshots":"diagnostics/institutional_snapshots.jsonl",
    "system_state":"diagnostics/system_state.jsonl",
    "health_events":"diagnostics/health_events.jsonl",
}
AUTO_ID_TABLES={"trade_decisions","scan_runs","strategy_validation_runs","algorithm_versions","health_events"}
DURABLE_STATE_KEYS={
    "adaptive_algorithm_current","adaptive_algorithm_status_cache","institutional_intelligence","institutional_intelligence_summary",
    "last_recommendation_learning_evidence","recommendation_learning_evidence_day","last_shadow_cycle","last_shadow_resolution",
    "last_strategy_decay_monitor","last_strategy_discovery","last_strategy_validation","last_daily_strategy_validation",
    "last_weekly_strategy_validation","strategy_decay_day","strategy_discovery_week","strategy_validation_day","strategy_validation_week",
}
DURABLE_STATE_PREFIXES=("international_weekly_freeze_",)


def _sha256(path:Path)->str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""):
            h.update(chunk)
    return h.hexdigest()


def _jsonl(zf:zipfile.ZipFile,name:str)->Iterable[Dict[str,Any]]:
    with zf.open(name) as f:
        for raw in f:
            if not raw.strip():continue
            row=json.loads(raw)
            if not isinstance(row,dict):
                raise ValueError(f"{name}: non-object JSONL row")
            yield row


def _columns(con:sqlite3.Connection,table:str)->set[str]:
    return {str(r[1]) for r in con.execute(f"PRAGMA table_info({table})")}


def _insert_row(con:sqlite3.Connection,table:str,row:Dict[str,Any],*,ignore:bool=True,drop_id:bool=False)->bool:
    cols=_columns(con,table);payload=dict(row)
    if drop_id:payload.pop("id",None)
    unknown=set(payload)-cols
    if unknown:
        raise ValueError(f"{table}: export columns not present in target schema: {sorted(unknown)}")
    names=[c for c in payload if c in cols]
    sql=f"INSERT {'OR IGNORE ' if ignore else ''}INTO {table}({','.join(names)}) VALUES({','.join('?' for _ in names)})"
    cur=con.execute(sql,tuple(payload[c] for c in names))
    return cur.rowcount>0


def _insert_validation(con:sqlite3.Connection,row:Dict[str,Any])->bool:
    exists=con.execute(
        "SELECT 1 FROM strategy_validation_runs WHERE run_id=? AND strategy_id=? AND validated_at=? LIMIT 1",
        (row.get("run_id"),row.get("strategy_id"),row.get("validated_at")),
    ).fetchone()
    if exists:return False
    return _insert_row(con,"strategy_validation_runs",row,ignore=False,drop_id=True)


def _insert_health(con:sqlite3.Connection,row:Dict[str,Any])->bool:
    exists=con.execute(
        "SELECT 1 FROM health_events WHERE ts=? AND component=? AND level=? AND message=? AND payload_json=? LIMIT 1",
        (row.get("ts"),row.get("component"),row.get("level"),row.get("message"),row.get("payload_json") or "{}"),
    ).fetchone()
    if exists:return False
    return _insert_row(con,"health_events",row,ignore=False,drop_id=True)


def _durable_state(key:str)->bool:
    return key in DURABLE_STATE_KEYS or any(key.startswith(p) for p in DURABLE_STATE_PREFIXES)


def _restore_strategy_evidence(con:sqlite3.Connection,validation_rows:list[Dict[str,Any]],algorithm_rows:list[Dict[str,Any]])->Dict[str,Any]:
    latest:Dict[str,Dict[str,Any]]={};eligible=set()
    for r in validation_rows:
        sid=str(r.get("strategy_id") or "")
        if not sid:continue
        if int(r.get("promotion_eligible") or 0)==1:eligible.add(sid)
        if sid not in latest or str(r.get("validated_at") or "")>str(latest[sid].get("validated_at") or ""):
            latest[sid]=r
    restored_stats=0
    for sid,r in latest.items():
        try:m=json.loads(r.get("metrics_json") or "{}")
        except Exception:m={}
        con.execute(
            "INSERT INTO strategy_stats(strategy_id,regime,sample_count,win_rate,avg_r,profit_factor,sharpe,sortino,max_drawdown,robustness,walk_forward_score,score,last_validated_at,holdout_avg_r,cost_adjusted_avg_r,parameter_stability,multiple_testing_penalty,decay_state) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(strategy_id,regime) DO UPDATE SET sample_count=excluded.sample_count,win_rate=excluded.win_rate,profit_factor=excluded.profit_factor,max_drawdown=excluded.max_drawdown,robustness=excluded.robustness,walk_forward_score=excluded.walk_forward_score,score=excluded.score,last_validated_at=excluded.last_validated_at,holdout_avg_r=excluded.holdout_avg_r,cost_adjusted_avg_r=excluded.cost_adjusted_avg_r,parameter_stability=excluded.parameter_stability,multiple_testing_penalty=excluded.multiple_testing_penalty,decay_state=excluded.decay_state",
            (sid,"ALL",int(r.get("sample_count") or 0),m.get("win_rate"),None,m.get("profit_factor"),None,None,m.get("max_drawdown"),m.get("robustness"),r.get("walk_avg_r"),m.get("score"),r.get("validated_at"),r.get("holdout_avg_r"),r.get("cost_adjusted_avg_r"),r.get("parameter_stability"),r.get("multiple_testing_penalty"),"RECOVERED_FROM_EXPORTED_VALIDATION"),
        )
        restored_stats+=1
    champion_count=None
    if algorithm_rows:
        last=max(algorithm_rows,key=lambda r:str(r.get("generated_at") or ""))
        try:payload=json.loads(last.get("payload_json") or "{}")
        except Exception:payload={}
        champion_count=int((payload.get("strategy_status_counts") or {}).get("CHAMPION") or 0)
    restored_champions=[]
    # Identity inference is allowed only when the exported current champion count exactly
    # equals the set of strategies that ever passed the exported promotion gate.
    if champion_count is not None and champion_count==len(eligible):
        for sid in sorted(eligible):
            cur=con.execute("UPDATE strategies SET status='CHAMPION',updated_at=? WHERE strategy_id=?",(datetime.now(IST).isoformat(timespec="seconds"),sid))
            if cur.rowcount:restored_champions.append(sid)
    return {"strategy_stats":restored_stats,"eligible_strategy_ids":len(eligible),"champion_count_evidence":champion_count,"restored_champions":restored_champions}


def _backup_database(db_path:Path)->Path:
    backup_dir=db_path.parent/"backups";backup_dir.mkdir(parents=True,exist_ok=True)
    stamp=datetime.now(IST).strftime("%Y%m%d_%H%M%S")
    out=backup_dir/f"pre_support_recovery_{stamp}.db"
    src=sqlite3.connect(str(db_path));dst=sqlite3.connect(str(out))
    try:src.backup(dst)
    finally:dst.close();src.close()
    return out


def recover(bundle:Path,db_path:Path,apply:bool=False)->Dict[str,Any]:
    bundle=bundle.expanduser().resolve();db_path=db_path.expanduser().resolve()
    if not bundle.is_file():raise FileNotFoundError(bundle)
    digest=_sha256(bundle);marker=f"support_recovery_import:{digest}"
    with zipfile.ZipFile(bundle) as zf:
        names=set(zf.namelist());missing=[p for p in EXPORTS.values() if p not in names]
        if missing:raise ValueError(f"support bundle missing required exports: {missing}")
        preview={}
        for table,path in EXPORTS.items():
            with zf.open(path) as f:
                preview[table]=sum(1 for raw in f if raw.strip())
    result={"policy":POLICY,"bundle":str(bundle),"bundle_sha256":digest,"db":str(db_path),"apply":bool(apply),"export_rows":preview}
    if not apply:return result
    # The runtime package owns schema creation and the strategy catalogue.
    init_db();seed_library()
    if db_path!=DB_PATH:
        raise ValueError(f"--db must match runtime DB_PATH for this recovery build: {DB_PATH}")
    backup=_backup_database(db_path);result["pre_import_backup"]=str(backup)
    con=sqlite3.connect(str(db_path));con.row_factory=sqlite3.Row;con.execute("PRAGMA foreign_keys=ON")
    try:
        old=con.execute("SELECT value_json FROM system_state WHERE key=?",(marker,)).fetchone()
        if old:
            result["already_imported"]=True;result["previous_import"]=json.loads(old[0]);return result
        con.execute("BEGIN IMMEDIATE")
        imported={};skipped={};validation_rows=[];algorithm_rows=[]
        with zipfile.ZipFile(bundle) as zf:
            for table in ("recommendations","trade_decisions","scan_runs","institutional_snapshots","algorithm_versions"):
                n=0
                for row in _jsonl(zf,EXPORTS[table]):
                    if table=="algorithm_versions":algorithm_rows.append(row)
                    n+=1 if _insert_row(con,table,row,ignore=True,drop_id=table in AUTO_ID_TABLES) else 0
                imported[table]=n;skipped[table]=preview[table]-n
            n=0
            for row in _jsonl(zf,EXPORTS["strategy_validation_runs"]):
                validation_rows.append(row);n+=1 if _insert_validation(con,row) else 0
            imported["strategy_validation_runs"]=n;skipped["strategy_validation_runs"]=preview["strategy_validation_runs"]-n
            n=0
            for row in _jsonl(zf,EXPORTS["health_events"]):n+=1 if _insert_health(con,row) else 0
            imported["health_events"]=n;skipped["health_events"]=preview["health_events"]-n
            durable=0
            for row in _jsonl(zf,EXPORTS["system_state"]):
                if not _durable_state(str(row.get("key") or "")):continue
                con.execute("INSERT INTO system_state(key,value_json,updated_at) VALUES(?,?,?) ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json,updated_at=excluded.updated_at",(row.get("key"),row.get("value_json") or "{}",row.get("updated_at") or datetime.now(IST).isoformat(timespec="seconds")));durable+=1
        imported["system_state_durable"]=durable;skipped["system_state_transient"]=preview["system_state"]-durable
        strategy=_restore_strategy_evidence(con,validation_rows,algorithm_rows)
        summary={"policy":POLICY,"bundle_sha256":digest,"imported":imported,"skipped":skipped,"strategy_recovery":strategy,"at":datetime.now(IST).isoformat(timespec="seconds")}
        con.execute("INSERT INTO system_state(key,value_json,updated_at) VALUES(?,?,?)",(marker,json.dumps(summary,separators=(",",":"),default=str),summary["at"]))
        con.commit();result.update(summary);result["already_imported"]=False
    except Exception:
        con.rollback();raise
    finally:con.close()
    return result


def main()->int:
    ap=argparse.ArgumentParser(description="Restore sanitized PS Scanner audit/learning evidence from a support export without inventing missing runtime data.")
    ap.add_argument("bundle",type=Path)
    ap.add_argument("--db",type=Path,default=DB_PATH)
    ap.add_argument("--apply",action="store_true",help="Apply after preview. Without this flag the command is read-only.")
    args=ap.parse_args()
    out=recover(args.bundle,args.db,args.apply)
    print(json.dumps(out,indent=2,default=str))
    return 0


if __name__=="__main__":raise SystemExit(main())
