import inspect
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from psscanner_quant.constants import VERSION
from psscanner_quant import main, engine, passive_views, support_bundle, cross_market
from psscanner_quant import db as dbmod


class V6810PassiveUIViewTests(unittest.TestCase):
    def test_version(self):
        self.assertEqual(VERSION,"6.8.14")

    def test_health_is_pure_memory_for_subsystems(self):
        src=inspect.getsource(main.health)
        for forbidden in (
            "with db(","history_control_status_cached()","trading_calendar_status()",
            "sector_status_cached()","execution_readiness_cached_snapshot(",
            "broker.status_cached()","broker.static_ip_status_cached()",
        ):
            self.assertNotIn(forbidden,src)
        self.assertIn('snap.get("history_control")',src)
        self.assertIn('snap.get("execution")',src)
        self.assertIn('"filesystem_reads_on_request":0',src)
        self.assertIn('"subsystem_refresh_calls_on_request":0',src)

    def test_performance_route_prefers_precomputed_cache(self):
        src=inspect.getsource(main.performance)
        self.assertIn("cached_performance(group_by,limit)",src)
        self.assertIn("performance_stats(",src)  # book-specific/fallback remains bounded
        cached=inspect.getsource(passive_views.cached_performance)
        self.assertNotIn("db(",cached)
        self.assertIn('"request_path_db_connections":0',cached)

    def test_performance_producer_uses_one_snapshot(self):
        src=inspect.getsource(passive_views.refresh_performance)
        self.assertEqual(src.count("with db("),1)
        self.assertIn("idx_recs_state_closed_perf_cover",src)
        self.assertIn("UI_PERFORMANCE_GROUPS",src)
        self.assertIn("partial_rows_published",src)

    def test_international_route_is_cached_only(self):
        src=inspect.getsource(main.international_board)
        self.assertIn("cached_international()",src)
        self.assertNotIn("recommendations(",src)
        self.assertNotIn("get_state(",src)
        self.assertNotIn("global_india_board_payload",src)
        cached=inspect.getsource(passive_views.cached_international)
        self.assertNotIn("db(",cached)
        self.assertNotIn("get_state(",cached)

    def test_support_export_is_prebuilt_not_generated_on_click(self):
        src=inspect.getsource(main.support_export)
        self.assertIn("latest_support_bundle_payload()",src)
        self.assertIn("Response",src)
        self.assertNotIn("build_support_bundle",src)
        producer=inspect.getsource(support_bundle.refresh_support_bundle)
        self.assertIn("_build_to_path",producer)
        self.assertIn("support_bundle_status",producer)
        support_src=Path(support_bundle.__file__).read_text()
        self.assertIn("ZIP_DEFLATED",support_src)
        self.assertIn("_redact_text(line,secrets)",support_src)

    def test_background_workers_own_passive_views_and_export(self):
        src=inspect.getsource(engine.Engine._supervise)
        self.assertIn('"international_view"',src)
        self.assertIn('"performance_view"',src)
        self.assertIn('"support_bundle"',src)

    def test_global_india_yields_cooperatively_without_breadth_cap(self):
        start_src=inspect.getsource(cross_market._start_global_india_job)
        src=inspect.getsource(cross_market.build_global_india_board)
        self.assertIn("full_nse_symbols()",start_src)
        self.assertNotIn("syms[:",start_src)
        self.assertIn("time.sleep(0)",start_src)
        self.assertIn("FULL_NSE_RESUMABLE_BRANCH_AND_BOUND_NO_TOP_N_CAP",src)
        self.assertIn("partial_rows_published",src)
        self.assertIn("BOUNDED_CONTINUATION_PENDING",src)

    def test_installer_primes_caches_before_launch(self):
        root=Path(__file__).resolve().parents[1]
        install=(root/"install.sh").read_text()
        prime=install.index("refresh_performance, refresh_international")
        launch=install.rindex('launchctl bootstrap "gui/$(id -u)" "$PLIST"')
        self.assertLess(prime,launch)
        self.assertIn("refresh_support_bundle",install)


if __name__=="__main__":
    unittest.main()
