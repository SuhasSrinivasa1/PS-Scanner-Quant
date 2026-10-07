from __future__ import annotations

import unittest
from pathlib import Path

from psscanner_quant.constants import VERSION

ROOT=Path(__file__).resolve().parents[1]


class V6818WebsiteCorrectnessTests(unittest.TestCase):
    def html(self):
        return (ROOT/"static"/"index.html").read_text()

    def test_release_identity(self):
        self.assertEqual(VERSION,"6.8.18")
        self.assertIn("v6.8.18",self.html())

    def test_execution_is_a_separate_top_level_status(self):
        s=self.html()
        self.assertIn('id="executionPill"',s)
        self.assertIn('id="opsExecution"',s)
        self.assertIn("function executionUi",s)
        self.assertIn("all execution gates passed",s)

    def test_unknown_worker_is_warming_not_dead(self):
        s=self.html()
        self.assertIn("v.alive===false",s)
        self.assertIn("v.alive!==true||!v.state",s)
        self.assertIn("state:'WARMING'",s)
        self.assertNotIn("state=!v.alive?'DEAD'",s)

    def test_groww_unknown_not_probed_is_not_false_failure(self):
        s=self.html()
        self.assertIn("UNKNOWN_NOT_PROBED",s)
        self.assertIn("?'PROBING'",s)
        self.assertNotIn("health.groww?.connected?'good':'bad'",s)

    def test_static_ip_mismatch_is_red_execution_error_but_not_research_gate(self):
        s=self.html()
        self.assertIn("if(s.configured===true)return{text:'MISMATCH',cls:'bad'}",s)
        self.assertIn("RESEARCH",s)
        self.assertIn("Static IP gates order execution only",s)

    def test_recovery_interrupt_is_warning_not_engine_failure(self):
        s=self.html()
        self.assertIn("ERROR|FAILED|DEAD|HUNG|STALL",s)
        self.assertIn("WARMING|INTERRUPT|PREPAR",s)

    def test_order_button_reports_actual_execution_blocker(self):
        s=self.html()
        self.assertIn("humanBlocker",s)
        self.assertIn("allBlockers",s)
        self.assertNotIn("!ipOk?",s)

    def test_health_refresh_error_does_not_relabel_groww(self):
        s=self.html()
        self.assertIn("Health refresh failed",s)
        self.assertNotIn("growwPill.textContent='● HEALTH ERROR'",s)

    def test_bash_repair_contract(self):
        s=(ROOT/"tools"/"apply_v6818_website_correctness.sh").read_text()
        self.assertIn("#!/bin/bash",s)
        self.assertIn("post_install_validate.py",s)
        self.assertIn('grep -q \'id="executionPill"\'',s)
        self.assertIn("api/health",s)


if __name__=="__main__":
    unittest.main()
