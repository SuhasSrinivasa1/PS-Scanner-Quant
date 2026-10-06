from __future__ import annotations

import inspect
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from psscanner_quant.constants import VERSION
from psscanner_quant import specialized
from psscanner_quant.engine import Engine


class V6815ETFFunnelReadinessTests(unittest.TestCase):
    def test_version(self):
        self.assertEqual(VERSION,"6.8.15")

    def test_etf_universe_uses_canonical_classification_and_normalized_market_fields(self):
        rows=[
            {"exchange":"nse","segment":"cash","instrument_type":"EQ","series":"EQ",
             "trading_symbol":"NIFTYBEES","name":"Nifty Bees"},
            {"exchange":"NSE","segment":"CASH","instrument_type":"EQ","series":"EQ",
             "trading_symbol":"GOLDBEES","name":"Gold ETF"},
            {"exchange":"NSE","segment":"CASH","instrument_type":"EQ","series":"EQ",
             "trading_symbol":"ABC","name":"ABC Limited"},
            {"exchange":"BSE","segment":"CASH","instrument_type":"ETF","series":"EQ",
             "trading_symbol":"BSEETF","name":"BSE ETF"},
        ]
        with patch.object(specialized,"instrument_rows",return_value=rows):
            self.assertEqual(specialized._etf_symbols(),["NIFTYBEES","GOLDBEES"])

    def test_etf_history_warmer_uses_background_pacer_contract(self):
        class ThirtyRows:
            def __len__(self): return 30
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"NIFTYBEES.1day.json"
            with patch.object(specialized,"_etf_symbols",return_value=["NIFTYBEES"]), \
                 patch.object(specialized,"_history_path",return_value=p), \
                 patch.object(specialized,"_load_raw_candles",return_value=[]), \
                 patch.object(specialized,"background_request_allowed",return_value={"allowed":True}), \
                 patch.object(specialized,"history",return_value=ThirtyRows()) as hist, \
                 patch.object(specialized,"get_state",return_value=0), \
                 patch.object(specialized,"set_state"):
                out=specialized.warm_etf_history(1)
        hist.assert_called_once_with("NIFTYBEES","1day",allow_network=True,background=True)
        self.assertEqual(out["attempted"],1)
        self.assertEqual(out["universe"],1)
        self.assertEqual(out["policy"],"DEDICATED_ETF_BACKGROUND_HISTORY_V6815")

    def test_etf_history_producer_is_scheduled_independently(self):
        method=inspect.getsource(Engine._etf_history)
        supervise=inspect.getsource(Engine._supervise)
        self.assertIn("warm_etf_history",method)
        self.assertIn('"etf_history"',supervise)
        self.assertIn("etf_history_worker_interval_seconds",supervise)

    def test_etf_scan_reports_truthful_standard_funnel_even_before_cache_exists(self):
        captured={}
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"NIFTYBEES.1day.json"
            def save(key,value):
                captured[key]=value
            with patch.object(specialized,"_etf_symbols",return_value=["NIFTYBEES"]), \
                 patch.object(specialized,"_history_path",return_value=p), \
                 patch.object(specialized,"live_prices",return_value={}), \
                 patch.object(specialized,"instrument_rows",return_value=[]), \
                 patch.object(specialized,"fabric_prime_symbol_context",return_value={"policy":"TEST"}), \
                 patch.object(specialized,"get_state",return_value={}), \
                 patch.object(specialized,"set_state",side_effect=save):
                self.assertEqual(specialized.scan_etfs(sides=("LONG",)),[])
        detail=captured["scan_detail_ETF"]
        self.assertEqual(detail["universe_total"],1)
        self.assertEqual(detail["history_path_missing"],1)
        self.assertEqual(detail["funnel"]["scan_scope_total"],0)
        self.assertEqual(detail["funnel"]["history_ready"],0)
        self.assertEqual(detail["funnel"]["raw_eligible"],0)
        self.assertEqual(detail["funnel"]["publication_ready"],0)
        self.assertEqual(detail["funnel"]["published"],0)

    def test_ui_distinguishes_explicit_zero_from_unreported_stage(self):
        html=(Path(__file__).resolve().parents[1]/"static/index.html").read_text()
        self.assertIn("function funnelReported",html)
        self.assertIn("v===null?'—'",html)
        self.assertIn("0 = backend explicitly reported zero",html)
        self.assertIn("— = this stage has not reported telemetry yet",html)
        self.assertIn("ETF history warming",html)

    def test_scanner_status_plural_alias_is_backward_compatible(self):
        src=(Path(__file__).resolve().parents[1]/"psscanner_quant/main.py").read_text()
        self.assertIn('@app.get("/api/scan/status")',src)
        self.assertIn('@app.get("/api/scans/status",include_in_schema=False)',src)

    def test_risk_and_static_ip_scope_are_unchanged(self):
        constants=(Path(__file__).resolve().parents[1]/"psscanner_quant/constants.py").read_text()
        main=(Path(__file__).resolve().parents[1]/"psscanner_quant/main.py").read_text()
        self.assertIn("TRADE_NOTIONAL_RUPEES = 20_000.0",constants)
        self.assertIn("MAX_RUPEE_RISK_PER_TRADE = 500.0",constants)
        self.assertIn('"static_ip_policy":"EXECUTION_ONLY"',main)


if __name__=="__main__":
    unittest.main()
