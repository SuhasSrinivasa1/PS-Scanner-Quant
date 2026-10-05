import json
import sqlite3
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from psscanner_quant import db as dbmod
from psscanner_quant.strategy_library import seed_library
from tools import recover_support_ledger as rec


class V6812SupportLedgerRecoveryTests(unittest.TestCase):
    def _bundle(self,root:Path)->Path:
        p=root/'support.zip'
        rows={
            'recommendations':[{'recommendation_id':'R1','book':'INTRADAY','period_key':'2026-10-05','symbol':'ABC','exchange':'NSE','side':'LONG','state':'CLOSED','score':80.0,'confidence':.7,'entry_price':100.0,'current_price':102.0,'target_price':103.0,'stop_price':98.0,'target_pct':3.0,'horizon':'INTRADAY','regime':'RANGE','strategy_ids_json':'[]','rationale_json':'{}','feature_snapshot_json':'{}','data_confidence':.8,'created_at':'2026-10-05T10:00:00+05:30','updated_at':'2026-10-05T11:00:00+05:30','closed_at':'2026-10-05T11:00:00+05:30','result':'WIN','close_reason':'TARGET_REACHED','max_favourable_pct':3.0,'max_adverse_pct':0.0,'software_version':'6.8.12','config_hash':None,'decision_id':None,'audit_envelope_json':'{}'}],
            'trade_decisions':[{'id':9,'decision_id':'D1','ts':'2026-10-05T10:00:00+05:30','book':'INTRADAY','period_key':'2026-10-05','symbol':'ABC','side':'LONG','decision':'ELIGIBLE','ensemble_score':80.0,'intelligence_score':82.0,'hard_fail_count':0,'strategy_ids_json':'[]','payload_json':'{}','audit_envelope_json':'{}','pipeline_verdict':'PUBLICATION_READY','pipeline_stage':'FINAL_GATES','realized_outcome':'WIN'}],
            'scan_runs':[{'id':5,'run_id':'S1','book':'INTRADAY','period_key':'2026-10-05','started_at':'2026-10-05T10:00:00+05:30','completed_at':'2026-10-05T10:01:00+05:30','status':'DONE','universe_total':1,'scan_scope_total':1,'processed':1,'funnel_json':'{}','near_misses_json':'[]','payload_json':'{}'}],
            'strategy_validation_runs':[],
            'algorithm_versions':[],
            'institutional_snapshots':[{'snapshot_id':'I1','captured_at':'2026-10-05T10:00:00+05:30','source':'TEST','payload_hash':'h','payload_json':'{}'}],
            'system_state':[{'key':'adaptive_algorithm_current','value_json':'{}','updated_at':'2026-10-05T10:00:00+05:30'},{'key':'worker_intraday','value_json':'{}','updated_at':'2026-10-05T10:00:00+05:30'}],
            'health_events':[{'id':10,'ts':'2026-10-05T10:00:00+05:30','component':'test','level':'INFO','message':'m','payload_json':'{}'}],
        }
        with zipfile.ZipFile(p,'w',compression=zipfile.ZIP_DEFLATED) as z:
            z.writestr('manifest.json','{}')
            for table,path in rec.EXPORTS.items():
                z.writestr(path,'\n'.join(json.dumps(x,separators=(',',':')) for x in rows[table])+'\n')
        return p

    def test_preview_is_read_only(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);bundle=self._bundle(root);db=root/'db.sqlite'
            out=rec.recover(bundle,db,False)
            self.assertFalse(out['apply']);self.assertEqual(out['export_rows']['recommendations'],1);self.assertFalse(db.exists())

    def test_apply_imports_audit_identity_and_skips_transient_state(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);bundle=self._bundle(root);db=root/'db.sqlite'
            old=dbmod.DB_PATH
            try:
                dbmod.DB_PATH=db
                with patch.object(rec,'DB_PATH',db):
                    dbmod.init_db();seed_library();out=rec.recover(bundle,db,True)
                self.assertEqual(out['imported']['recommendations'],1)
                self.assertEqual(out['imported']['trade_decisions'],1)
                self.assertEqual(out['imported']['system_state_durable'],1)
                self.assertEqual(out['skipped']['system_state_transient'],1)
                con=sqlite3.connect(db)
                self.assertEqual(con.execute("select count(*) from recommendations where recommendation_id='R1'").fetchone()[0],1)
                self.assertEqual(con.execute("select count(*) from system_state where key='worker_intraday'").fetchone()[0],0)
                con.close()
            finally:dbmod.DB_PATH=old

    def test_repeat_bundle_is_idempotent(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);bundle=self._bundle(root);db=root/'db.sqlite';old=dbmod.DB_PATH
            try:
                dbmod.DB_PATH=db
                with patch.object(rec,'DB_PATH',db):
                    dbmod.init_db();seed_library();first=rec.recover(bundle,db,True);second=rec.recover(bundle,db,True)
                self.assertFalse(first['already_imported']);self.assertTrue(second['already_imported'])
            finally:dbmod.DB_PATH=old


if __name__=='__main__':unittest.main()
