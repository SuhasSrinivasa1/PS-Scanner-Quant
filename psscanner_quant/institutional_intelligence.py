from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import time
from datetime import datetime, timedelta
from threading import RLock
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import urlencode

import requests

from .broker import broker
from .constants import IST
from .data import instrument_rows
from .db import db, health, get_state, now_iso, set_state
from .trading_calendar import is_regular_trading_day, previous_trading_day

POLICY = "V685_INSTITUTIONAL_DISCLOSURE_DELIVERY_DERIVATIVES_POINT_IN_TIME_SHADOW"
NSE_BASE = "https://www.nseindia.com"
NSE_ARCHIVE = "https://nsearchives.nseindia.com"
FII_DII_API = "/api/fiidiiTradeReact"
LARGE_DEAL_API = "/api/snapshot-capital-market-largedeal"
INSIDER_API = "/api/corporates-pit"
ANNOUNCEMENTS_API = "/api/corporate-announcements"

_LOCK=RLock()
_CACHE:Dict[str,Any]={}
_SESSION=requests.Session()
_SESSION.headers.update({
    "User-Agent":"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/125 Safari/537.36",
    "Accept":"application/json,text/plain,*/*",
    "Accept-Language":"en-US,en;q=0.9",
    "Referer":"https://www.nseindia.com/",
})


def _f(v:Any,default:float=0.0)->float:
    try:
        x=float(str(v).replace(",","").strip())
        return x if math.isfinite(x) else default
    except Exception:return default


def _nse_json(path:str,timeout:float=5.0)->Any:
    """Fetch one official NSE JSON resource from the dedicated background producer."""
    try:
        if not _SESSION.cookies:
            _SESSION.get(NSE_BASE,timeout=min(3.0,timeout))
    except Exception:
        pass
    r=_SESSION.get(NSE_BASE+path,timeout=timeout)
    r.raise_for_status()
    return r.json()


def _rows_any(payload:Any)->List[Dict[str,Any]]:
    if isinstance(payload,list):return [dict(x) for x in payload if isinstance(x,dict)]
    if isinstance(payload,dict):
        preferred=("data","rows","fiiDii","fii_dii","insiderTrading","announcements","value")
        for k in preferred:
            v=payload.get(k)
            if isinstance(v,list):return [dict(x) for x in v if isinstance(x,dict)]
        for _,v in payload.items():
            if isinstance(v,list) and any(isinstance(x,dict) for x in v):
                return [dict(x) for x in v if isinstance(x,dict)]
    return []


def _flow_rows(payload:Any)->List[Dict[str,Any]]:
    return _rows_any(payload)


def _parse_flows(payload:Any)->Dict[str,Any]:
    rows=_flow_rows(payload);out={}
    for r in rows:
        label=str(r.get("category") or r.get("type") or r.get("clientType") or r.get("name") or "").upper()
        if "FII" in label or "FPI" in label:key="FII_FPI"
        elif "DII" in label:key="DII"
        else:continue
        buy=_f(r.get("buyValue") if r.get("buyValue") is not None else r.get("buy_value"))
        sell=_f(r.get("sellValue") if r.get("sellValue") is not None else r.get("sell_value"))
        net=_f(r.get("netValue") if r.get("netValue") is not None else r.get("net_value"),buy-sell)
        out[key]={"buy_crore":buy,"sell_crore":sell,"net_crore":net,
                  "date":r.get("date") or r.get("tradeDate") or r.get("asOnDate"),"raw":r}
    return out


def _iter_lists(obj:Any,path:str="")->Iterable[tuple[str,List[Dict[str,Any]]]]:
    if isinstance(obj,dict):
        for k,v in obj.items():
            p=f"{path}.{k}" if path else str(k)
            if isinstance(v,list) and any(isinstance(x,dict) for x in v):
                yield p,[dict(x) for x in v if isinstance(x,dict)]
            else:
                yield from _iter_lists(v,p)
    elif isinstance(obj,list):
        for i,v in enumerate(obj):
            yield from _iter_lists(v,f"{path}[{i}]")


