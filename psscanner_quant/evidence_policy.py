from __future__ import annotations

from typing import Any, Dict

BOOK_PROFILES: Dict[str,Dict[str,Any]]={
 "INTRADAY":{"primary":["fresh intraday trend/VWAP","relative volume","liquidity/turnover"],"confirm":["institutional/accumulation","candlestick timing","news/event risk","sector breadth"],"macro":["USDINR","mapped sector/global proxy"],"institutional_role":"CONFIRMATION_HIGH_VALUE_NOT_STANDALONE"},
 "CIRCUIT":{"primary":["fresh same-session price/volume","verified circuit band/order imbalance","deadline capacity"],"confirm":["institutional/accumulation","candlestick timing","news/event catalyst","execution permission"],"macro":["sector/global shock"],"institutional_role":"CONFIRMATION_ONLY_NEVER_CIRCUIT_TRIGGER"},
 "WEEKLY":{"primary":["daily trend/momentum","target-capacity geometry","NIFTY relative strength"],"confirm":["institutional history/accumulation","sector leadership","news/events","candlestick structure"],"macro":["USDINR","oil","gold","silver","mapped global sector"],"institutional_role":"MULTI_SESSION_CONFIRMATION"},
 "ETF":{"primary":["ETF trend/momentum","regime alignment","volume/liquidity"],"confirm":["institutional/flow context where available","benchmark/sector leadership","news/events"],"macro":["global index/rates/commodity context"],"institutional_role":"SUPPORTING_NOT_REQUIRED_WHEN_NOT_APPLICABLE"},
 "MONTHLY":{"primary":["fundamentals","long-horizon trend/momentum","target-capacity geometry"],"confirm":["institutional ownership/history","sector breadth","news/events","cash-flow/quality"],"macro":["USDINR","oil","gold","silver","global sector/risk regime"],"institutional_role":"HIGH_VALUE_CONFIRMATION"},
 "INTERNATIONAL":{"primary":["US daily trend","multi-week momentum","net weekly edge after friction"],"confirm":["global risk regime","news/events","institutional/flow context"],"macro":["rates","DXY","oil","gold","major indices"],"institutional_role":"SUPPORTING_CONTEXT"},
 "GLOBAL_INDIA":{"primary":["global cross-asset driver","Indian daily confirmation","industry mapping"],"confirm":["institutional/accumulation","sector breadth","news/events"],"macro":["USDINR","oil","gold","silver","mapped global sector"],"institutional_role":"CONFIRMATION_NOT_STANDALONE"},
}

def _industry_dependencies(industry:str)->list[str]:
    x=str(industry or "").upper()
    rules=[
      (("JEWEL","GOLD","PRECIOUS"),["GOLD","SILVER","USDINR"]),
      (("OIL","GAS","PETROLEUM","REFIN"),["CRUDE","NATGAS","USDINR","DXY"]),
      (("METAL","MINING","STEEL","ALUMIN","COPPER"),["COPPER","GOLD","DXY","USDINR"]),
      (("CHEM","FERTIL"),["CRUDE","NATGAS","USDINR"]),
      (("AUTO","AUTOMOBILE","TYRE","TRANSPORT"),["CRUDE","USDINR","US_DISCRETIONARY"]),
      (("IT ","SOFTWARE","INFORMATION TECHNOLOGY","TECH"),["NASDAQ","US_TECH","USDINR"]),
      (("BANK","FINANCE","FINANCIAL","INSURANCE"),["US_FINANCIALS","USDINR","DXY"]),
      (("PHARMA","HEALTH","HOSPITAL"),["US_HEALTH","USDINR"]),
    ]
    out=[]
    for keys,deps in rules:
        if any(k in x for k in keys):
            for d in deps:
                if d not in out:out.append(d)
    return out

def combination_profile(book:str,side:str,features:Dict[str,Any],institutional:Dict[str,Any],
                        news:Dict[str,Any],global_ctx:Dict[str,Any],sector:Dict[str,Any],
                        candles:Dict[str,Any],fundamentals:Dict[str,Any])->Dict[str,Any]:
    b=str(book or "").upper();profile=BOOK_PROFILES.get(b,BOOK_PROFILES.get("GLOBAL_INDIA") if b.startswith("GLOBAL_INDIA") else BOOK_PROFILES["WEEKLY"])
    sign=1 if str(side).upper()=="LONG" else -1
    def f(v,d=0.0):
        try:return float(v)
        except Exception:return d
    inst_score=f(institutional.get("score"));inst_conf=f(institutional.get("confidence"))
    vr=f(features.get("volume_ratio"));trend=sign*f(features.get("trend"));ret20=sign*f(features.get("ret20"))
    news_sent=sign*f(news.get("sentiment_score"));news_mat=f(news.get("materiality"))
    candle_hits=[x for x in (candles.get("hits") or []) if str(x.get("direction") or "").upper()==str(side).upper()]
    supportive={
      "trend_momentum":bool(trend>0 and ret20>0),
      "volume":bool(vr>=1.10),
      "institutional":bool(inst_conf>0 and sign*inst_score>=18),
      "news":bool(news_mat>=.25 and news_sent>=0),
      "candlestick":bool(candle_hits),
      "sector":bool(sector.get("supportive")),
    }
    deps=_industry_dependencies(str(sector.get("industry") or ""))
    moves=global_ctx.get("moves_pct") or {}
    observed={k:moves.get(k) for k in deps if k in moves}
    confirmations=sum(1 for v in supportive.values() if v)
    return {
      "book":b,"profile":profile,"supportive_signals":supportive,"supportive_count":confirmations,
      "industry":sector.get("industry"),"commodity_fx_dependencies":deps,"observed_dependency_moves":observed,
      "institutional_is_standalone_trigger":False,
      "combination_state":"STRONG" if confirmations>=4 else ("CONFIRMED" if confirmations>=2 else "LIMITED"),
      "scoring_policy":"USES_EXISTING_VALIDATED_FILTER_WEIGHTS; COMBINATION LABEL IS AUDIT/ENSEMBLE CONTEXT UNTIL INCREMENTAL OOS VALIDATION",
    }

def profiles()->Dict[str,Any]:
    return {"policy":"BOOK_SPECIFIC_EVIDENCE_COMBINATIONS_V689","profiles":BOOK_PROFILES}
