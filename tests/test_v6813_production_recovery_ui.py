from __future__ import annotations

import json
import re
import sqlite3
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


class V6813ProductionRecoveryUITests(unittest.TestCase):
    def text(self, rel: str) -> str:
        return (ROOT/rel).read_text()

    def test_version_is_6813(self):
        self.assertIn('VERSION = "6.8.14"', self.text("psscanner_quant/constants.py"))

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


    def test_complete_totp_pair_is_recognized_as_configured(self):
        from psscanner_quant import broker as broker_mod
        old=broker_mod.CREDENTIALS_PATH
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"groww_credentials.json"
            try:
                broker_mod.CREDENTIALS_PATH=p
                b=broker_mod.GrowwBroker()
                p.write_text(json.dumps({
                    "auth_mode":"totp",
                    "totp_token":"test-token",
                    "totp_secret":"test-secret",
                }))
                self.assertTrue(b.configured())
                self.assertTrue(b.status_cached()["configured"])
                p.write_text(json.dumps({
                    "auth_mode":"totp",
                    "totp_token":"test-token",
                }))
                self.assertFalse(b.configured())
            finally:
                broker_mod.CREDENTIALS_PATH=old

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
        self.assertIn("v6.8.14",s)

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

    def test_migration_helper_is_invoked_through_python(self):
        s=self.text("install.sh")
        self.assertIn('python3 "$SRC/tools/migrate_groww_secrets.py" "$APP" "$TMPSECRET"',s)
        self.assertNotIn('  "$SRC/tools/migrate_groww_secrets.py" "$APP" "$TMPSECRET"',s)

    def test_damaged_install_enters_recovery_mode(self):
        s=self.text("install.sh")
        self.assertIn('elif [[ -d "$APP/data" || -d "$APP/logs" ]]; then',s)
        self.assertIn('MODE="recovery"',s)
        self.assertIn('Damaged/incomplete prior installation detected.',s)

    def test_missing_credentials_do_not_abort_research_recovery(self):
        s=self.text("install.sh")
        self.assertIn('migrate_rc -eq 4 || $migrate_rc -eq 5',s)
        self.assertIn('Continuing recovery with execution fail-closed',s)
        self.assertIn('mode in ("fresh","recovery")',s)
        self.assertIn('"$MODE" == "fresh" || "$MODE" == "recovery"',s)

    def test_recovery_preserves_surviving_runtime_state(self):
        s=self.text("install.sh")
        self.assertIn('if [[ "$MODE" == "upgrade" || "$MODE" == "recovery" ]]; then',s)
        self.assertIn('rsync -a "$ROLLBACK/data/" "$APP/data/"',s)
        self.assertIn('rsync -a "$ROLLBACK/logs/" "$APP/logs/"',s)

    def test_recovery_skips_missing_settings_and_database(self):
        s=self.text("install.sh")
        self.assertIn('no settings.json survived; runtime defaults will initialize cleanly',s)
        self.assertIn('Ledger migration skipped: no prior SQLite database survived.',s)

    def test_schema_bootstrap_runs_before_migrations_and_unit_suite(self):
        s=self.text("install.sh")
        schema=s.index("Recovery database schema: READY")
        settings=s.index("v6.4.3 settings migration")
        suite=s.index("./.venv/bin/python -m unittest discover -s tests -v")
        self.assertLess(schema,settings)
        self.assertLess(schema,suite)
        self.assertIn("from psscanner_quant import db as dbmod",s)
        self.assertIn("dbmod.init_db()",s)
        self.assertIn("PRAGMA quick_check",s)

    def test_empty_existing_sqlite_is_repaired_to_full_schema(self):
        from psscanner_quant import db as dbmod
        old=dbmod.DB_PATH
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"partial.db"
            sqlite3.connect(str(p)).close()
            try:
                dbmod.DB_PATH=p
                dbmod.init_db()
                con=sqlite3.connect(str(p))
                tables={r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                qc=con.execute("PRAGMA quick_check").fetchone()[0]
                con.close()
                self.assertTrue({"system_state","recommendations","trade_decisions","scan_runs"}.issubset(tables))
                self.assertEqual(qc,"ok")
            finally:
                dbmod.DB_PATH=old

    def test_corrupt_recovery_database_is_quarantined_not_deleted(self):
        s=self.text("install.sh")
        self.assertIn('".damaged_recovery_" + stamp',s)
        self.assertIn('os.replace(p,forensic)',s)
        self.assertNotIn('unlink()',s)

    def test_ui_exposes_secure_groww_totp_and_static_ip_setup(self):
        ui=self.text("static/index.html")
        self.assertIn("Groww TOTP Credentials",ui)
        self.assertIn('id="growwTokenInput"',ui)
        self.assertIn('id="growwSecretInput"',ui)
        self.assertIn('type="password"',ui)
        self.assertIn("/api/groww/configure-totp",ui)
        self.assertIn('id="staticIpInput"',ui)
        self.assertIn("Save credentials & verify",ui)
        self.assertIn("values are never prefilled",ui)

    def test_groww_totp_ui_api_is_local_only_and_secret_free(self):
        main=self.text("psscanner_quant/main.py")
        self.assertIn('@app.post("/api/groww/configure-totp")',main)
        self.assertIn('host not in ("127.0.0.1","::1","localhost")',main)
        self.assertIn('"secret_values_returned":False',main)
        self.assertIn('"storage":"LOCAL_CHMOD_600"',main)
        self.assertNotIn('"totp_token":payload.totp_token',main)
        self.assertNotIn('"totp_secret":payload.totp_secret',main)

    def test_broker_configure_totp_writes_complete_pair_mode_0600(self):
        import os
        from psscanner_quant import broker as broker_mod
        old=broker_mod.CREDENTIALS_PATH
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"groww_credentials.json"
            try:
                broker_mod.CREDENTIALS_PATH=p
                b=broker_mod.GrowwBroker()
                out=b.configure_totp("test-token-123","test-secret-456")
                raw=json.loads(p.read_text())
                self.assertEqual(raw["auth_mode"],"totp")
                self.assertEqual(raw["totp_token"],"test-token-123")
                self.assertEqual(raw["totp_secret"],"test-secret-456")
                self.assertEqual(out["auth_mode"],"totp")
                self.assertNotIn("totp_token",out)
                self.assertNotIn("totp_secret",out)
                self.assertEqual(os.stat(p).st_mode & 0o777,0o600)
            finally:
                broker_mod.CREDENTIALS_PATH=old


if __name__=="__main__":
    unittest.main()
