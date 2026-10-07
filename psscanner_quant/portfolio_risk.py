from __future__ import annotations

from typing import Any, Dict, List

import numpy as np

from .data import history
from .db import db


def _return_series(symbol: str):
    """Load the bounded daily-return series used by the portfolio correlation gate."""
    try:
        d=history(symbol,'1day',allow_network=False)
        if len(d)<40 or 'close' not in d:return None
        r=d['close'].pct_change().dropna().tail(80)
        return r if len(r)>=25 else None
    except Exception:
        return None


def _corr_series(ra, rb) -> float:
    try:
        if ra is None or rb is None:return 0.0
        idx=ra.index.intersection(rb.index)
        if len(idx)<25:return 0.0
        c=float(np.corrcoef(ra.loc[idx].values,rb.loc[idx].values)[0,1])
        return c if np.isfinite(c) else 0.0
    except Exception:return 0.0


def _corr(a: str, b: str) -> float:
    return _corr_series(_return_series(a),_return_series(b))


def prepare_recommendation_cluster(symbols, side: str) -> Dict[str, Any]:
    """Prime one scan-local correlation snapshot.

    The former finalist path re-read the same daily-history files for every
    finalist/peer pair.  A 46-finalist x 20-peer pass could therefore parse
    roughly 1,840 history files.  This snapshot preserves the exact correlation
    gate while loading each unique symbol once for the scan.
    """
    side=str(side or '').upper()
    syms=[]
    for raw in symbols or []:
        s=str(raw or '').upper()
        if s and s not in syms:syms.append(s)
    with db() as con:
        rows=[dict(r) for r in con.execute(
            "SELECT recommendation_id,symbol,side,book FROM recommendations "
            "WHERE state='LIVE' AND exchange='NSE' AND side=?",
            (side,),
        ).fetchall()]
    load=list(syms)
    for r in rows:
        s=str(r.get('symbol') or '').upper()
        if s and s not in load:load.append(s)
    returns={s:_return_series(s) for s in load}
    return {
        'side':side,'rows':rows,'returns':returns,'symbols_loaded':len(load),
        'policy':'SCAN_LOCAL_BOUNDED_RETURN_SERIES_CACHE_V6816',
    }


def recommendation_cluster(symbol: str, side: str, exclude_id: str='', prepared: Dict[str, Any] | None=None) -> Dict[str, Any]:
    sym=symbol.upper();side=side.upper()
    if isinstance(prepared,dict) and str(prepared.get('side') or '').upper()==side:
        rs=[dict(r) for r in (prepared.get('rows') or []) if str(r.get('symbol') or '').upper()!=sym]
        returns=prepared.get('returns') or {}
        base=returns.get(sym)
    else:
        with db() as con:
            rs=[dict(r) for r in con.execute(
                "SELECT recommendation_id,symbol,side,book FROM recommendations "
                "WHERE state='LIVE' AND exchange='NSE' AND side=? AND symbol<>?",
                (side,sym),
            ).fetchall()]
        returns={};base=None
    peers=[]
    for r in rs[:20]:
        if exclude_id and r['recommendation_id']==exclude_id:continue
        peer=str(r.get('symbol') or '').upper()
        c=_corr_series(base,returns.get(peer)) if returns else _corr(sym,peer)
        if c>=0.70:peers.append({'symbol':r['symbol'],'book':r['book'],'correlation':round(c,3)})
    peers.sort(key=lambda x:x['correlation'],reverse=True)
    high=[x for x in peers if x['correlation']>=0.85]
    return {
        'symbol':sym,'side':side,'highly_correlated_open_recommendations':len(high),
        'correlated_peers':peers[:8],
        'hard_block':len(high)>=3,
        'reason':'THREE_OR_MORE_HIGHLY_CORRELATED_SAME_SIDE_RECOMMENDATIONS' if len(high)>=3 else '',
        'correlation_source':'PREPARED_SCAN_CACHE' if returns else 'DIRECT_CACHE_READ',
    }


def risk_summary() -> Dict[str, Any]:
    with db() as con:
        live=[dict(r) for r in con.execute("SELECT book,side,symbol,entry_price,current_price,target_pct,created_at FROM recommendations WHERE state='LIVE' ORDER BY book,side,score DESC").fetchall()]
        orders=[dict(r) for r in con.execute("SELECT symbol,side,product,quantity,limit_price,state,created_at FROM orders ORDER BY created_at DESC LIMIT 50").fetchall()]
    by_book={}
    for r in live:
        k=r['book'];by_book.setdefault(k,{'LONG':0,'SHORT':0});by_book[k][r['side']]=by_book[k].get(r['side'],0)+1
    return {'live_recommendations':len(live),'by_book':by_book,'recent_orders':orders[:20],'principle':'Correlation and concentration are evaluated separately from signal quality; several correlated positions are treated as one risk cluster.'}
