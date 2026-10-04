import inspect
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from psscanner_quant import config, cross_market, engine, main, support_bundle
from psscanner_quant.constants import VERSION
from psscanner_quant.db import now_iso


class V6812RuntimeCompletionTests(unittest.TestCase):
    def test_version(self):
        self.assertEqual(VERSION,"6.8.12")

    def test_global_india_cycle_budget_is_below_watchdog(self):
        budget=float(config._DEFAULTS["global_india_detail_budget_seconds"])
        watchdog=engine.Engine()._worker_timeout_seconds("global_india",300)
        self.assertLessEqual(budget,240.0)
        self.assertLess(budget,watchdog)

    def test_global_india_bound_is_conservative_and_final_blend_is_bounded(self):
        low=cross_market._global_india_score_ceiling(.5,-1.0,"LONG",0.0)
        high=cross_market._global_india_score_ceiling(.5,1.0,"LONG",0.0)
        self.assertEqual(low,high)
        self.assertEqual(cross_market._global_india_final_score_ceiling(95.0),96.0)

    def test_incomplete_global_india_cycle_never_freezes_partial_board(self):
        with patch.object(cross_market,"build_global_india_board",return_value={"complete":False}), \
             patch.object(cross_market,"freeze_global_india_board",side_effect=AssertionError("partial board frozen")), \
             patch.object(cross_market,"set_state"):
            self.assertEqual(cross_market.run_global_india_cycle(),0)

    def test_global_india_source_is_resumable_without_top_n_cap(self):
        start_src=inspect.getsource(cross_market._start_global_india_job)
        build_src=inspect.getsource(cross_market.build_global_india_board)
        run_src=inspect.getsource(cross_market.run_global_india_cycle)
        self.assertIn("full_nse_symbols()",start_src)
        self.assertNotIn("syms[:",start_src)
        self.assertIn("_global_india_final_score_ceiling",start_src)
        self.assertIn("deadline=time.monotonic()+budget",build_src)
        self.assertIn("BOUNDED_CONTINUATION_PENDING",build_src)
        self.assertIn("partial_rows_published",build_src)
        self.assertIn('if board.get("complete") is not True',run_src)

    def test_support_refresh_skips_fresh_completed_bundle_and_keeps_memory_payload(self):
        old_latest=support_bundle._LATEST_PATH
        old_status_path=support_bundle._STATUS_PATH
        old_payload=support_bundle._PAYLOAD
        old_status=dict(support_bundle._STATUS)
        try:
            with tempfile.TemporaryDirectory() as td:
                root=Path(td)
                latest=root/"latest.zip"
                latest.write_bytes(b"PK-complete-prebuilt")
                support_bundle._LATEST_PATH=latest
                support_bundle._STATUS_PATH=root/"status.json"
                support_bundle._PAYLOAD=None
                support_bundle._STATUS.clear()
                support_bundle._STATUS.update({
                    "ready":True,"path":str(latest),"generated_at":now_iso(),
                    "last_error":None,"elapsed_ms":1.0,
                })
                with patch.object(support_bundle,"_build_to_path",side_effect=AssertionError("fresh bundle rebuilt")):
                    out=support_bundle.refresh_support_bundle(force=False,min_age_seconds=1800)
                self.assertTrue(out["ready"])
                self.assertTrue(out["payload_ready"])
                self.assertTrue(out["refresh_skipped_fresh"])
                self.assertEqual(out["request_path_filesystem_reads"],0)
                self.assertEqual(support_bundle.latest_support_bundle_payload(),b"PK-complete-prebuilt")
        finally:
            support_bundle._LATEST_PATH=old_latest
            support_bundle._STATUS_PATH=old_status_path
            support_bundle._PAYLOAD=old_payload
            support_bundle._STATUS.clear()
            support_bundle._STATUS.update(old_status)

    def test_support_refresh_defers_behind_heavy_research(self):
        src=inspect.getsource(engine.Engine._support_bundle_refresh)
        self.assertIn('"global_india"',src)
        self.assertIn('"market_snapshot"',src)
        self.assertIn("LOW_PRIORITY_SUPPORT_REFRESH_NEVER_COMPETES_WITH_HEAVY_RESEARCH",src)
        e=engine.Engine()
        e.worker_runtime["global_india"]={"state":"RUNNING"}
        with patch.object(support_bundle,"refresh_support_bundle",side_effect=AssertionError("heavy overlap")):
            # Import inside Engine points at the module function, so patch its module source.
            with patch("psscanner_quant.support_bundle.refresh_support_bundle",side_effect=AssertionError("heavy overlap")):
                with patch("psscanner_quant.engine.set_state"):
                    e._support_bundle_refresh()

    def test_support_http_response_uses_preloaded_memory_only(self):
        src=inspect.getsource(main.support_export)
        self.assertIn("latest_support_bundle_payload()",src)
        self.assertNotIn("latest_support_bundle_path",src)
        self.assertNotIn("FileResponse",src)
        with patch.object(main,"latest_support_bundle_payload",return_value=b"PK-memory"):
            response=main.support_export()
        self.assertEqual(response.body,b"PK-memory")
        self.assertEqual(response.headers.get("x-ps-scanner-support-source"),"PREBUILT_MEMORY")


if __name__=="__main__":
    unittest.main()
