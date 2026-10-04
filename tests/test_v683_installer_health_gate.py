import unittest
from pathlib import Path

from psscanner_quant.constants import VERSION


class V683InstallerHealthGateTests(unittest.TestCase):
    def test_version(self):
        self.assertEqual(VERSION, "6.8.6")

    def test_installer_health_gate_derives_expected_version_from_installed_source(self):
        root = Path(__file__).resolve().parents[1]
        install = (root / "install.sh").read_text()
        self.assertIn(
            'EXPECTED_VERSION="$("$APP/.venv/bin/python" -c \'from psscanner_quant.constants import VERSION; print(VERSION)\')"',
            install,
        )
        self.assertIn('python3 - "$NEW_HEALTH" "$EXPECTED_VERSION"', install)
        self.assertIn('expected=sys.argv[2]', install)
        self.assertIn("d.get('version')==expected", install)

    def test_final_health_and_groww_gate_uses_same_expected_version(self):
        root = Path(__file__).resolve().parents[1]
        install = (root / "install.sh").read_text()
        self.assertIn('python3 - "$NEW_HEALTH" "$NEW_GROWW" "$EXPECTED_VERSION"', install)
        self.assertIn('expected=sys.argv[3]', install)
        self.assertIn("h.get('version')==expected", install)
        self.assertNotIn("d.get('version')=='6.8.1'", install)
        self.assertNotIn("h.get('version')=='6.8.1'", install)


if __name__ == "__main__":
    unittest.main()
