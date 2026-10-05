from __future__ import annotations

import json
import sys
import tempfile
import time
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from psscanner_quant import data, db as dbmod, execution_integrity as xi, fundamentals, history_control, regime


class V6814TomorrowReadinessTests(unittest.TestCase):
    def test_background_history_yields_during_provider_cooldown(self):
        old=history_control._GLOBAL_COOLDOWN_UNTIL
        try:
            history_control._GLOBAL_COOLDOWN_UNTIL=time.time()+30
            with patch("psscanner_quant.history_control.load_settings",return_value={"history_min_request_interval_seconds":2.0}):
                permit=history_control.background_request_allowed()
            self.assertFalse(permit["allowed"])
            self.assertGreater(permit["cooldown_remaining_seconds"],0)
        finally:
            history_control._GLOBAL_COOLDOWN_UNTIL=old

    def test_background_history_uses_zero_same_call_429_retries(self):
        with tempfile.TemporaryDirectory() as td:
            cache=Path(td)/"ABC.1day.json"
            seen=[]
            def fake_window(groww_symbol,interval,start,end,max_429):
                seen.append(max_429)
                return [],429,RuntimeError("429")
            settings={
                "daily_history_ttl_hours":12,"intraday_history_ttl_minutes":5,
                "history_429_max_retries":3,"history_daily_chunk_days":175,
                "history_daily_target_days":350,"history_daily_min_rows":220,
                "history_forbidden_quarantine_hours":6.0,
            }
            with patch.object(data,"instrument",return_value={"symbol":"ABC","groww_symbol":"NSE-ABC"}), \
                 patch.object(data,"_history_path",return_value=cache), \
                 patch.object(data,"load_settings",return_value=settings), \
                 patch.object(data,"quarantine_status",return_value={"quarantined":False}), \
                 patch.object(data,"_request_history_window",side_effect=fake_window), \
                 patch.object(data,"health"):
                data.history("ABC","1day",force=True,background=True)
            self.assertEqual(seen,[0])

    def test_connected_symbol_scoped_history_403_is_quarantined(self):
        with tempfile.TemporaryDirectory() as td:
            cache=Path(td)/"ABC.1day.json"
            settings={
                "daily_history_ttl_hours":12,"intraday_history_ttl_minutes":5,
                "history_429_max_retries":3,"history_daily_chunk_days":175,
                "history_daily_target_days":350,"history_daily_min_rows":220,
                "history_forbidden_quarantine_hours":6.0,
            }
            with patch.object(data,"instrument",return_value={"symbol":"ABC","groww_symbol":"NSE-ABC"}), \
                 patch.object(data,"_history_path",return_value=cache), \
                 patch.object(data,"load_settings",return_value=settings), \
                 patch.object(data,"quarantine_status",return_value={"quarantined":False}), \
                 patch.object(data,"_request_history_window",return_value=([],403,RuntimeError("403"))), \
                 patch.object(data.broker,"status_cached",return_value={"connected":True}), \
                 patch.object(data,"quarantine") as q:
                data.history("ABC","1day",force=True,background=True)
            q.assert_called_once()
            self.assertEqual(q.call_args.kwargs["status_code"],403)
            self.assertEqual(q.call_args.kwargs["hours"],6.0)

    def test_sparse_regime_remains_warming(self):
        syms=[f"S{i}" for i in range(1000)]
        summaries={
            "S0":{"recent_closes":[100.0]*30},
            "S1":{"recent_closes":[100.0]*30},
        }
        prices={"S0":110.0,"S1":90.0}
        with patch.object(regime,"full_nse_symbols",return_value=syms), \
             patch.object(regime,"history_summary_snapshot",return_value=summaries), \
             patch.object(regime,"set_state"):
            out=regime.classify(prices=prices,allow_network_prices=False,summaries=summaries)
        self.assertEqual(out["regime"],"WARMING")
        self.assertTrue(out["insufficient_sample"])
        self.assertFalse(out["ready_for_classification"])
        self.assertEqual(out["sample"],2)
        self.assertGreaterEqual(out["minimum_sample_required"],50)

    def test_unsupported_fundamental_negative_cache_survives_memory_reset(self):
        old_db=dbmod.DB_PATH
        old_cache=dict(fundamentals._NEGATIVE_CACHE)
        try:
            with tempfile.TemporaryDirectory() as td:
                dbmod.DB_PATH=Path(td)/"test.db"
                dbmod.init_db()
                fundamentals._NEGATIVE_CACHE.clear()
                class BadTicker:
                    @property
                    def info(self):
                        raise RuntimeError("HTTP Error 404: No fundamentals data found")
                fake=types.SimpleNamespace(Ticker=lambda _:BadTicker())
                with patch.dict(sys.modules,{"yfinance":fake}):
                    self.assertEqual(fundamentals.refresh("NOYAHOO"),{})
                with dbmod.db() as con:
                    row=con.execute("SELECT source FROM fundamentals_cache WHERE symbol='NOYAHOO'").fetchone()
                self.assertEqual(row[0],"YAHOO_UNSUPPORTED_NEGATIVE_CACHE")
                fundamentals._NEGATIVE_CACHE.clear()
                self.assertEqual(fundamentals.get_cached("NOYAHOO"),{})
                self.assertTrue(fundamentals._negative_cached("NOYAHOO"))
        finally:
            dbmod.DB_PATH=old_db
            fundamentals._NEGATIVE_CACHE.clear()
            fundamentals._NEGATIVE_CACHE.update(old_cache)

    def test_external_cnc_baseline_is_explicit_and_quantity_changes_reblock(self):
        old_db=dbmod.DB_PATH
        try:
            with tempfile.TemporaryDirectory() as td:
                dbmod.DB_PATH=Path(td)/"test.db"
                dbmod.init_db()
                first={"positions":[{"trading_symbol":"ABC","product":"CNC","quantity":10,"net_carry_forward_quantity":0}]}
                changed={"positions":[{"trading_symbol":"ABC","product":"CNC","quantity":11,"net_carry_forward_quantity":0}]}
                with patch.object(xi.broker,"positions",return_value=first):
                    out=xi.acknowledge_external_position_baseline("ACKNOWLEDGE_EXTERNAL_CNC_BASELINE")
                self.assertFalse(out["reconciliation"]["hard_block"])
                self.assertTrue(out["reconciliation"]["external_baseline_active"])
                with patch.object(xi.broker,"positions",return_value=changed):
                    out2=xi.reconcile_positions()
                self.assertTrue(out2["hard_block"])
                self.assertEqual(out2["mismatches"][0]["delta"],1)
        finally:
            dbmod.DB_PATH=old_db

    def test_external_mis_cannot_be_baselined(self):
        old_db=dbmod.DB_PATH
        try:
            with tempfile.TemporaryDirectory() as td:
                dbmod.DB_PATH=Path(td)/"test.db"
                dbmod.init_db()
                payload={"positions":[{"trading_symbol":"ABC","product":"MIS","quantity":-1,"net_carry_forward_quantity":0}]}
                with patch.object(xi.broker,"positions",return_value=payload):
                    with self.assertRaises(ValueError):
                        xi.acknowledge_external_position_baseline("ACKNOWLEDGE_EXTERNAL_CNC_BASELINE")
        finally:
            dbmod.DB_PATH=old_db

    def test_release_identity_and_static_ip_scope(self):
        from psscanner_quant.constants import VERSION
        self.assertEqual(VERSION,"6.8.14")
        main=(Path(__file__).resolve().parents[1]/"psscanner_quant/main.py").read_text()
        workflow=(Path(__file__).resolve().parents[1]/".github/workflows/ci.yml").read_text()
        self.assertIn('"build_commit":build_commit()',main)
        self.assertIn('printf \'%s\\n\' "$GITHUB_SHA" > "$STAGE/BUILD_COMMIT"',workflow)
        self.assertIn('"static_ip_policy":"EXECUTION_ONLY"',main)

    def test_external_baseline_api_is_local_only_and_explicit(self):
        main=(Path(__file__).resolve().parents[1]/"psscanner_quant/main.py").read_text()
        self.assertIn('/api/execution/positions/acknowledge-external-baseline',main)
        self.assertIn('host not in ("127.0.0.1","::1","localhost")',main)
        self.assertIn("ACKNOWLEDGE_EXTERNAL_CNC_BASELINE",(Path(__file__).resolve().parents[1]/"psscanner_quant/execution_integrity.py").read_text())


if __name__=="__main__":
    unittest.main()
