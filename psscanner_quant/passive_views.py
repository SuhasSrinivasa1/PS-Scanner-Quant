from __future__ import annotations

import copy
import json
import os
import threading
import time
from pathlib import Path
from typing import Any, Dict, Iterable

from .constants import VERSION
from .db import get_state, now_iso
from .paths import DATA

_PERF_PATH=DATA/"passive_performance_views.json"
_INTL_PATH=DATA/"passive_international_view.json"
_LOCK=threading.RLock()
_PERF:Dict[str,Any]={"ready":False,"refreshed_at":None,"last_error":"not yet refreshed","views":{}}
_INTL:Dict[str,Any]={"ready":False,"refreshed_at":None,"last_error":"not yet refreshed","payload":{}}

UI_PERFORMANCE_GROUPS=("book","strategy","family","side","regime","time_bucket","behavior_cluster","month")
PERFORMANCE_LIMITS=(1000,10000)


def _atomic_json(path:Path,payload:Dict[str,Any])->None:
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+".tmp")
    tmp.write_text(json.dumps(payload,separators=(",",":"),default=str))
    os.replace(tmp,path)


def _load(path:Path)->Dict[str,Any]:
    try:
        if path.exists():
            d=json.loads(path.read_text())
            return d if isinstance(d,dict) else {}
    except Exception:
        pass
    return {}


def prime()->Dict[str,Any]:
    """Restore last complete passive UI views without querying SQLite."""
    p=_load(_PERF_PATH);i=_load(_INTL_PATH)
    with _LOCK:
        if p.get("version")==VERSION and isinstance(p.get("views"),dict) and p.get("views"):
            _PERF.clear();_PERF.update(p)
        if i.get("version")==VERSION and isinstance(i.get("payload"),dict) and i.get("payload"):
            _INTL.clear();_INTL.update(i)
    return status()


def status()->Dict[str,Any]:
    with _LOCK:
        return {
            "performance":{"ready":bool(_PERF.get("ready")),"refreshed_at":_PERF.get("refreshed_at"),"last_error":_PERF.get("last_error"),"view_count":len(_PERF.get("views") or {})},
            "international":{"ready":bool(_INTL.get("ready")),"refreshed_at":_INTL.get("refreshed_at"),"last_error":_INTL.get("last_error")},
        }


def _age_seconds(raw:Any)->float|None:
    try:
        from datetime import datetime
        dt=datetime.fromisoformat(str(raw))
        return max(0.0,time.time()-dt.timestamp())
    except Exception:
        return None


def refresh_performance()->Dict[str,Any]:
    """Build all website performance groupings off-request from one DB snapshot."""
    started=time.monotonic();attempt=now_iso()
    try:
        from .analytics import performance
        views={}
        for limit in PERFORMANCE_LIMITS:
            for group_by in UI_PERFORMANCE_GROUPS:
                out=performance(group_by=group_by,limit=limit,budget_seconds=None,db_timeout_seconds=10.0)
                out["performance_contract"]={**(out.get("performance_contract") or {}),
                    "background_precomputed":True,"passive_cached_source":True}
                views[f"{group_by}|{limit}"]=out
                time.sleep(0)
        payload={"version":VERSION,"ready":True,"refreshed_at":now_iso(),"last_attempt_at":attempt,"last_error":None,
                 "elapsed_ms":round((time.monotonic()-started)*1000.0,1),"views":views,
                 "policy":"V681_COMPLETE_ANALYTICS_PRECOMPUTED_FOR_PASSIVE_UI_VIEWS"}
        _atomic_json(_PERF_PATH,payload)
        with _LOCK:_PERF.clear();_PERF.update(payload)
    except Exception as exc:
        with _LOCK:
            _PERF["last_attempt_at"]=attempt;_PERF["last_error"]=str(exc)[:240]
    return performance_status()


def performance_status()->Dict[str,Any]:
    with _LOCK:
        return {"ready":bool(_PERF.get("ready")),"refreshed_at":_PERF.get("refreshed_at"),
                "last_error":_PERF.get("last_error"),"elapsed_ms":_PERF.get("elapsed_ms"),
                "view_count":len(_PERF.get("views") or {})}