def _parse_large_deals(payload:Any)->List[Dict[str,Any]]:
    out=[]
    for path,rows in _iter_lists(payload):
        lp=path.lower()
        kind="BLOCK" if "block" in lp else ("BULK" if "bulk" in lp else ("SHORT_SELL" if "short" in lp else "LARGE_DEAL"))
        for r in rows:
            sym=str(r.get("symbol") or r.get("tradingSymbol") or r.get("security") or "").upper()
            if not sym:continue
            side=str(r.get("buySell") or r.get("buy_sell") or r.get("side") or r.get("transactionType") or "").upper()
            qty=_f(r.get("quantity") if r.get("quantity") is not None else r.get("qty"))
            px=_f(r.get("price") if r.get("price") is not None else r.get("tradePrice"))
            client=str(r.get("clientName") or r.get("client") or r.get("name") or "")
            out.append({"symbol":sym,"kind":kind,"side":side,"quantity":qty,"price":px,
                        "value_rupees":round(qty*px,2) if qty and px else None,"client":client[:160],"raw":r})
    seen=set();dedup=[]
    for x in out:
        key=(x["symbol"],x["kind"],x["side"],x["quantity"],x["price"],x["client"])
        if key in seen:continue
        seen.add(key);dedup.append(x)
    return dedup


def _pick(row:Dict[str,Any],*names:str)->Any:
    lower={str(k).strip().lower():v for k,v in row.items()}
    for name in names:
        if name in row and row.get(name) not in (None,""):return row.get(name)
        v=lower.get(str(name).strip().lower())
        if v not in (None,""):return v
    return None


def _fetch_delivery_snapshot(now:datetime)->Dict[str,Any]:
    """Fetch NSE's latest published security-wise deliverable data.

    During an active NSE session the current day's report does not exist yet, so use
    the prior trading session until the normal post-market publication window.
    """
    candidate=now.date()
    if is_regular_trading_day(candidate) and now.hour < 18:
        candidate=candidate-timedelta(days=1)
    d=previous_trading_day(candidate)
    url=f"{NSE_ARCHIVE}/products/content/sec_bhavdata_full_{d.strftime('%d%m%Y')}.csv"
    r=requests.get(url,timeout=8,headers={"User-Agent":_SESSION.headers.get("User-Agent","Mozilla/5.0")})
    r.raise_for_status()
    text=r.content.decode("utf-8-sig",errors="ignore")
    rows={}
    for raw in csv.DictReader(io.StringIO(text)):
        row={str(k).strip():v for k,v in raw.items() if k is not None}
        sym=str(_pick(row,"SYMBOL","symbol") or "").strip().upper()
        if not sym:continue
        deliverable=_f(_pick(row,"DELIV_QTY","DELIVERABLE QTY","deliverable_qty"),-1)
        pct=_f(_pick(row,"DELIV_PER","% DLY QT TO TRADED QTY","DELIV_PER%","delivery_pct"),-1)
        traded=_f(_pick(row,"TTL_TRD_QNTY","TOTTRDQTY","TRD_QTY","traded_qty"),-1)
        if deliverable<0 and pct<0:continue
        rows[sym]={"date":d.isoformat(),"deliverable_qty":None if deliverable<0 else deliverable,
                   "delivery_pct":None if pct<0 else pct,"traded_qty":None if traded<0 else traded,
                   "source":"NSE_FULL_BHAVCOPY_SECURITY_DELIVERABLE_DATA"}
    return {"date":d.isoformat(),"symbols":rows,"count":len(rows),"source_url":url}


