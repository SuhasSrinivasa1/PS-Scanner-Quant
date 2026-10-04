from __future__ import annotations

import json
import math
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Tuple

from .constants import IST, GLOBAL_INDIA_FREEZE_TIME, SHORT_HARD_EXIT
from .config import load_settings
from .data import universe, history, liquidity_rank, full_nse_symbols, history_summary_snapshot
from .db import db, get_state, now_iso, set_state, health
from .features import latest_features
from .fundamentals import get as fundamentals_get
from .trade_intelligence import evaluate as evaluate_trade_intelligence
from .evidence_fabric import symbol_context as fabric_symbol_context
from .trading_calendar import is_regular_trading_day, next_trading_day

# Sector/global-driver mapping. Matching is intentionally broad because the NIFTY500
# Industry field is not perfectly normalized across constituents.
DRIVER_RULES: List[Tuple[Tuple[str,...], Tuple[str,...]]] = [
    (("information technology","software","it services","computer","telecom"), ("NASDAQ","US_TECH","US_SEMIS","MSFT","ORCL","NVDA")),
    (("bank","financial","finance","insurance","nbfc"), ("US_FINANCIALS","US_BANKS","JPM","GS","BAC","SP500","USDINR")),
    (("oil","gas","petroleum","refinery","energy"), ("US_ENERGY","XOM","SHEL","CRUDE","NATGAS","DXY")),
    (("metal","mining","steel","aluminium","copper","zinc"), ("US_MATERIALS","BHP","RIO","COPPER","GOLD","DXY")),
    (("pharma","health","hospital","biotech","life science"), ("US_HEALTH","LLY","NVO","SP500","DXY")),
    (("auto","automobile","tyre","transport equipment"), ("US_DISCRETIONARY","TSLA","TM","NIKKEI225","DAX","CRUDE")),
    (("consumer","retail","textile","fmcg","food","beverage"), ("US_DISCRETIONARY","US_STAPLES","SP500","CRUDE")),
    (("industrial","capital goods","engineering","construction","infrastructure"), ("US_INDUSTRIALS","DAX","COPPER","CRUDE")),
    (("chemical","fertilizer","materials"), ("US_MATERIALS","CRUDE","NATGAS","DXY")),
    (("realty","real estate","housing"), ("SP500","US_FINANCIALS","DXY")),
]
DEFAULT_DRIVERS=("SP500","NASDAQ","STOXX50","NIKKEI225","HANGSENG","USDINR")


def _target_trade_date(now:datetime|None=None):
    now=now or datetime.now(IST)
    t=now.time().replace(tzinfo=None)
    if is_regular_trading_day(now.date()) and t < SHORT_HARD_EXIT:
        return now.date()
    return next_trading_day(now.date())


def _drivers(industry:str)->Tuple[str,...]:
    text=str(industry or '').lower()
    for needles,labels in DRIVER_RULES:
        if any(n in text for n in needles):return labels
    return DEFAULT_DRIVERS


def _driver_score(labels:Tuple[str,...], moves:Dict[str,float]) -> Tuple[float,List[Dict[str,Any]]]:
    vals=[];evidence=[]
    for lab in labels:
        if lab not in moves:continue
        mv=float(moves[lab]);
        # USDINR/DXY often act inversely for import-sensitive sectors; we keep them low weight
        # rather than pretending a universal sign relationship.
        w=.55 if lab in ("USDINR","DXY") else 1.0
        vals.append(mv*w);evidence.append({'driver':lab,'move_pct':round(mv,3),'weight':w})
    if not vals:return 0.0,evidence
    return sum(vals)/max(1,sum((x.get('weight') or 1.0) for x in evidence)),evidence


def _calibration_adjustment(side:str)->float:
    """Small bounded adjustment only after a meaningful resolved sample.

    Cross-market outcomes can inform the overnight cue, but they never directly promote an
    Indian Champion strategy. Until 30 resolved calls exist, calibration is exactly zero.
    """
    book='GLOBAL_INDIA_LONG' if side=='LONG' else 'GLOBAL_INDIA_SHORT'
    try:
        with db() as con:
            rows=con.execute("SELECT result FROM recommendations WHERE book=? AND state='CLOSED' AND result IN ('WIN','LOSS','MISS') ORDER BY closed_at DESC LIMIT 120",(book,)).fetchall()
        n=len(rows)
        if n<30:return 0.0
        wins=sum(1 for r in rows if r[0]=='WIN')
        wr=wins/n
        return max(-3.0,min(3.0,(wr-.5)*10.0))
    except Exception:return 0.0


