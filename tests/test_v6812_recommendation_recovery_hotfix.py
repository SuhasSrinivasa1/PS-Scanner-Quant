import inspect
import sqlite3
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from psscanner_quant import engine, specialized, support_bundle, evidence_fabric
from psscanner_quant.constants import IST


class V6812RecommendationRecoveryHotfixTests(unittest.TestCase):
    def test_intraday_always_uses_bounded_rotating_full_breadth(self):
        src=inspect.getsource(engine.run_intraday_cycle)
        self.assertIn("BOUNDED_ROTATING_FULL_CACHED_BREADTH_NO_TOP_N_NO_GATE_RELAXATION",src)
        self.assertNotIn('cands=scan_equities("INTRADAY")',src)
        self.assertIn("_publish_intraday_candidates",src)

    def test_intraday_publication_is_explicitly_accounted(self):
        src=inspect.getsource(engine._publish_intraday_candidates)
        for key in ("duplicate_identity","short_deadline_reject","cutoff_reject","insert_error","published"):
            self.assertIn(key,src)
        self.assertIn("con_override=con",src)

    def test_global_india_preopen_identity_waits_for_activation(self):
        row={"book":"GLOBAL_INDIA_LONG","period_key":"2026-10-05","created_at":"2026-10-05T09:00:30+05:30",
             "rationale_json":'{"target_session_reference":"2026-10-05","activation_pending":true}'}
        pre=datetime(2026,10,5,9,5,tzinfo=IST);post=datetime(2026,10,5,9,20,tzinfo=IST)
        self.assertEqual(engine._activation_gate(row,pre)["state"],"PREPARED")
        self.assertTrue(engine._activation_gate(row,post)["active"])
        self.assertTrue(engine._recommendation_needs_activation(row,post))

    def test_future_horizon_and_nextday_rows_are_prepared(self):
        now=datetime(2026,10,5,12,0,tzinfo=IST)
        weekly={"book":"WEEKLY","period_key":"2026-10-12","created_at":"2026-10-03T18:00:00+05:30","rationale_json":"{}"}
        nextday={"book":"CIRCUIT_NEXTDAY","period_key":"2026-10-06","created_at":"2026-10-05T15:00:00+05:30","rationale_json":"{}"}
        self.assertFalse(engine._activation_gate(weekly,now)["active"])
        self.assertFalse(engine._activation_gate(nextday,now)["active"])

    def test_international_lifecycle_never_closes_future_week(self):
        src=inspect.getsource(specialized.update_international_books)
        self.assertIn("active_rows",src)
        self.assertIn("if not session.get('open')",src)
        self.assertIn("activation_pending",src)
        self.assertIn("_activate_recommendation",src)
        self.assertNotIn("r['period_key']!=week_key",src)
        cycle=inspect.getsource(specialized.run_international_cycle)
        self.assertIn("FIRST_FRESH_US_REGULAR_SESSION_QUOTE",cycle)

    def test_etf_and_international_have_complete_rejection_funnels(self):
        etf=inspect.getsource(specialized.scan_etfs);intl=inspect.getsource(specialized.run_international_cycle)
        for key in ("score_reject","capacity_prefilter_reject","intelligence_reject","final_target_reject"):
            self.assertIn(key,etf)
        for key in ("history_short","trend_reject","momentum_reject","geometry_reject","intelligence_reject"):
            self.assertIn(key,intl)

    def test_symbol_context_has_batch_prime_contract(self):
        src=inspect.getsource(evidence_fabric.prime_symbol_context)
        self.assertIn("prime_news_cache",src);self.assertIn("prime_event_risk_context",src);self.assertIn("prime_ownership_cache",src)
        self.assertIn("network_calls",src)

    def test_activation_rebases_entry_once_and_preserves_forecast_reference(self):
        class CaptureCon:
            def __init__(self):self.calls=[]
            def execute(self,sql,args=()):self.calls.append((sql,args));return self
        row={
            "recommendation_id":"R1","book":"GLOBAL_INDIA_LONG","side":"LONG",
            "entry_price":100.0,"current_price":100.0,"target_pct":3.0,"target_price":103.0,"stop_price":98.0,
            "max_favourable_pct":0.0,"max_adverse_pct":0.0,
            "rationale_json":'{"activation_pending":true,"target_session_reference":"2026-10-05"}',
        }
        con=CaptureCon();now=datetime(2026,10,5,9,16,tzinfo=IST)
        out=engine._activate_recommendation(con,row,110.0,now)
        self.assertAlmostEqual(out["entry_price"],110.0)
        self.assertAlmostEqual(out["target_price"],113.3)
        self.assertAlmostEqual(out["stop_price"],107.8)
        rationale=engine._rec_rationale(out)
        self.assertFalse(rationale["activation_pending"])
        self.assertEqual(rationale["entry_activation"]["forecast_reference_price"],100.0)
        self.assertFalse(engine._recommendation_needs_activation(out,now))
        self.assertEqual(len(con.calls),1)

    def test_scan_equities_primes_symbol_context_once_per_batch(self):
        src=inspect.getsource(engine.scan_equities)
        self.assertIn("fabric_prime_symbol_context",src)
        self.assertIn("primed=scan_ctx",src)

    def test_support_refresh_refuses_low_disk_without_rebuilding(self):
        old_latest=support_bundle._LATEST_PATH;old_status_path=support_bundle._STATUS_PATH;old_payload=support_bundle._PAYLOAD;old_status=dict(support_bundle._STATUS)
        try:
            with tempfile.TemporaryDirectory() as td:
                root=Path(td);latest=root/"latest.zip";latest.write_bytes(b"PK-old")
                support_bundle._LATEST_PATH=latest;support_bundle._STATUS_PATH=root/"status.json";support_bundle._PAYLOAD=b"PK-old"
                support_bundle._STATUS.clear();support_bundle._STATUS.update({"ready":True,"generated_at":"2000-01-01T00:00:00+00:00","payload_ready":True})
                usage=type("DU",(),{"free":1024})()
                with patch.object(support_bundle.shutil,"disk_usage",return_value=usage),patch.object(support_bundle,"_build_to_path",side_effect=AssertionError("must not build")):
                    out=support_bundle.refresh_support_bundle(force=True)
                self.assertEqual(out.get("last_error"),"INSUFFICIENT_FREE_DISK_FOR_SUPPORT_REFRESH")
                self.assertEqual(support_bundle.latest_support_bundle_payload(),b"PK-old")
        finally:
            support_bundle._LATEST_PATH=old_latest;support_bundle._STATUS_PATH=old_status_path;support_bundle._PAYLOAD=old_payload
            support_bundle._STATUS.clear();support_bundle._STATUS.update(old_status)


if __name__=="__main__":unittest.main()
