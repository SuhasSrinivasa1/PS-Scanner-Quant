import inspect
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from psscanner_quant import db as dbmod, support_bundle
from psscanner_quant.constants import VERSION


class V6811AcceptanceFixTests(unittest.TestCase):
    def test_version(self):
        self.assertGreaterEqual(tuple(int(x) for x in VERSION.split(".")),(6,8,15))

    def test_validator_requires_new_passive_cache_contracts(self):
        root=Path(__file__).resolve().parents[1]
        src=(root/"tools"/"post_install_validate.py").read_text()
        self.assertIn("from psscanner_quant.constants import VERSION",src)
        self.assertIn('perf_contract.get("passive_cached") is not True',src)
        self.assertIn('perf_contract.get("background_precomputed") is not True',src)
        self.assertIn('perf_contract.get("request_path_db_connections") != 0',src)
        self.assertIn('international_contract.get("passive_cached") is not True',src)
        self.assertIn('support.get("compression")!="DEFLATE_LEVEL_1"',src)
        self.assertNotIn('perf_contract.get("passive_bounded") is not True',src)

    def test_support_bundle_uses_background_deflate(self):
        src=inspect.getsource(support_bundle._build_to_path)
        self.assertIn("ZIP_DEFLATED",src)
        self.assertIn("compresslevel=1",src)
        self.assertIn('"compression":"DEFLATE_LEVEL_1"',src)
        self.assertIn("BACKGROUND_PREBUILT_SANITIZED_SUPPORT_BUNDLE_V6812",src)

    def test_repetitive_logs_are_materially_compressed_and_zip_is_valid(self):
        old_db=dbmod.DB_PATH
        old_logs=support_bundle.LOGS
        old_creds=support_bundle.CREDENTIALS_PATH
        try:
            with tempfile.TemporaryDirectory() as td:
                root=Path(td)
                dbmod.DB_PATH=root/"psscanner_quant.db"
                dbmod.init_db()
                logs=root/"logs";logs.mkdir()
                # Model the real service logs: highly repetitive structured text.
                payload=("INFO worker=global_india stage=DETAIL_ENRICHMENT symbol=TEST status=ok\n"*40000)
                (logs/"service.log").write_text(payload)
                support_bundle.LOGS=logs
                support_bundle.CREDENTIALS_PATH=root/"missing_credentials.json"
                out_path=root/"bundle.zip"
                meta=support_bundle._build_to_path(out_path)
                self.assertTrue(meta["ready"])
                self.assertEqual(meta["compression"],"DEFLATE_LEVEL_1")
                self.assertLess(meta["compression_ratio"],0.25)
                with zipfile.ZipFile(out_path,"r") as z:
                    self.assertIsNone(z.testzip())
                    self.assertIn("logs/service.log",z.namelist())
        finally:
            dbmod.DB_PATH=old_db
            support_bundle.LOGS=old_logs
            support_bundle.CREDENTIALS_PATH=old_creds


if __name__=="__main__":
    unittest.main()
