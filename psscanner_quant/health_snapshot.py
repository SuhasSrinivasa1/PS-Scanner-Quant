from __future__ import annotations

import copy
import json
import threading
import time
from typing import Any, Dict

from .constants import BOOKS
from .db import db, now_iso

_LOCK = threading.RLock()
_CACHE: Dict[str, Any] = {
    "ready": False,
    "refreshed_at": None,
    "last_attempt_at": None,
    "last_error": "not yet refreshed",
    "elapsed_ms": None,
    "order_count": None,
    "state": {},
    "recent": [],
    "recommendation_counts": [],
    "decision_counts_24h": {},
    "fundamentals": {"status":"WARMING","mode":"PROSPECTIVE_POINT_IN_TIME_CAPTURE"},
    "events": {"status":"WARMING","policy":"Only persisted timestamped events are used."},
}

def status() -> Dict[str, Any]:
    # Writers replace the complete snapshot under _LOCK. Passive readers never mutate
    # nested values, so a shallow copy avoids deep-copying full evidence/state payloads.
    with _LOCK:
        return dict(_CACHE)

def refresh() -> Dict[str, Any]:
    """Refresh the DB-backed health snapshot outside passive request paths.

    /api/health must never compete with full-breadth research for Python/SQLite time.
    The background worker owns these reads; HTTP callers consume the last complete
    snapshot and fail closed if no execution-critical snapshot has been produced yet.
    """
    started=time.monotonic();attempt=now_iso()
    state_keys=["last_regime","global_context","last_research_cycle","universe_status","full_breadth_discovery",
                "daily_history_warm_status","last_intraday_history_warm","live_price_cache_status",
                "position_reconciliation","last_verified_backup"]+["scan_status_"+b for b in BOOKS]
    try:
        from datetime import datetime
        from .constants import IST
        today=datetime.now(IST).date().isoformat()
        with db(timeout_seconds=.75) as con:
            order_count=int(con.execute(
                "SELECT COUNT(*) FROM orders WHERE substr(created_at,1,10)=? AND state NOT IN ('FAILED','CANCELLED')",(today,)
            ).fetchone()[0])
            marks=",".join("?" for _ in state_keys)
            state={}
            for row in con.execute(f"SELECT key,value_json FROM system_state WHERE key IN ({marks})",tuple(state_keys)).fetchall():
                try:state[str(row[0])]=json.loads(row[1] or "{}")
                except Exception:state[str(row[0])]={}
            recent=[dict(r) for r in con.execute(
                "SELECT ts,component,level,message FROM health_events ORDER BY id DESC LIMIT 30"
            ).fetchall()]
            recs=[{"book":r[0],"state":r[1],"n":r[2]} for r in con.execute(
                "SELECT book,state,COUNT(*) n FROM recommendations GROUP BY book,state"
            ).fetchall()]
            decisions={r[0]:r[1] for r in con.execute(
                "SELECT decision,COUNT(*) FROM trade_decisions WHERE ts>=datetime('now','-1 day') GROUP BY decision"
            ).fetchall()}
            f=con.execute("SELECT COUNT(*),COUNT(DISTINCT symbol),MIN(asof),MAX(asof) FROM fundamental_snapshots").fetchone()
            e=con.execute("SELECT COUNT(*),SUM(CASE WHEN starts_at>=? THEN 1 ELSE 0 END) FROM market_events",(now_iso(),)).fetchone()
        from .broker import broker
        from .orders import execution_readiness_cached_snapshot
        from .trading_calendar import status as trading_calendar_status
        from .sector_context import status_cached as sector_status_cached
        from .history_control import status_cached as history_control_status_cached
        groww=broker.status_cached()
        static_ip=broker.static_ip_status_cached()
        execution=execution_readiness_cached_snapshot(order_count,state.get("position_reconciliation") or {})
        snapshot={
            "ready":True,"refreshed_at":now_iso(),"last_attempt_at":attempt,"last_error":None,
            "elapsed_ms":round((time.monotonic()-started)*1000.0,1),"order_count":order_count,"state":state,
            "recent":recent,"recommendation_counts":recs,"decision_counts_24h":decisions,
            "groww":groww,"static_ip":static_ip,"execution":execution,
            "trading_calendar":trading_calendar_status(),"sector_breadth":sector_status_cached(),
            "history_control":history_control_status_cached(),
            "fundamentals":{
                "snapshots":int(f[0] or 0),"symbols":int(f[1] or 0),"first_asof":f[2],"last_asof":f[3],
                "mode":"PROSPECTIVE_POINT_IN_TIME_CAPTURE","bounded":True,
                "historical_backtest_policy":"Only snapshots captured by the decision timestamp are eligible; current fundamentals are never backfilled into the past.",
            },
            "events":{
                "total_events":int(e[0] or 0),"future_events":int(e[1] or 0),"bounded":True,
                "policy":"Only persisted timestamped events are used. Missing macro data remains UNKNOWN rather than assumed safe.",
            },
        }
        with _LOCK:_CACHE.clear();_CACHE.update(snapshot)
    except Exception as exc:
        with _LOCK:
            _CACHE["last_attempt_at"]=attempt
            _CACHE["last_error"]=str(exc)[:180]
    return status()
