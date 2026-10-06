from __future__ import annotations

import json
import tempfile
import unittest
from datetime import date, datetime as real_datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from psscanner_quant import data, db as dbmod, specialized
from psscanner_quant.constants import IST, VERSION


class V6815ProductionPathRegressions(unittest.TestCase):
    def test_cached_etf_resolves_through_production_history_lookup_and_becomes_ready(self):
        self.assertEqual(VERSION,"6.8.15")
        old_cache=data._CACHE
        captured={}
        try:
            with tempfile.TemporaryDirectory() as td:
                data._CACHE=Path(td)
                symbol="NIFTYBEES"
                path=data._history_path(symbol,"1day")
                start=real_datetime(2026,8,1,15,30,tzinfo=IST)
                candles=[]
                for i in range(35):
                    px=100.0+i*.25
                    candles.append([(start+timedelta(days=i)).isoformat(),px,px+1,px-1,px+.2,100000+i])
                path.write_text(json.dumps({"symbol":symbol,"interval":"1day","candles":candles}))
                rows=[{"exchange":"NSE","segment":"CASH","instrument_type":"EQ","series":"EQ",
                       "trading_symbol":symbol,"name":"Nifty Bees"}]
                def save(key,value):
                    captured[key]=value
                with patch.object(specialized,"instrument_rows",return_value=rows), \
                     patch.object(specialized,"live_prices",return_value={symbol:108.0}), \
                     patch.object(specialized,"latest_features",return_value={
                         "close":108.0,"trend":0.0,"ret20":0.0,"volume_ratio":0.0,"atr_pct":1.0
                     }), \
                     patch.object(specialized,"detect_patterns",return_value={}), \
                     patch.object(specialized,"fabric_prime_symbol_context",return_value={}), \
                     patch.object(specialized,"get_state",return_value={}), \
                     patch.object(specialized,"set_state",side_effect=save):
                    self.assertEqual(specialized.scan_etfs(sides=("LONG",)),[])
                detail=captured["scan_detail_ETF"]
                self.assertTrue(path.exists())
                self.assertEqual(detail["universe_total"],1)
                self.assertEqual(detail["history_path_missing"],0)
                self.assertEqual(detail["history_ready"],1)
                self.assertEqual(detail["funnel"]["history_ready"],1)
        finally:
            data._CACHE=old_cache

    def test_after_close_noop_preserves_existing_frozen_publication_status(self):
        old_db=dbmod.DB_PATH
        captured={}
        try:
            with tempfile.TemporaryDirectory() as td:
                dbmod.DB_PATH=Path(td)/"test.db"
                dbmod.init_db()
                target="2026-10-07"
                ts="2026-10-06T15:05:00+05:30"
                with dbmod.db() as con:
                    for i in range(5):
                        con.execute(
                            "INSERT INTO recommendations("
                            "recommendation_id,book,period_key,symbol,exchange,side,state,score,confidence,"
                            "entry_price,current_price,horizon,regime,strategy_ids_json,rationale_json,"
                            "feature_snapshot_json,data_confidence,created_at,updated_at,software_version"
                            ") VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                            (f"cnd-{i}","CIRCUIT_NEXTDAY",target,f"SYM{i}","NSE","LONG","LIVE",90.0,.9,
                             100.0,100.0,"NEXT_SESSION","NEXT_SESSION_CIRCUIT","[]","{}","{}",.9,ts,ts,VERSION),
                        )
                class FixedDateTime(real_datetime):
                    @classmethod
                    def now(cls,tz=None):
                        value=real_datetime(2026,10,6,16,5,tzinfo=IST)
                        return value if tz is not None else value.replace(tzinfo=None)
                def save(key,value):
                    captured[key]=value
                with patch.object(specialized,"datetime",FixedDateTime), \
                     patch.object(specialized,"next_trading_day",return_value=date(2026,10,7)), \
                     patch.object(specialized,"load_settings",return_value={}), \
                     patch.object(specialized,"_circuit_calibration",return_value={"sample":0}), \
                     patch.object(specialized,"set_state",side_effect=save):
                    self.assertEqual(specialized.run_circuit_nextday_cycle(),0)
                status=captured["scan_status_CIRCUIT_NEXTDAY"]
                self.assertEqual(status["status"],"ALREADY_FROZEN")
                self.assertEqual(status["window_status"],"FREEZE_WINDOW_CLOSED")
                self.assertEqual(status["published"],5)
                self.assertEqual(status["shortage"],0)
                self.assertFalse(status["recovery_required"])
                self.assertEqual(status["publication_source"],"PERSISTED_RECOMMENDATIONS")
                with dbmod.db() as con:
                    count=con.execute(
                        "SELECT COUNT(*) FROM recommendations WHERE book='CIRCUIT_NEXTDAY' AND period_key=? AND state='LIVE'",
                        (target,),
                    ).fetchone()[0]
                self.assertEqual(count,5)
        finally:
            dbmod.DB_PATH=old_db


if __name__=="__main__":
    unittest.main()