def _fetch_recent_disclosures(now:datetime)->Dict[str,Any]:
    start=(now.date()-timedelta(days=14)).strftime("%d-%m-%Y");end=now.date().strftime("%d-%m-%Y")
    q=urlencode({"index":"equities","from_date":start,"to_date":end})
    pit_rows=[];ann_rows=[];errors=[]
    try:
        payload=_nse_json(f"{INSIDER_API}?{q}",6.0)
        for r in _rows_any(payload)[:2500]:
            sym=str(_pick(r,"symbol","Symbol") or "").upper()
            if not sym:continue
            pit_rows.append({
                "symbol":sym,"person":str(_pick(r,"acqName","name","personName") or "")[:160],
                "person_category":str(_pick(r,"personCategory","category") or "")[:120],
                "transaction_type":str(_pick(r,"tdpTransactionType","transactionType","buySell") or "")[:80],
                "securities_acquired_disposed":_f(_pick(r,"secAcq","securitiesAcquiredDisposed","quantity"),0),
                "transaction_value":_f(_pick(r,"secVal","value"),0),
                "date":_pick(r,"date","acqfromDt","transactionDate","broadcastDate"),
                "source":"NSE_SEBI_PIT_REGULATION_7_2","raw":r,
            })
    except Exception as exc:errors.append("insider_pit:"+str(exc)[:160])
    try:
        payload=_nse_json(f"{ANNOUNCEMENTS_API}?{q}",6.0)
        for r in _rows_any(payload)[:3000]:
            sym=str(_pick(r,"symbol","sm_name","Symbol") or "").upper()
            subject=str(_pick(r,"subject","desc","description","attchmntText") or "").strip()
            text=(subject+" "+str(_pick(r,"remark","details") or "")).lower()
            kind=None;severity="INFO"
            if any(k in text for k in ("pledge","encumbrance","regulation 31","reg 31")):
                kind="PLEDGE_ENCUMBRANCE";severity="RISK_REVIEW"
            elif any(k in text for k in ("insider trading","regulation 7(2)","regulation 7 (2)","pit regulation")):
                kind="INSIDER_DISCLOSURE"
            elif any(k in text for k in ("regulation 29","reg 29","substantial acquisition","sast","acquisition and disposal")):
                kind="SAST_OWNERSHIP_CHANGE"
            elif any(k in text for k in ("fraud","forensic","insolvency","default","auditor resignation","resignation of auditor","show cause","penalty","regulatory action")):
                kind="GOVERNANCE_RISK";severity="RISK_REVIEW"
            if not kind:continue
            ann_rows.append({"symbol":sym,"kind":kind,"severity":severity,"subject":subject[:300],
                             "broadcast_at":_pick(r,"an_dt","broadcastDate","broadcast_date","date"),
                             "attachment":_pick(r,"attchmntFile","attachment","fileName"),"source":"NSE_CORPORATE_ANNOUNCEMENTS","raw":r})
    except Exception as exc:errors.append("regulatory_announcements:"+str(exc)[:160])
    return {"window_days":14,"insider_transactions":pit_rows,"regulatory_announcements":ann_rows,"errors":errors}


def _fno_rows_by_underlying()->Dict[str,List[Dict[str,Any]]]:
    out:Dict[str,List[Dict[str,Any]]]={}
    for r in instrument_rows():
        if str(r.get("exchange") or "").upper()!="NSE" or str(r.get("segment") or "").upper()!="FNO":continue
        u=str(r.get("underlying_symbol") or "").upper().strip()
        if u:out.setdefault(u,[]).append(r)
    return out


