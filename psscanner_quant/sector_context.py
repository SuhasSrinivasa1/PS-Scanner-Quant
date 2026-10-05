from __future__ import annotations

import statistics
import time
from datetime import datetime
from threading import RLock
from typing import Any, Dict, List

from .data import universe, history_summary_snapshot
from .db import health, get_state, now_iso, set_state

_CACHE: Dict[str, Any] = {"at":0.0,"snapshot":{}}
_META_CACHE: Dict[str,str] = {}
_LOCK=RLock()


def prime_cache() -> Dict[str,Any]:
    """Restore the last complete sector snapshot outside passive request paths."""
    if _CACHE.get("snapshot"):return dict(_CACHE["snapshot"])
    try:
        state=get_state("sector_context_snapshot",{}) or {}
        snap=state.get("snapshot") if isinstance(state,dict) else {}
        if isinstance(snap,dict) and snap:
            captured=state.get("captured_at")
            try:captured_epoch=datetime.fromisoformat(str(captured)).timestamp()
            except Exception:captured_epoch=0.0
            _CACHE["snapshot"]=dict(snap);_CACHE["at"]=captured_epoch
    except Exception:
        pass
    return dict(_CACHE.get("snapshot") or {})


def _industry_map() -> Dict[str,List[str]]:
    out:Dict[str,List[str]]={}
    for r in universe():
        ind=str(r.get("industry") or r.get("sector") or "UNKNOWN").strip() or "UNKNOWN"
        if ind.upper()=="UNKNOWN":continue
        out.setdefault(ind,[]).append(str(r.get("symbol") or "").upper())
    return out


def _feat(sym:str,summaries:Dict[str,Dict[str,Any]])->Dict[str,Any]:
    """Compute the small sector-breadth feature set from compact daily summaries."""
    try:
        closes=[float(x) for x in ((summaries.get(sym) or {}).get("recent_closes") or []) if x is not None]
        if len(closes)<25:return {}
        close=closes[-1];prev=closes[-2] if len(closes)>=2 else close
        base20=closes[-21] if len(closes)>=21 else closes[0]
        last20=closes[-20:];last50=closes[-50:] if len(closes)>=50 else last20
        sma20=sum(last20)/len(last20);sma50=sum(last50)/len(last50)
        trend=1 if close>sma20>sma50 else (-1 if close<sma20<sma50 else 0)
        return {"close":close,"ret1":((close/prev)-1)*100 if prev>0 else 0.0,
                "ret20":((close/base20)-1)*100 if base20>0 else 0.0,
                "sma20":sma20,"trend":trend}
    except Exception:return {}


def build_snapshot(ttl_seconds:int=900, max_peers_per_industry:int=20) -> Dict[str,Any]:
    if not _CACHE["snapshot"]:prime_cache()
    if _CACHE["snapshot"] and time.time()-float(_CACHE["at"])<ttl_seconds:
        return _CACHE["snapshot"]
    with _LOCK:
        if _CACHE["snapshot"] and time.time()-float(_CACHE["at"])<ttl_seconds:
            return _CACHE["snapshot"]
        snap={}
        try:
            groups=_industry_map()
            all_syms=[s for syms in groups.values() for s in syms[:max_peers_per_industry]]
            summaries=history_summary_snapshot(all_syms)
            for industry,syms in groups.items():
                moves=[];ret20s=[];above20=0;trend_up=0;trend_down=0;n=0
                for s in syms[:max_peers_per_industry]:
                    f=_feat(s,summaries)
                    if not f:continue
                    n+=1;moves.append(float(f.get("ret1") or 0));ret20s.append(float(f.get("ret20") or 0))
                    if float(f.get("close") or 0)>float(f.get("sma20") or 1e99):above20+=1
                    tr=float(f.get("trend") or 0)
                    if tr>0:trend_up+=1
                    elif tr<0:trend_down+=1
                if n:
                    snap[industry]={"industry":industry,"sample":n,"members":len(syms),
                        "median_move_pct":round(statistics.median(moves),3) if moves else 0.0,
                        "median_ret20_pct":round(statistics.median(ret20s),3) if ret20s else 0.0,
                        "positive_pct":round(100*sum(1 for x in moves if x>0)/n,1),
                        "above_sma20_pct":round(100*above20/n,1),"trend_up_pct":round(100*trend_up/n,1),
                        "trend_down_pct":round(100*trend_down/n,1)}
        except Exception as exc:
            health("sector_context","WARN",str(exc)[:180])
        _CACHE["at"]=time.time();_CACHE["snapshot"]=snap
        if snap:set_state("sector_context_snapshot",{"captured_at":now_iso(),"snapshot":snap,
            "policy":"V686_COMPACT_HISTORY_SUMMARY_INDUSTRY_BREADTH"})
        return snap


