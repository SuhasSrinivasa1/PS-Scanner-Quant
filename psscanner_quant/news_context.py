from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any, Dict, List
import time
from threading import RLock

from .constants import IST
from .db import db, health, now_iso, set_state

POSITIVE = {'beats','beat','surge','wins','order','contract','approval','approved','growth','upgrade','raises','record','profit','launch','expands','acquisition','buyback','dividend'}
NEGATIVE = {'misses','miss','falls','drop','fraud','probe','investigation','downgrade','cuts','loss','default','lawsuit','penalty','recall','warning','pledge','dilution'}
BINARY = {'earnings','results','merger','acquisition','court','regulator','approval','fda','board','guidance','offer','buyback'}
_MEM_CACHE:Dict[str,Dict[str,Any]]={}
_MEM_LOCK=RLock()


def prime_cache(symbols, ttl_minutes:int=30)->Dict[str,Dict[str,Any]]:
    """Load cached news for a scanner batch with bounded SQLite reads."""
    syms=[]
    for raw in symbols or []:
        s=str(raw or "").upper()
        if s and s not in syms:syms.append(s)
    if not syms:return {}
    cutoff=datetime.now(IST)-timedelta(minutes=ttl_minutes);out={}
    try:
        for pos in range(0,len(syms),800):
            chunk=syms[pos:pos+800];marks=",".join("?" for _ in chunk)
            with db(timeout_seconds=.35) as con:
                rows=con.execute(f"SELECT symbol,asof,payload_json FROM news_cache WHERE symbol IN ({marks})",tuple(chunk)).fetchall()
            for r in rows:
                try:
                    ts=datetime.fromisoformat(r['asof']);ts=ts if ts.tzinfo else ts.replace(tzinfo=IST)
                    if ts<cutoff:continue
                    out[str(r['symbol']).upper()]=json.loads(r['payload_json'] or '{}')
                except Exception:continue
    except Exception:pass
    with _MEM_LOCK:
        for s in syms:_MEM_CACHE[s]={"loaded_at":time.monotonic(),"payload":dict(out.get(s) or {})}
    return {s:dict(out.get(s) or {}) for s in syms}


def _cached(symbol:str, ttl_minutes:int=30)->Dict[str,Any]:
    sym=symbol.upper()
    with _MEM_LOCK:mem=dict(_MEM_CACHE.get(sym) or {})
    if mem and time.monotonic()-float(mem.get("loaded_at") or 0)<=min(60.0,max(5.0,ttl_minutes*60.0)):
        return dict(mem.get("payload") or {})
    with db() as con:r=con.execute('SELECT asof,payload_json FROM news_cache WHERE symbol=?',(sym,)).fetchone()
    if not r:return {}
    try:
        ts=datetime.fromisoformat(r['asof']);ts=ts if ts.tzinfo else ts.replace(tzinfo=IST)
        if datetime.now(IST)-ts>timedelta(minutes=ttl_minutes):return {}
        payload=json.loads(r['payload_json'] or '{}')
        with _MEM_LOCK:_MEM_CACHE[sym]={"loaded_at":time.monotonic(),"payload":dict(payload)}
        return payload
    except Exception:return {}

def context(symbol:str, allow_refresh:bool=False)->Dict[str,Any]:
    c=_cached(symbol)
    if c:return c
    if not allow_refresh:return {'status':'UNKNOWN','sentiment_score':0.0,'materiality':0.0,'headlines':[],'binary_event_risk':False,'source':'NOT_REFRESHED'}
    ticker=symbol.upper()+'.NS'
    headlines=[]
    try:
        import yfinance as yf
        items=(yf.Ticker(ticker).news or [])[:12]
        for item in items:
            content=item.get('content') if isinstance(item,dict) else None
            content=content if isinstance(content,dict) else item
            title=str((content or {}).get('title') or '').strip()
            if title:headlines.append(title[:280])
    except Exception as exc:
        health('news_context','WARN',f'{symbol}: {exc}')
    pos=neg=0;binary=False
    for h in headlines:
        words={w.strip('.,:;!?()[]{}\"\'').lower() for w in h.split()}
        pos+=len(words & POSITIVE);neg+=len(words & NEGATIVE);binary=binary or bool(words & BINARY)
    total=max(1,pos+neg)
    sent=(pos-neg)/total if headlines else 0.0
    material=min(1.0,(pos+neg)/4.0) if headlines else 0.0
    payload={'status':'READY' if headlines else 'NO_RECENT_NEWS','sentiment_score':round(sent,3),'materiality':round(material,3),'headlines':headlines[:5],'binary_event_risk':binary,'source':'YFINANCE_AGGREGATED_NEWS','asof':now_iso()}
    with db() as con:
        con.execute('INSERT INTO news_cache(symbol,asof,payload_json) VALUES(?,?,?) ON CONFLICT(symbol) DO UPDATE SET asof=excluded.asof,payload_json=excluded.payload_json',(symbol.upper(),now_iso(),json.dumps(payload,separators=(',',':'))))
    return payload


def refresh_batch(symbols, limit:int=12)->Dict[str,Any]:
    """Refresh a bounded shared priority batch; scanners themselves stay cache-only."""
    unique=[]
    for raw in symbols or []:
        sym=str(raw or "").upper()
        if sym and sym not in unique:unique.append(sym)
    chosen=unique[:max(0,min(int(limit),len(unique)))]
    ready=0;errors=0
    for sym in chosen:
        try:
            out=context(sym,allow_refresh=True)
            if out.get("status") in ("READY","NO_RECENT_NEWS"):ready+=1
            if out.get("status")=="UNKNOWN":errors+=1
        except Exception:
            errors+=1
    result={"attempted":len(chosen),"ready":ready,"errors":errors,"at":now_iso(),
            "policy":"V680_SHARED_PRIORITY_NEWS_PRODUCER_SCANNERS_CACHE_ONLY"}
    set_state("last_news_batch",result)
    return result
