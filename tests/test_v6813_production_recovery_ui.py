from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


class V6813ProductionRecoveryUITests(unittest.TestCase):
    def text(self, rel: str) -> str:
        return (ROOT/rel).read_text()

    def test_version_is_6813(self):
        self.assertIn('VERSION = "6.8.13"', self.text("psscanner_quant/constants.py"))

    def test_installer_supports_true_fresh_install(self):
        s=self.text("install.sh")
        self.assertIn('MODE="fresh"',s)
        self.assertIn('Fresh recovery install: application state will initialize cleanly.',s)
        self.assertIn('Groww execution will remain fail-closed until credentials are configured.',s)
        self.assertNotIn('Previous PS_Scanner_Final not found; refusing install',s)
        self.assertIn('post_install_validate.py',s)

    def test_fresh_install_never_requires_connected_groww_to_start_research(self):
        s=self.text("install.sh")
        self.assertIn('if [[ "$MODE" == "fresh" ]]',s)
        self.assertIn('manual execution remains fail-closed',s)
        self.assertIn('CONFIGURE_GROWW.command',s)

    def test_secure_groww_setup_is_local_only(self):
        s=self.text("tools/configure_groww.py")
        self.assertIn("getpass.getpass",s)
        self.assertIn("os.chmod(tmp,0o600)",s)
        self.assertNotIn("print(payload)",s)
        self.assertIn("Groww authentication VERIFIED",s)

    def test_ui_has_professional_command_center_and_recovery_visibility(self):
        s=self.text("static/index.html")
        for token in (
            "Production Command Center",
            "Evidence Fabric",
            "Recovery Contracts",
            "Research Funnel",
            "PREPARED · WAITING FOR VALID SESSION ENTRY",
            "frozen-book shortage",
        ):
            self.assertIn(token,s)
        self.assertIn("v6.8.13",s)

    def test_ui_distinguishes_prepared_from_active(self):
        s=self.text("static/index.html")
        self.assertIn("life.state==='PREPARED'",s)
        self.assertIn("life.active===false",s)
        self.assertIn("FORECAST REF",s)
        self.assertIn("ACTIVE / PREPARED LONG",s)

    def test_core_risk_and_full_breadth_invariants_remain(self):
        constants=self.text("psscanner_quant/constants.py")
        config=self.text("psscanner_quant/config.py")
        self.assertIn("TRADE_NOTIONAL_RUPEES = 20_000.0",constants)
        self.assertIn("MAX_RUPEE_RISK_PER_TRADE = 500.0",constants)
        self.assertIn('"full_nse_breadth_enabled": True',config)
        self.assertIn('"universe_size": 0',config)
        self.assertIn('"intraday_scan_size": 0',config)
        self.assertIn('"horizon_scan_size": 0',config)

    def test_installer_contains_no_empty_command_substitution_rm_pattern(self):
        s=self.text("install.sh")
        self.assertIsNone(re.search(r'rm\s+-rf\s+"\$\([^\n]+\)"?/\*',s))
        self.assertNotIn('rm -rf "$(brew --cache',s)


if __name__=="__main__":
    unittest.main()