def prime_symbol_meta(rows=None) -> Dict[str,str]:
    """Prime symbol->industry metadata once for cache-only scanner consumers."""
    global _META_CACHE
    with _LOCK:
        if rows is not None:
            for r in rows:
                sym=str((r or {}).get("symbol") or "").upper()
                if not sym:continue
                ind=str((r or {}).get("industry") or (r or {}).get("sector") or "UNKNOWN").strip() or "UNKNOWN"
                _META_CACHE[sym]=ind
        elif not _META_CACHE:
            for r in universe():
                sym=str(r.get("symbol") or "").upper()
                if sym:
                    _META_CACHE[sym]=str(r.get("industry") or r.get("sector") or "UNKNOWN").strip() or "UNKNOWN"
        return dict(_META_CACHE)


def _industry_for_symbol(symbol:str)->str:
    sym=str(symbol or "").upper()
    with _LOCK:
        ind=_META_CACHE.get(sym)
    if ind:return ind
    try:
        prime_symbol_meta()
        with _LOCK:return _META_CACHE.get(sym,"UNKNOWN")
    except Exception:return "UNKNOWN"


def context_from_features(symbol:str, side:str, features:Dict[str,Any]) -> Dict[str,Any]:
    """Compose sector evidence without a per-symbol SQLite history-summary read."""
    sym=symbol.upper();industry=_industry_for_symbol(sym);snap=dict(_CACHE.get("snapshot") or {});s=snap.get(industry) or {}
    try:stock_ret=float((features or {}).get("ret20") or 0)
    except Exception:stock_ret=0.0
    if not s:
        return {"status":"UNKNOWN","industry":industry,"reason":"sector peer snapshot not ready; scanner does not block to rebuild it"}
    sign=1 if side.upper()=="LONG" else -1
    supportive=(s.get("trend_up_pct",0)>=50 if sign>0 else s.get("trend_down_pct",0)>=50)
    relative=stock_ret-float(s.get("median_ret20_pct") or 0)
    return {**s,"status":"PASS" if supportive else "WARN","symbol":sym,"stock_ret20_pct":round(stock_ret,3),
            "stock_vs_industry_ret20_pct":round(relative,3),"supportive":supportive,
            "source":"FULL_NSE_MAPPED_INDUSTRY_PLUS_CACHED_DAILY_BREADTH_IN_MEMORY"}


def context(symbol:str, side:str="LONG", build_if_missing:bool=True, features:Dict[str,Any]|None=None) -> Dict[str,Any]:
    if features is not None:
        return context_from_features(symbol,side,features)
    sym=symbol.upper();industry=_industry_for_symbol(sym)
    snap=dict(_CACHE.get("snapshot") or {})
    if not snap and build_if_missing:snap=build_snapshot()
    s=snap.get(industry) or {};summaries=history_summary_snapshot([sym]);f=_feat(sym,summaries)
    if not s or not f:
        return {"status":"UNKNOWN","industry":industry,"reason":"sector peer snapshot not ready; scanner does not block to rebuild it"}
    sign=1 if side.upper()=="LONG" else -1;stock_ret=float(f.get("ret20") or 0)
    supportive=(s.get("trend_up_pct",0)>=50 if sign>0 else s.get("trend_down_pct",0)>=50)
    relative=stock_ret-float(s.get("median_ret20_pct") or 0)
    return {**s,"status":"PASS" if supportive else "WARN","symbol":sym,"stock_ret20_pct":round(stock_ret,3),"stock_vs_industry_ret20_pct":round(relative,3),"supportive":supportive,"source":"FULL_NSE_MAPPED_INDUSTRY_PLUS_CACHED_DAILY_BREADTH"}


def context_cached(symbol:str, side:str="LONG", features:Dict[str,Any]|None=None) -> Dict[str,Any]:
    return context(symbol,side,build_if_missing=False,features=features)

def status()->Dict[str,Any]:
    snap=build_snapshot();return {"industries_ready":len(snap),"source":"FULL_NSE_MAPPED_INDUSTRY_PLUS_CACHED_DAILY_BREADTH","top":sorted(snap.values(),key=lambda x:x.get("sample",0),reverse=True)[:20]}

def status_cached()->Dict[str,Any]:
    snap=dict(_CACHE.get("snapshot") or {})
    return {"industries_ready":len(snap),"source":"FULL_NSE_MAPPED_INDUSTRY_PLUS_CACHED_DAILY_BREADTH","top":sorted(snap.values(),key=lambda x:x.get("sample",0),reverse=True)[:20],"cached":True,"cache_age_seconds":round(max(0.0,time.time()-float(_CACHE.get("at") or 0)),1) if _CACHE.get("at") else None}
