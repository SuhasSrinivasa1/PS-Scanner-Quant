from __future__ import annotations

import unittest
from pathlib import Path

from psscanner_quant.constants import VERSION

ROOT=Path(__file__).resolve().parents[1]


class V6815WebUIReliabilityTests(unittest.TestCase):
    def text(self,path:str)->str:
        return (ROOT/path).read_text()

    def test_version(self):
        self.assertEqual(VERSION,"6.8.15")

    def test_dashboard_separates_fast_health_from_slower_support_telemetry(self):
        ui=self.text("static/index.html")
        self.assertIn("const SUPPORT_TELEMETRY_MS=60000",ui)
        self.assertIn("refreshSupportingTelemetry",ui)
        self.assertIn("setInterval(()=>refreshHealth(false),15000)",ui)
        self.assertNotIn("Promise.all([api('/api/health'),api('/api/sanity')",ui)

    def test_hidden_browser_tabs_pause_polling_and_resume_cleanly(self):
        ui=self.text("static/index.html")
        self.assertIn("if(document.hidden&&!force)return",ui)
        self.assertIn("document.addEventListener('visibilitychange'",ui)
        self.assertIn("refreshVisibleBook",ui)
        self.assertIn("healthRefreshBusy",ui)
        self.assertIn("bookRefreshBusy",ui)

    def test_api_requests_are_time_bounded_and_ui_surfaces_failures(self):
        ui=self.text("static/index.html")
        self.assertIn("new AbortController()",ui)
        self.assertIn("Timed out loading",ui)
        self.assertIn("Dashboard connection delayed:",ui)
        self.assertIn('id="uiBanner"',ui)

    def test_command_center_does_not_report_online_from_empty_worker_snapshot(self):
        ui=self.text("static/index.html")
        self.assertIn("workerCount=Object.keys(workers).length",ui)
        self.assertIn("else if(!workerCount)",ui)
        self.assertIn("worker supervisor snapshot is initializing",ui)
        self.assertIn("background_snapshot_age_seconds",ui)

    def test_unprobed_configured_groww_is_verifying_not_auth_failure(self):
        ui=self.text("static/index.html")
        self.assertIn("UNKNOWN|WARMING|NOT_PROBED",ui)
        self.assertIn("'VERIFYING'",ui)

    def test_browser_icon_requests_are_served(self):
        main=self.text("psscanner_quant/main.py")
        ui=self.text("static/index.html")
        for route in ("/favicon.ico","/apple-touch-icon.png","/apple-touch-icon-precomposed.png"):
            self.assertIn(route,main)
        self.assertIn('rel="icon" href="/favicon.ico"',ui)
        self.assertIn('rel="apple-touch-icon" href="/apple-touch-icon.png"',ui)
        self.assertIn('media_type="image/svg+xml"',main)

    def test_runtime_html_and_api_are_no_store(self):
        main=self.text("psscanner_quant/main.py")
        self.assertIn('request.url.path.startswith("/api/") or request.url.path=="/"',main)
        self.assertIn('"Cache-Control"]="no-store, no-cache, must-revalidate, max-age=0"',main)


if __name__=="__main__":
    unittest.main()
