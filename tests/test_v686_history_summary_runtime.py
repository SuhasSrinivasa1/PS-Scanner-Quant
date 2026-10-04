import inspect
import unittest
from unittest.mock import patch

from psscanner_quant import data, db as dbmod, engine as engine_mod, institutional_intelligence as inst, regime, sector_context
from psscanner_quant.constants import VERSION


class V686HistorySummaryRuntimeTests(unittest.TestCase):
    def test_version(self):
        self.assertEqual(VERSION, "6.8.11")

    def test_schema_has_compact_history_summary_index(self):
        self.assertIn("CREATE TABLE IF NOT EXISTS history_summaries", dbmod.SCHEMA)
        self.assertIn("PRIMARY KEY(symbol, interval)", dbmod.SCHEMA)

    def test_full_breadth_uses_summary_without_runtime_candle_reparse(self):
        summaries={
            "AAA":{"daily_rows":40,"intraday_rows":35,"recent_closes":[90.0,100.0]},
            "BBB":{"daily_rows":10,"intraday_rows":0,"recent_closes":[50.0]},
        }
        with patch.object(data,"full_nse_symbols",return_value=["AAA","BBB"]), patch.object(data,"set_state"):
            with patch.object(data,"_load_raw_candles",side_effect=AssertionError("full breadth must not parse history files")):
                out=data.full_breadth_discovery_snapshot({"AAA":102.0,"BBB":49.0},summaries=summaries)
        self.assertEqual(out["evaluated"],2)
        self.assertEqual(out["daily_history_ready"],1)
        self.assertEqual(out["intraday_history_ready"],1)
        self.assertEqual(out["history_source"],"SQLITE_HISTORY_SUMMARY_INDEX")

    def test_regime_reuses_same_summary_snapshot(self):
        closes=[100.0+i*.2 for i in range(60)]
        summaries={"AAA":{"daily_rows":60,"recent_closes":closes}}
        with patch.object(regime,"full_nse_symbols",return_value=["AAA"]), patch.object(regime,"set_state"):
            with patch.object(regime,"_recent_closes",side_effect=AssertionError("regime must not parse candle files")):
                out=regime.classify(prices={"AAA":113.0},allow_network_prices=False,summaries=summaries)
        self.assertEqual(out["history_ready"],1)
        self.assertEqual(out["history_source"],"SQLITE_HISTORY_SUMMARY_INDEX")

    def test_sector_breadth_uses_compact_summary_features(self):
        sector_context._CACHE={"at":0.0,"snapshot":{}}
        uni=[
            {"symbol":"AAA","industry":"Banks"},
            {"symbol":"BBB","industry":"Banks"},
            {"symbol":"CCC","industry":"IT"},
        ]
        summaries={
            "AAA":{"recent_closes":[100+i for i in range(30)]},
            "BBB":{"recent_closes":[90+i*.8 for i in range(30)]},
            "CCC":{"recent_closes":[70+i*.5 for i in range(30)]},
        }
        with patch.object(sector_context,"universe",return_value=uni), \
             patch.object(sector_context,"history_summary_snapshot",return_value=summaries), \
             patch.object(sector_context,"set_state"):
            out=sector_context.build_snapshot(ttl_seconds=0)
        self.assertIn("Banks",out)
        self.assertIn("IT",out)
        self.assertGreater(out["Banks"]["sample"],0)

    def test_large_deal_watp_is_normalized_to_value(self):
        payload={"bulk_deals":[{"symbol":"ABC","buySell":"BUY","qty":"350000","watp":"116.75","clientName":"FUND"}]}
        rows=inst._parse_large_deals(payload)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["price"],116.75)
        self.assertEqual(rows[0]["value_rupees"],40862500.0)

    def test_market_snapshot_shares_one_summary_read(self):
        src=inspect.getsource(engine_mod.Engine._market_snapshot)
        self.assertIn("summaries=history_summary_snapshot(syms)",src)
        self.assertIn("full_breadth_discovery_snapshot(prices,summaries=summaries)",src)
        self.assertIn("summaries=summaries",src)

    def test_installer_backfills_before_launch(self):
        from pathlib import Path
        root=Path(__file__).resolve().parents[1]
        src=(root/"install.sh").read_text()
        self.assertIn("backfill_history_summaries",src)
        backfill=src.index("backfill_history_summaries")
        launch_block=src.index('mkdir -p "$HOME/Library/LaunchAgents"',backfill)
        self.assertLess(backfill,launch_block)


if __name__ == "__main__":
    unittest.main()
