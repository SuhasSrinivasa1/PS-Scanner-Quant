import inspect
import unittest

from psscanner_quant.constants import VERSION
from psscanner_quant import main, engine, data, support_bundle, evidence_policy, lifecycle


class V689FinalProductContractTests(unittest.TestCase):
    def test_version(self):
        self.assertEqual(VERSION, "6.8.15")

    def test_passive_health_has_no_request_path_database(self):
        src=inspect.getsource(main.health)
        self.assertIn("health_db_snapshot_status",src)
        self.assertNotIn("with db(",src)
        self.assertIn("request_path_db_connections",src)
        self.assertIn("snapshot_fresh",src)
        self.assertIn("stale_snapshot_blocks_execution",src)

    def test_background_health_worker_exists(self):
        src=inspect.getsource(engine.Engine._supervise)
        self.assertIn('"health_snapshot"',src)
        self.assertIn("health_snapshot_worker_interval_seconds",src)
        self.assertIn("refresh_health_db_snapshot",inspect.getsource(engine.Engine._health_snapshot_refresh))

    def test_history_summary_is_shared_in_memory(self):
        src=inspect.getsource(data.history_summary_snapshot)
        self.assertIn("_HISTORY_SUMMARY_CACHE",src)
        self.assertIn("ttl_seconds",src)
        self.assertIn("return {k:dict(v) for k,v in cached.items()}",src)

    def test_log_export_is_visible_and_secret_aware(self):
        src=inspect.getsource(support_bundle.build_support_bundle)
        self.assertIn("SERVICE_LOGS_PLUS_SANITIZED_RUNTIME_AUDIT_EXPORT",src)
        self.assertIn("contains_credentials",src)
        self.assertNotIn("settings.json",src)
        self.assertEqual(support_bundle._sanitize({"api_secret":"x","ok":1})["api_secret"],"<REDACTED>")
        html=(main.STATIC/"index.html").read_text()
        self.assertIn("Export All Logs",html)
        self.assertIn("/api/support/export",html)

    def test_book_evidence_profiles_never_make_institutional_standalone(self):
        p=evidence_policy.profiles()
        self.assertIn("INTRADAY",p["profiles"])
        self.assertIn("MONTHLY",p["profiles"])
        for name,profile in p["profiles"].items():
            self.assertIn("institutional_role",profile)
        combo=evidence_policy.combination_profile(
            "INTRADAY","LONG",{"trend":1,"ret20":2,"volume_ratio":1.5},
            {"score":25,"confidence":.8},{"sentiment_score":.2,"materiality":.5},
            {"moves_pct":{"USDINR":.1}},{"industry":"Information Technology","supportive":True},
            {"hits":[{"direction":"LONG"}]},{}
        )
        self.assertFalse(combo["institutional_is_standalone_trigger"])
        self.assertGreaterEqual(combo["supportive_count"],4)

    def test_append_only_policy_is_explicit(self):
        src=inspect.getsource(engine._publish_append_discoveries)
        self.assertIn("APPEND_DISCOVERY",src)
        self.assertIn("initial_frozen_slate_preserved",src)
        self.assertIn("no_rank_replacement",src)
        self.assertIn("evidence_combination",src)
        self.assertIn("horizon_append_score_uplift",src)

    def test_global_india_prediction_period_is_weekly(self):
        from datetime import datetime
        from psscanner_quant.constants import IST
        dt=datetime(2026,10,7,12,0,tzinfo=IST)
        self.assertEqual(engine.period_key("GLOBAL_INDIA_LONG",dt),"2026-10-05")
        self.assertEqual(engine.period_key("GLOBAL_INDIA_SHORT",dt),"2026-10-05")
        self.assertIn("NSE_TRADING_WEEK",lifecycle.BOOK_CONTRACTS["GLOBAL_INDIA_LONG"]["horizon"])
        self.assertIn("SAME_DAY_MIS",lifecycle.BOOK_CONTRACTS["GLOBAL_INDIA_SHORT"]["publication"])

    def test_short_execution_contract_is_not_relaxed(self):
        from psscanner_quant.constants import SHORT_HARD_EXIT
        self.assertEqual((SHORT_HARD_EXIT.hour,SHORT_HARD_EXIT.minute),(15,0))


if __name__ == "__main__":
    unittest.main()