def _derivative_snapshot(symbols:Iterable[str],old:Dict[str,Any],now:datetime,max_symbols:int=6,wall_clock_budget_seconds:float=60.0)->Dict[str,Any]:
    """Capture bounded live option positioning for priority FNO underlyings only."""
    fno=_fno_rows_by_underlying();result={};attempted=0;errors=[]
    old_ctx=dict(old.get("derivatives") or {})
    budget=max(10.0,min(float(wall_clock_budget_seconds or 60.0),120.0))
    started=time.monotonic();deadline=started+budget;budget_exhausted=False
    for sym in list(dict.fromkeys(str(x or "").upper() for x in symbols if x)):
        if time.monotonic() >= deadline:
            budget_exhausted=True
            break
        rows=fno.get(sym) or []
        if not rows:continue
        expiries=sorted({str(r.get("expiry_date") or "")[:10] for r in rows if str(r.get("expiry_date") or "")[:10]>=now.date().isoformat()})
        if not expiries:continue
        expiry=expiries[0];attempted+=1
        try:
            chain=broker.option_chain(sym,expiry,"NSE")
            strikes=chain.get("strikes") if isinstance(chain,dict) else {}
            strikes=strikes if isinstance(strikes,dict) else {}
            ce_oi=pe_oi=ce_vol=pe_vol=0.0;ce_ivs=[];pe_ivs=[]
            underlying=_f(chain.get("underlying_ltp"))
            nearest=[]
            for k,v in strikes.items():
                if not isinstance(v,dict):continue
                try:dist=abs(float(k)-underlying) if underlying>0 else 0.0
                except Exception:dist=1e99
                nearest.append((dist,v))
                ce=v.get("CE") or {};pe=v.get("PE") or {}
                ce_oi+=_f(ce.get("open_interest"));pe_oi+=_f(pe.get("open_interest"))
                ce_vol+=_f(ce.get("volume"));pe_vol+=_f(pe.get("volume"))
            for _,v in sorted(nearest,key=lambda x:x[0])[:7]:
                ce=v.get("CE") or {};pe=v.get("PE") or {}
                civ=_f((ce.get("greeks") or {}).get("iv"),-1);piv=_f((pe.get("greeks") or {}).get("iv"),-1)
                if civ>=0:ce_ivs.append(civ)
                if piv>=0:pe_ivs.append(piv)
            fut=[r for r in rows if str(r.get("expiry_date") or "")[:10]==expiry and (str(r.get("instrument_type") or "").upper()=="FUT" or str(r.get("trading_symbol") or "").upper().endswith("FUT"))]
            future_ltp=None;basis=None
            if fut:
                fq=broker.quote(str(fut[0].get("trading_symbol") or ""),"NSE","FNO")
                future_ltp=_f(fq.get("last_price") or fq.get("ltp"),0) or None
                if future_ltp and underlying>0:basis=round((future_ltp/underlying-1)*100,4)
            prev=old_ctx.get(sym) or {}
            total_oi=ce_oi+pe_oi;prev_oi=_f(prev.get("total_oi"),0)
            result[sym]={"expiry":expiry,"underlying_ltp":underlying or None,
                "call_oi":round(ce_oi,2),"put_oi":round(pe_oi,2),"total_oi":round(total_oi,2),
                "oi_change_since_prior_snapshot":round(total_oi-prev_oi,2) if prev_oi else None,
                "pcr_oi":round(pe_oi/ce_oi,4) if ce_oi>0 else None,
                "call_volume":round(ce_vol,2),"put_volume":round(pe_vol,2),
                "pcr_volume":round(pe_vol/ce_vol,4) if ce_vol>0 else None,
                "atm_call_iv":round(sum(ce_ivs)/len(ce_ivs),4) if ce_ivs else None,
                "atm_put_iv":round(sum(pe_ivs)/len(pe_ivs),4) if pe_ivs else None,
                "iv_skew_put_minus_call":round((sum(pe_ivs)/len(pe_ivs))-(sum(ce_ivs)/len(ce_ivs)),4) if ce_ivs and pe_ivs else None,
                "nearest_future_ltp":future_ltp,"futures_basis_pct":basis,
                "captured_at":now_iso(),"source":"GROWW_LIVE_OPTION_CHAIN_AND_FNO_QUOTE","scoring_mode":"SHADOW_ONLY_UNTIL_OOS_VALIDATED"}
        except Exception as exc:errors.append(f"{sym}:"+str(exc)[:120])
        if attempted>=max_symbols:break
    return {"symbols":result,"attempted":attempted,"ready":len(result),"errors":errors,
            "budget_seconds":budget,"elapsed_seconds":round(time.monotonic()-started,2),
            "budget_exhausted":budget_exhausted,
            "policy":"BOUNDED_PRIORITY_FNO_POINT_IN_TIME_SHADOW_ONLY_HARD_WALL_CLOCK"}


def _persist_snapshot(payload:Dict[str,Any])->None:
    raw=json.dumps(payload,sort_keys=True,separators=(",",":"),default=str)
    digest=hashlib.sha256(raw.encode()).hexdigest()
    try:
        with db(timeout_seconds=1.0) as con:
            con.execute(
                "INSERT OR IGNORE INTO institutional_snapshots(snapshot_id,captured_at,source,payload_hash,payload_json) "
                "VALUES(?,?,?,?,?)",
                (digest[:32],payload.get("captured_at") or now_iso(),"NSE_GROWW_OFFICIAL_PLUS_LOCAL_OHLCV",digest,raw),
            )
    except Exception as exc:
        health("institutional_intelligence","WARN",f"snapshot persistence: {str(exc)[:160]}")