def _global_india_summary_features(summary:Dict[str,Any])->Dict[str,float]|None:
    """Return exact close-only fields used by the Global->India necessary prefilter.

    The detailed scanner still computes the authoritative pandas feature set for every
    survivor. These values only prove when a symbol cannot possibly clear the unchanged
    score gate, even after granting the maximum ADX contribution.
    """
    rows=int((summary or {}).get("daily_rows") or 0)
    closes=[float(x) for x in ((summary or {}).get("recent_closes") or []) if x is not None]
    if rows<60 or len(closes)<50:return None
    px=float(closes[-1] or 0)
    if px<=0 or len(closes)<21:return None
    base=float(closes[-21] or 0)
    if base<=0:return None
    ret20=(px/base-1.0)*100.0
    sma20=sum(closes[-20:])/20.0
    sma50=sum(closes[-50:])/50.0
    trend=1.0 if px>sma20>sma50 else (-1.0 if px<sma20<sma50 else 0.0)
    return {"close":px,"ret20":ret20,"trend":trend}


def _global_india_score_ceiling(aligned:float, trend:float, side:str, calibration:float)->float:
    sign=1 if str(side).upper()=="LONG" else -1
    trend_ok=sign*float(trend)>=0
    return 68+min(16,float(aligned)*9)+(7 if trend_ok else -4)+7+float(calibration)


def _global_india_possible_sides(row:Dict[str,Any], summary:Dict[str,Any],
                                 moves:Dict[str,Any], calibration:Dict[str,float])->Dict[str,Any]|None:
    f=_global_india_summary_features(summary)
    if not f:return None
    labels=_drivers(str(row.get("industry") or "UNKNOWN"));cue,evidence=_driver_score(labels,moves)
    if not evidence:return None
    own=float(f["ret20"])/20.0
    combined=.68*cue+.32*own
    possible=[]
    for side in ("LONG","SHORT"):
        sign=1 if side=="LONG" else -1
        aligned=sign*combined
        if aligned<=0.12:continue
        # Exact live formula contributes at most +7 from ADX. If the score cannot
        # reach 78 even with that maximum, detailed candle parsing cannot rescue it.
        ceiling=_global_india_score_ceiling(aligned,float(f["trend"]),side,float(calibration.get(side) or 0))
        if ceiling>=78:possible.append(side)
    if not possible:return None
    return {"sides":tuple(possible),"cue":cue,"evidence":evidence,"combined":combined}


