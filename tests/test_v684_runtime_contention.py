import inspect
import unittest
from unittest.mock import patch

from psscanner_quant import broker as broker_mod, data, engine as engine_mod
from psscanner_quant.broker import GrowwBroker
from psscanner_quant.constants import VERSION


class V684RuntimeContentionTests(unittest.TestCase):
    def test_version(self):
        self.assertEqual(VERSION, "6.8.10")

    def test_full_nse_ltp_has_hard_wall_clock_budget(self):
        b = GrowwBroker()
        clock = {"t": 0.0}

        def monotonic():
            clock["t"] += 1.0
            return clock["t"]

        def fake_request(method, path, *, params=None, json_body=None, timeout=15, retry_auth=True):
            symbols = str((params or {}).get("exchange_symbols") or "").split(",")
            return {s: 100.0 for s in symbols if s}

        b._request = fake_request
        symbols = [f"NSE_TEST{i:03d}" for i in range(500)]
        with patch.object(broker_mod.time, "monotonic", side_effect=monotonic), patch.object(broker_mod, "health"):
            out = b.ltp(symbols, wall_clock_budget_seconds=5.0)

        status = b._last_ltp_status
        self.assertTrue(status.get("budget_exhausted"))
        self.assertLess(int(status.get("batches") or 0), 10)
        self.assertLess(len(out), len(symbols))
        self.assertEqual(status.get("policy"), "PARTIAL_SUCCESS_50_BATCHES_BOUNDED_10_FALLBACK_HARD_WALL_CLOCK")

    def test_recurring_history_warmers_use_bounded_rotation(self):
        intraday_src = inspect.getsource(data.warm_intraday_history)
        daily_src = inspect.getsource(data.warm_daily_history)
        self.assertIn("rotate_count", intraday_src)
        self.assertIn("priority_pool", intraday_src)
        self.assertNotIn("_activity_rank_full_breadth()", intraday_src)
        self.assertIn("rotate_count", daily_src)
        self.assertIn("CACHED_FULL_BREADTH_DISCOVERY", daily_src)
        self.assertNotIn("_fast_raw_history_coverage(syms", daily_src)

    def test_market_snapshot_reports_internal_stage_and_heavy_warmers_are_staggered(self):
        snapshot_src = inspect.getsource(engine_mod.Engine._market_snapshot)
        supervise_src = inspect.getsource(engine_mod.Engine._supervise)
        cached_status_src = inspect.getsource(engine_mod.Engine.worker_status_cached)
        self.assertIn('"LTP_REFRESH"', snapshot_src)
        self.assertIn('"BREADTH_DISCOVERY"', snapshot_src)
        self.assertIn('"REGIME_CLASSIFICATION"', snapshot_src)
        self.assertIn('"current_stage":state.get("stage") or state.get("state")', cached_status_src)
        self.assertIn('self._maintenance,45', supervise_src)
        self.assertIn('self._daily_history,60', supervise_src)


if __name__ == "__main__":
    unittest.main()