def refresh(force:bool=False,symbols:Optional[Iterable[str]]=None)->Dict[str,Any]:
    now=datetime.now(IST)
    with _LOCK:
        old=dict(_CACHE)
        try:
            ts=datetime.fromisoformat(str(old.get("captured_at"))) if old.get("captured_at") else None
            if ts and not force and now-ts<timedelta(minutes=5):return old
        except Exception:pass
    errors=[];flows={};deals=[];delivery={};disclosures={};derivatives={}
    try:flows=_parse_flows(_nse_json(FII_DII_API))
    except Exception as exc:errors.append("fii_dii:"+str(exc)[:180])
    try:deals=_parse_large_deals(_nse_json(LARGE_DEAL_API))
    except Exception as exc:errors.append("large_deals:"+str(exc)[:180])
    try:delivery=_fetch_delivery_snapshot(now)
    except Exception as exc:errors.append("delivery:"+str(exc)[:180])
    try:
        disclosures=_fetch_recent_disclosures(now);errors.extend(disclosures.get("errors") or [])
    except Exception as exc:errors.append("disclosures:"+str(exc)[:180])
    try:derivatives=_derivative_snapshot(symbols or [],old,now)
    except Exception as exc:errors.append("derivatives:"+str(exc)[:180])
    out={
        "captured_at":now_iso(),"flows":flows,"large_deals":deals[:1200],"large_deal_count":len(deals),
        "delivery":delivery,"disclosures":disclosures,"derivatives":derivatives.get("symbols") or {},
        "derivatives_status":{k:v for k,v in derivatives.items() if k!="symbols"},
        "status":"READY" if (flows or deals or delivery or disclosures or derivatives.get("symbols")) else ("STALE_FALLBACK" if old else "UNAVAILABLE"),
        "errors":errors,"policy":POLICY,
        "sources":{
            "fii_dii":"NSE FII/FPI & DII trading activity",
            "large_deals":"NSE Bulk/Block Deals & Short Selling",
            "delivery":"NSE Full Bhavcopy and Security Deliverable data",
            "insider":"NSE SEBI PIT Regulation 7(2) disclosures",
            "regulatory":"NSE corporate announcements classified for pledge/SAST/governance events",
            "derivatives":"Groww live option chain (OI/volume/IV/Greeks) plus nearest FNO future quote",
        },
        "scope_note":"Direct disclosures, deliverable volume and derivatives are kept distinct from inferred OHLCV accumulation. Newly added evidence is shadow/advisory until validated out of sample.",
    }
    for key in ("flows","large_deals","delivery","disclosures","derivatives"):
        if not out.get(key) and old.get(key):out[key]=old.get(key)
    out["large_deal_count"]=len(out.get("large_deals") or [])
    with _LOCK:
        _CACHE.clear();_CACHE.update(out)
    set_state("institutional_intelligence",out);_persist_snapshot(out)
    if errors:health("institutional_intelligence","WARN","; ".join(errors)[:240])
    return dict(out)

def cached_status()->Dict[str,Any]:
    with _LOCK:
        if _CACHE:return dict(_CACHE)
    state=get_state("institutional_intelligence",{}) or {}
    if state:
        with _LOCK:
            if not _CACHE:_CACHE.update(dict(state))
            return dict(_CACHE)
    return {}


def _deal_signal(symbol:str,deals:List[Dict[str,Any]])->Dict[str,Any]:
    sym=symbol.upper();rows=[x for x in deals if str(x.get("symbol") or "").upper()==sym]
    buy=sell=0.0
    for x in rows:
        val=_f(x.get("value_rupees"),_f(x.get("quantity"))*_f(x.get("price")))
        side=str(x.get("side") or "").upper()
        if "BUY" in side or side in ("B","PURCHASE"):buy+=val
        elif "SELL" in side or side in ("S","SALE"):sell+=val
    net=buy-sell
    return {"rows":rows[:20],"buy_value_rupees":round(buy,2),"sell_value_rupees":round(sell,2),
            "net_value_rupees":round(net,2),"direction":"BUY" if net>0 else ("SELL" if net<0 else "NEUTRAL")}


def _ownership_change(symbol:str)->Dict[str,Any]:
    try:
        with db(timeout_seconds=.35) as con:
            rs=con.execute("SELECT asof,payload_json FROM fundamental_snapshots WHERE symbol=? ORDER BY asof DESC LIMIT 12",(symbol.upper(),)).fetchall()
        vals=[]
        for r in rs:
            try:
                d=json.loads(r[1] or "{}");v=d.get("heldPercentInstitutions")
                if v is not None:vals.append((r[0],float(v)))
            except Exception:continue
        if not vals:return {"status":"UNKNOWN","reason":"no point-in-time institutional ownership snapshots"}
        latest=vals[0]
        older=next((x for x in vals[1:] if x[1]!=latest[1]),None)
        return {"status":"READY","latest_asof":latest[0],"latest":latest[1],
                "prior_asof":older[0] if older else None,"prior":older[1] if older else None,
                "change":round(latest[1]-older[1],6) if older else None,
                "policy":"PROSPECTIVE_CAPTURE_ONLY_NO_HISTORICAL_BACKFILL"}
    except Exception as exc:return {"status":"UNKNOWN","reason":str(exc)[:120]}