def build_global_india_board() -> Dict[str,Any]:
    started=time.monotonic();now=datetime.now(IST);target=_target_trade_date(now);week_key=(now.date()-timedelta(days=now.weekday())).isoformat();g=get_state('global_context',{}) or {};moves=g.get('moves_pct') or {}
    settings=load_settings();max_side=max(1,min(10,int(settings.get('global_india_max_per_side',5))))
    syms=full_nse_symbols()
    meta={str(x.get('symbol') or '').upper():x for x in universe()}
    calibration={side:_calibration_adjustment(side) for side in ('LONG','SHORT')}

    # v6.8.8: full breadth remains unconditional, but the first pass uses the compact
    # persisted 60-close summary created in v6.8.6. No arbitrary Top-N cap is introduced.
    # A symbol reaches detailed pandas/candle work iff it can mathematically still clear
    # the existing score gate after granting the maximum possible ADX contribution.
    summaries=history_summary_snapshot(syms)
    detail_plan={}
    summary_ready=0
    for idx,sym in enumerate([str(x or '').upper() for x in syms if x],1):
        if idx%64==0:time.sleep(0)
        summary=summaries.get(sym) or {}
        if int(summary.get("daily_rows") or 0)>=60:summary_ready+=1
        row=meta.get(sym,{})
        possible=_global_india_possible_sides(row,summary,moves,calibration)
        if possible:detail_plan[sym]=possible

    set_state('scan_status_GLOBAL_INDIA',{'book':'GLOBAL_INDIA','running':True,'status':'DETAIL_ENRICHMENT',
        'stage':'DETAIL_ENRICHMENT','summary_evaluated':len(syms),'summary_ready':summary_ready,
        'detail_candidates':len(detail_plan),'target_session':target.isoformat(),'week_key':week_key,'at':now_iso(),
        'policy':'FULL_NSE_SUMMARY_NECESSARY_PREFILTER_NO_TOP_N_CAP'})

    candidates=[];detail_parsed=0
    for idx,(sym,plan) in enumerate(detail_plan.items(),1):
        if idx%8==0:time.sleep(0)
        try:df=history(sym,'1day',allow_network=False)
        except Exception:continue
        if len(df)<60:continue
        detail_parsed+=1
        f=latest_features(df);px=float(f.get('close') or 0)
        if px<=0:continue
        row=meta.get(sym,{})
        labels=_drivers(str(row.get('industry') or 'UNKNOWN'));cue,evidence=_driver_score(labels,moves)
        if not evidence:continue
        own=float(f.get('ret20') or 0)/20.0
        trend=float(f.get('trend') or 0)
        adx=float(f.get('adx14') or 0);atr=max(.15,float(f.get('atr_pct') or 1.0))
        combined=.68*cue+.32*own
        for side in plan.get("sides") or ():
            sign=1 if side=='LONG' else -1
            aligned=sign*combined
            if aligned<=0.12:continue
            trend_ok=sign*trend>=0
            score=68+min(16,aligned*9)+(7 if trend_ok else -4)+min(7,adx/8)+calibration[side]
            if score<78:continue
            target_pct=max(.55,min(3.0,atr*1.15+min(1.0,abs(combined))*.35))
            stop_pct=max(.35,min(1.8,target_pct/1.6))
            fund=fundamentals_get(sym,allow_refresh=False)
            shared=fabric_symbol_context(sym,book='GLOBAL_INDIA',side=side,features=f,fundamentals=fund)
            ti=evaluate_trade_intelligence(
                book='GLOBAL_INDIA',symbol=sym,side=side,features=f,fundamentals=fund,
                regime_state={'regime':'GLOBAL_OVERNIGHT','trend_vote':0.0,'breadth_up_pct':50.0,'breadth_down_pct':50.0},
                candle_info={},news=shared['news'],global_ctx=g,portfolio={},
                sector_ctx=shared['sector'],event_ctx=shared['events'],institutional_ctx=shared['institutional'],
                target_pct=target_pct,stop_pct=stop_pct,
                strategy_ids=['GLOBAL_SECTOR_CUE','GLOBAL_CROSS_ASSET','INDIA_DAILY_CONFIRM'],
                data_confidence=max(.55,min(.90,.60+min(20,len(evidence))*.01)),
            )
            if ti.get('decision')=='NO_TRADE':continue
            score=.80*score+.20*float(ti.get('score') or 0)
            candidates.append({'symbol':sym,'side':side,'score':round(score,2),'confidence':round(max(.52,min(.84,.55+abs(combined)*.08+min(20,len(evidence))*0.005)),3),'price':px,'features':f,'fundamentals':fund,'industry':row.get('industry') or 'UNKNOWN','driver_cue_pct':round(cue,3),'combined_cue_pct':round(combined,3),'drivers':evidence,'target_pct':round(target_pct,4),'stop_pct':round(stop_pct,4),'target_date':target.isoformat(),'trade_intelligence':ti,'institutional_context':shared['institutional'],'evidence_fabric_policy':shared['fabric_policy']})
    candidates.sort(key=lambda x:x['score'],reverse=True)
    runtime={'summary_evaluated':len(syms),'summary_ready':summary_ready,'detail_candidates':len(detail_plan),
             'detail_parsed':detail_parsed,'detail_parse_ratio':round(detail_parsed/max(1,len(syms)),4),
             'cooperative_yield':True,'elapsed_seconds':round(time.monotonic()-started,2),
             'policy':'FULL_NSE_SUMMARY_NECESSARY_PREFILTER_NO_TOP_N_CAP'}
    board={'generated_at':now_iso(),'target_session':target.isoformat(),'freeze_time_ist':'09:00','state':'FROZEN' if is_regular_trading_day(now.date()) and now.date()==target and now.time().replace(tzinfo=None)>=GLOBAL_INDIA_FREEZE_TIME else 'PROVISIONAL_OVERNIGHT','long':[x for x in candidates if x['side']=='LONG'][:max_side],'short':[x for x in candidates if x['side']=='SHORT'][:max_side],'global_context_generated_at':g.get('generated_at'),'global_coverage':g.get('coverage',len(moves)),'policy':'GLOBAL_MARKETS_TO_INDIA_WEEKLY_PREDICTION_DAILY_EVIDENCE_V689','week_key':week_key,'universe_scanned':len(syms),'runtime':runtime}
    set_state('global_india_board',board)
    return board


