import unittest
from pathlib import Path


ROOT=Path(__file__).resolve().parents[1]


class V6812FreshRecoveryInstallTests(unittest.TestCase):
    def test_missing_app_uses_fresh_recovery_instead_of_refusing(self):
        src=(ROOT/'install.sh').read_text()
        self.assertIn('MODE="fresh_recovery"',src)
        self.assertIn('if [[ -d "$APP" ]]; then',src)
        self.assertNotIn('Previous PS_Scanner_Final not found; refusing install',src)
        self.assertIn('if [[ -d "$APP" ]]; then mv "$APP" "$ROLLBACK"; fi',src)

    def test_fresh_recovery_initializes_empty_runtime_before_tests(self):
        src=(ROOT/'install.sh').read_text()
        init_pos=src.index('from psscanner_quant.db import init_db')
        test_pos=src.index('./.venv/bin/python -m unittest discover -s tests -v')
        self.assertLess(init_pos,test_pos)
        self.assertIn('update_settings({})',src)
        self.assertIn('seed_library()',src)
        self.assertIn('seed_official_calendar()',src)
        self.assertIn('seed_release_experiment()',src)

    def test_fresh_recovery_does_not_invent_credentials(self):
        src=(ROOT/'install.sh').read_text()
        self.assertIn('no Groww credentials were reconstructed or invented',src)
        self.assertIn('execution remains unavailable until Groww is reconfigured',src)
        self.assertIn('elif [[ "$MODE" == "migration" ]]; then',src)

    def test_execution_probe_remains_strict_for_non_fresh_installs(self):
        src=(ROOT/'install.sh').read_text()
        self.assertIn("execution_ok=(g.get('connected') is True) if mode!='fresh_recovery' else True",src)
        self.assertIn('else\n    echo "v6.8.12 application started, but Groww connectivity could not be verified after explicit probes."',src)
        self.assertIn('exit 21',src)

    def test_fresh_recovery_reports_empty_ledger_for_separate_restore(self):
        src=(ROOT/'install.sh').read_text()
        self.assertIn('NEW EMPTY RUNTIME — recoverable audit/learning ledger must be restored separately',src)
        self.assertIn('NOT CONFIGURED — execution remains blocked until credentials are reconfigured',src)


if __name__=='__main__':
    unittest.main()