def context(symbol:str, *, features:Optional[Dict[str,Any]]=None,
            fundamentals:Optional[Dict[str,Any]]=None)->Dict[str,Any]:
    """Return auditable institutional/accumulation evidence without making identity claims."""
    state=cached_status();features=features or {};fundamentals=fundamentals or {};sym=symbol.upper()
    cmf=_f(features.get("cmf20"));mfi=_f(features.get("mfi14"),50.0);obv=_f(features.get("obv_trend5"))
    vr=_f(features.get("volume_ratio"),1.0);ownership=_f(fundamentals.get("heldPercentInstitutions"),-1)
    deal=_deal_signal(sym,list(state.get("large_deals") or []))
    technical=max(-30,min(30,cmf*100.0))+max(-20,min(20,(mfi-50.0)*0.8))+max(-20,min(20,obv*20.0))+max(-10,min(10,(vr-1.0)*8.0))
    deal_net=_f(deal.get("net_value_rupees"));direct=0.0
    if deal_net:direct=(1 if deal_net>0 else -1)*min(20.0,4.0+math.log10(max(1.0,abs(deal_net)))*2.0)
    flows=state.get("flows") or {};market_net=_f((flows.get("FII_FPI") or {}).get("net_crore"))+_f((flows.get("DII") or {}).get("net_crore"))
    market_context=max(-6.0,min(6.0,market_net/1000.0));score=max(-100.0,min(100.0,technical+direct+market_context))
    available=sum([1 if features.get("cmf20") is not None else 0,1 if features.get("mfi14") is not None else 0,
                   1 if features.get("obv_trend5") is not None else 0,1 if ownership>=0 else 0,1 if deal.get("rows") else 0])
    confidence=min(1.0,available/5.0);direction="ACCUMULATION" if score>=18 else ("DISTRIBUTION" if score<=-18 else ("NEUTRAL" if available else "UNKNOWN"))
    delivery=((state.get("delivery") or {}).get("symbols") or {}).get(sym)
    disc=state.get("disclosures") or {}
    insiders=[x for x in (disc.get("insider_transactions") or []) if str(x.get("symbol") or "").upper()==sym][:20]
    regs=[x for x in (disc.get("regulatory_announcements") or []) if str(x.get("symbol") or "").upper()==sym][:20]
    derivatives=(state.get("derivatives") or {}).get(sym)
    governance_risk=[x for x in regs if x.get("kind") in ("PLEDGE_ENCUMBRANCE","GOVERNANCE_RISK")]
    return {
        "symbol":sym,"direction":direction,"score":round(score,2),"confidence":round(confidence,3),
        "accumulation_indicators":{"cmf20":round(cmf,4),"mfi14":round(mfi,2),"obv_trend5":round(obv,4),"volume_ratio":round(vr,3)},
        "institutional_ownership":None if ownership<0 else round(ownership,5),"institutional_ownership_change":_ownership_change(sym),"large_deal_evidence":deal,
        "market_flow":{"FII_FPI":flows.get("FII_FPI"),"DII":flows.get("DII"),"combined_net_crore":round(market_net,2),"score_contribution":round(market_context,2)},
        "delivery_evidence":delivery,"insider_transactions":insiders,"regulatory_disclosures":regs,
        "governance_risk_disclosures":governance_risk,"derivatives_positioning":derivatives,
        "new_evidence_scoring_mode":"SHADOW_ONLY_UNTIL_INCREMENTAL_OOS_VALUE_IS_VALIDATED",
        "source_status":state.get("status") or "UNKNOWN","captured_at":state.get("captured_at"),"policy":POLICY,
        "identity_caution":"OHLCV accumulation does not identify the buyer; direct NSE disclosures are kept separate from inferred behavior.",
        "live_scoring_mode":"ADVISORY_UNTIL_CHALLENGER_OOS_PROMOTION",
        "v685_new_evidence_mode":"DISCLOSURE_DELIVERY_DERIVATIVES_SHADOW_ONLY",
    }

def point_in_time_history(limit:int=60)->List[Dict[str,Any]]:
    try:
        with db(timeout_seconds=.5) as con:
            rs=con.execute("SELECT captured_at,source,payload_json FROM institutional_snapshots ORDER BY captured_at DESC LIMIT ?",(max(1,min(int(limit),500)),)).fetchall()
        out=[]
        for r in rs:
            try:p=json.loads(r[2] or "{}")
            except Exception:p={}
            out.append({"captured_at":r[0],"source":r[1],"payload":p})
        return out
    except Exception:return []