def cached_performance(group_by:str="book",limit:int=10000)->Dict[str,Any]:
    g=str(group_by or "book").lower();requested=max(100,min(int(limit or 10000),50000))
    with _LOCK:
        ready=bool(_PERF.get("ready"));refreshed=_PERF.get("refreshed_at");err=_PERF.get("last_error")
        views=_PERF.get("views") or {}
        exact=views.get(f"{g}|{requested}")
        if exact:
            out=copy.deepcopy(exact)
            age=_age_seconds(refreshed)
            out["performance_contract"]={**(out.get("performance_contract") or {}),
                "passive_cached":True,"request_path_db_connections":0,"cache_refreshed_at":refreshed,
                "cache_age_seconds":round(age,2) if age is not None else None}
            return out
        # If the complete cached ledger has fewer rows than the caller's requested
        # limit, a larger cached limit is semantically identical and can be reused.
        for cache_limit in sorted(PERFORMANCE_LIMITS):
            cand=views.get(f"{g}|{cache_limit}")
            if cand and int(cand.get("rows_scanned") or 0)<requested and int(cand.get("rows_scanned") or 0)<cache_limit:
                out=copy.deepcopy(cand);age=_age_seconds(refreshed)
                out["requested_limit"]=requested
                out["performance_contract"]={**(out.get("performance_contract") or {}),
                    "passive_cached":True,"request_path_db_connections":0,"cache_refreshed_at":refreshed,
                    "cache_age_seconds":round(age,2) if age is not None else None,
                    "cache_limit_used":cache_limit}
                return out
    return {
        "generated_at":now_iso(),"book":None,"group_by":g,"status":"CACHE_WARMING" if not ready else "CACHE_LIMIT_NOT_PRECOMPUTED",
        "complete":False,"rows_scanned":0,"requested_limit":requested,"total":{},"groups":[],
        "degraded_reason":err or "Passive performance view is awaiting a matching complete background snapshot.",
        "performance_contract":{"passive_cached":True,"request_path_db_connections":0,"network_calls":False,
                                "cache_refreshed_at":refreshed,"partial_rows_published":False},
    }


def refresh_international()->Dict[str,Any]:
    """Build the complete International/Global->India page off the HTTP request path."""
    started=time.monotonic();attempt=now_iso()
    try:
        from .engine import recommendations
        from .cross_market import board_payload
        payload={
            "us_long":recommendations("INTERNATIONAL"),
            "global_to_india":board_payload(),
            "us_scan":get_state("scan_status_INTERNATIONAL",{}) or {},
            "global_india_scan":get_state("scan_status_GLOBAL_INDIA",{}) or {},
        }
        state={"version":VERSION,"ready":True,"refreshed_at":now_iso(),"last_attempt_at":attempt,"last_error":None,
               "elapsed_ms":round((time.monotonic()-started)*1000.0,1),"payload":payload,
               "policy":"BACKGROUND_COMPLETE_INTERNATIONAL_VIEW_HTTP_DB_FREE"}
        _atomic_json(_INTL_PATH,state)
        with _LOCK:_INTL.clear();_INTL.update(state)
    except Exception as exc:
        with _LOCK:
            _INTL["last_attempt_at"]=attempt;_INTL["last_error"]=str(exc)[:240]
    return international_status()


def international_status()->Dict[str,Any]:
    with _LOCK:
        return {"ready":bool(_INTL.get("ready")),"refreshed_at":_INTL.get("refreshed_at"),
                "last_error":_INTL.get("last_error"),"elapsed_ms":_INTL.get("elapsed_ms")}


def cached_international()->Dict[str,Any]:
    with _LOCK:
        ready=bool(_INTL.get("ready"));refreshed=_INTL.get("refreshed_at");err=_INTL.get("last_error")
        payload=copy.deepcopy(_INTL.get("payload") or {})
    age=_age_seconds(refreshed)
    payload["cache_contract"]={
        "ready":ready,"passive_cached":True,"request_path_db_connections":0,"network_calls":False,
        "refreshed_at":refreshed,"age_seconds":round(age,2) if age is not None else None,"last_error":err,
    }
    if not ready:
        payload.setdefault("us_long",{"book":"INTERNATIONAL","live":{"long":[],"short":[]},"closed":[]})
        payload.setdefault("global_to_india",{"provisional":{},"frozen_long":{"live":{"long":[]}},"frozen_short":{"live":{"short":[]}}})
        payload.setdefault("us_scan",{"status":"CACHE_WARMING"})
        payload.setdefault("global_india_scan",{"status":"CACHE_WARMING"})
    return payload
