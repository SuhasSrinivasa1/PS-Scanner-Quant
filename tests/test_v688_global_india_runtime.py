import inspect
import unittest
from unittest.mock import patch

from psscanner_quant import cross_market as cm, data
from psscanner_quant.features import latest_features
from psscanner_quant.constants import VERSION


class V688GlobalIndiaRuntimeTests(unittest.TestCase):
    def test_version(self):
        self.assertGreaterEqual(tuple(int(x) for x in VERSION.split(".")),(6,8,15))

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

    def test_compact_summary_close_sequence_matches_authoritative_parser(self):
        candles=[]
        base=1_780_000_000
        for i in range(65):
            ts=base+i*86400
            px=100.0+i
            candles.append([ts,px-1,px+2,px-2,px,1000+i])
        # Last duplicate wins in both paths; an invalid HLC row is ignored in both paths.
        candles.append([base+10*86400,150,152,148,151,2000])
        candles.append([base+70*86400,150,None,148,151,2000])
        rows,closes=data._history_summary_values("1day",candles)
        df=data._parse_candles(candles)
        self.assertEqual(rows,len(df))
        self.assertEqual(closes,[float(x) for x in df["close"].tolist()[-60:]])
        sf=cm._global_india_summary_features({"daily_rows":rows,"recent_closes":closes})
        df_last=latest_features(df)
        self.assertAlmostEqual(sf["ret20"],df_last["ret20"],places=10)
        self.assertAlmostEqual(sf["trend"],df_last["trend"],places=10)

    def test_full_breadth_is_screened_without_top_n_slice(self):
        start_src=inspect.getsource(cm._start_global_india_job)
        src=inspect.getsource(cm.build_global_india_board)
        self.assertIn("history_summary_snapshot(syms)",start_src)
        self.assertIn("summary_evaluated",src)
        self.assertNotIn("syms[:",start_src)
        self.assertIn("time.sleep(0)",start_src)
        self.assertIn("FULL_NSE_RESUMABLE_BRANCH_AND_BOUND_NO_TOP_N_CAP",src)


if __name__ == "__main__":
    unittest.main()
