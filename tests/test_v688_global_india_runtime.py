import inspect
import unittest
from unittest.mock import patch

from psscanner_quant import cross_market as cm
from psscanner_quant.constants import VERSION


class V688GlobalIndiaRuntimeTests(unittest.TestCase):
    def test_version(self):
        self.assertEqual(VERSION, "6.8.8")

    def test_summary_features_match_close_only_fields(self):
        closes=[100.0+i for i in range(60)]
        out=cm._global_india_summary_features({"daily_rows":220,"recent_closes":closes})
        self.assertIsNotNone(out)
        self.assertAlmostEqual(out["close"],159.0)
        self.assertAlmostEqual(out["ret20"],(159.0/139.0-1.0)*100.0)
        self.assertEqual(out["trend"],1.0)

    def test_ceiling_is_true_upper_bound_of_live_score_formula(self):
        for side in ("LONG","SHORT"):
            for aligned in (0.13,0.4,1.0,2.0):
                for trend in (-1.0,0.0,1.0):
                    for calibration in (-3.0,0.0,3.0):
                        ceiling=cm._global_india_score_ceiling(aligned,trend,side,calibration)
                        sign=1 if side=="LONG" else -1
                        trend_ok=sign*trend>=0
                        for adx in (0.0,8.0,24.0,56.0,100.0):
                            actual=68+min(16,aligned*9)+(7 if trend_ok else -4)+min(7,adx/8)+calibration
                            self.assertLessEqual(actual,ceiling+1e-12)

    def test_impossible_summary_never_parses_detailed_history(self):
        syms=[f"S{i}" for i in range(200)]
        meta=[{"symbol":s,"industry":"Information Technology"} for s in syms]
        summaries={s:{"daily_rows":220,"recent_closes":[100.0]*60} for s in syms}
        # Zero global moves means no aligned driver cue can cross the unchanged gate.
        with patch.object(cm,"full_nse_symbols",return_value=syms), \
             patch.object(cm,"universe",return_value=meta), \
             patch.object(cm,"history_summary_snapshot",return_value=summaries), \
             patch.object(cm,"get_state",side_effect=lambda key,default=None: {"moves_pct":{},"coverage":0} if key=="global_context" else (default or {})), \
             patch.object(cm,"_calibration_adjustment",return_value=0.0), \
             patch.object(cm,"history",side_effect=AssertionError("detail history must not be parsed")), \
             patch.object(cm,"set_state"):
            board=cm.build_global_india_board()
        self.assertEqual(board["universe_scanned"],200)
        self.assertEqual(board["runtime"]["summary_evaluated"],200)
        self.assertEqual(board["runtime"]["detail_parsed"],0)

    def test_full_breadth_is_screened_without_top_n_slice(self):
        src=inspect.getsource(cm.build_global_india_board)
        self.assertIn("history_summary_snapshot(syms)",src)
        self.assertIn("summary_evaluated",src)
        self.assertNotIn("syms[:",src)
        self.assertIn("time.sleep(0)",src)
        self.assertIn("FULL_NSE_SUMMARY_NECESSARY_PREFILTER_NO_TOP_N_CAP",src)


if __name__ == "__main__":
    unittest.main()