def freeze_global_india_board() -> int:
    from .engine import _insert_rec, period_key, _append_discovery_capacity
    now=datetime.now(IST);target=_target_trade_date(now);t=now.time().replace(tzinfo=None)
    # Weekly prediction freeze: first available NSE trading morning at/after 09:00.
    # If Monday is a holiday or the app was offline, the same week self-heals later
    # without rewriting or replacing any identity already published.
    if not (is_regular_trading_day(now.date()) and t>=GLOBAL_INDIA_FREEZE_TIME):return 0
    board=get_state('global_india_board',{}) or build_global_india_board()
    made=0
    for side,key,book in [('LONG','long','GLOBAL_INDIA_LONG'),('SHORT','short','GLOBAL_INDIA_SHORT')]:
        pk=period_key(book,now)
        with db() as con:
            rows=[dict(r) for r in con.execute(
                "SELECT symbol,created_at,rationale_json FROM recommendations WHERE book=? AND period_key=? AND COALESCE(result,'')<>'VOID'",
                (book,pk),
            ).fetchall()]
        existing={str(r.get('symbol') or '').upper() for r in rows}
        initial=not existing
        cap=_append_discovery_capacity(book,pk,now)
        allowance=len(board.get(key) or []) if initial else min(cap.get('remaining_total',0),cap.get('remaining_today',0))
        if allowance<=0:continue
        picks=[]
        for cand in board.get(key) or []:
            sym=str(cand.get('symbol') or '').upper()
            if not sym or sym in existing:continue
            ti=cand.get('trade_intelligence') or {};combo=ti.get('evidence_combination') or {}
            if not initial:
                if float(cand.get('score') or 0)<83.0:continue
                if str(combo.get('combination_state') or '') not in ('CONFIRMED','STRONG'):continue
            picks.append(cand)
        for cand in picks[:allowance]:
            rationale={'reasons':['major global-market alignment','industry-driver mapping','Indian stock daily-trend confirmation','shared institutional/technical evidence'],
                'mapping_type':'SECTOR_AND_CROSS_ASSET_NOT_NAIVE_EQUIVALENT','industry':cand.get('industry'),
                'global_drivers':cand.get('drivers'),'driver_cue_pct':cand.get('driver_cue_pct'),'combined_cue_pct':cand.get('combined_cue_pct'),
                'target_session_reference':target.isoformat(),'week_key':pk,'freeze_deadline_ist':'MONDAY_09:00',
                'data_confidence':cand.get('confidence'),'prediction_horizon':'NSE_TRADING_WEEK',
                'selection_phase':'INITIAL_FREEZE' if initial else 'APPEND_DISCOVERY','append_only':True,
                'initial_frozen_slate_preserved':True,'no_rank_replacement':True,
                'short_execution_policy':'BEARISH_WEEKLY_RESEARCH_MAY_ONLY_EXECUTE_AS_SAME_DAY_MIS_WITH_15:00_EXIT',
                'learning_policy':'Global outcomes are research evidence only; no direct Champion promotion without Indian OOS validation.',
                'trade_intelligence':ti,'institutional_context':cand.get('institutional_context'),
                'evidence_fabric_policy':cand.get('evidence_fabric_policy'),'publication_policy_version':'V689_GLOBAL_INDIA_WEEKLY_APPEND_ONLY'}
            rid=_insert_rec(book,cand['symbol'],side,cand['score'],cand['confidence'],cand['price'],cand['features'],
                'GLOBAL_WEEKLY',['GLOBAL_SECTOR_CUE','GLOBAL_CROSS_ASSET','INDIA_DAILY_CONFIRM'],rationale,
                exchange='NSE',target_pct_override=cand['target_pct'],stop_pct_override=cand['stop_pct'],period_key_override=pk)
            if rid:made+=1;existing.add(str(cand['symbol']).upper())
    if made:
        board=dict(board);board['state']='WEEKLY_FROZEN_APPEND_ONLY';board['frozen_at']=board.get('frozen_at') or now_iso()
        board['week_key']=period_key('GLOBAL_INDIA_LONG',now);set_state('global_india_board',board)
    return made


def run_global_india_cycle() -> int:
    try:
        board=build_global_india_board();made=freeze_global_india_board()
        set_state('scan_status_GLOBAL_INDIA',{'book':'GLOBAL_INDIA','running':False,'status':'OK','generated_at':board.get('generated_at'),'target_session':board.get('target_session'),'state':board.get('state'),'long':len(board.get('long') or []),'short':len(board.get('short') or []),'published':made,'runtime':board.get('runtime') or {},'at':now_iso()})
        return made
    except Exception as exc:
        health('global_india','WARN',str(exc)[:220]);set_state('scan_status_GLOBAL_INDIA',{'book':'GLOBAL_INDIA','status':'ERROR','error':str(exc)[:220],'at':now_iso()});return 0


def board_payload() -> Dict[str,Any]:
    from .engine import recommendations
    board=get_state('global_india_board',{}) or {}
    return {'provisional':board,'frozen_long':recommendations('GLOBAL_INDIA_LONG'),'frozen_short':recommendations('GLOBAL_INDIA_SHORT')}
