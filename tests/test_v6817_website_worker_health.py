from __future__ import annotations

import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from psscanner_quant import data
from psscanner_quant import engine as eng
from psscanner_quant import support_bundle as sb
from psscanner_quant.constants import IST, VERSION


class _Thread:
    name = "psq-daily_history"

    def is_alive(self):
        return True


class V6817WebsiteWorkerHealthTests(unittest.TestCase):
    def tearDown(self):
        eng._SCAN_PROGRESS_MEMORY.clear()

    def test_daily_history_warmer_emits_per_symbol_progress(self):
        metas=[
            {"symbol":"AAA","industry":"A"},
            {"symbol":"BBB","industry":"B"},
            {"symbol":"CCC","industry":"C"},
        ]
        states={
            "daily_history_warm_cursor":0,
            "universe_status":{},
            "full_breadth_discovery":{"universe":3,"status":"CURRENT","daily_history_ready":3,"at":"2026-10-07T12:00:00+05:30"},
        }
        events=[]
        df=pd.DataFrame({"close":list(range(40))})
        with patch.object(data,"universe",return_value=metas), \
             patch.object(data,"_active_nse_recommendation_symbols",return_value=[]), \
             patch.object(data,"get_state",side_effect=lambda k,d=None: states.get(k,d)), \
             patch.object(data,"_load_raw_candles",return_value=[]), \
             patch.object(data,"background_request_allowed",return_value={"allowed":True}), \
             patch.object(data,"history",return_value=df), \
             patch.object(data,"set_state"):
            out=data.warm_daily_history(3,progress_callback=events.append)

        self.assertEqual(out["attempted"],3)
        self.assertEqual(out["ready"],3)
        warming=[e for e in events if e.get("stage")=="WARMING"]
        self.assertEqual([e["processed"] for e in warming],[1,2,3])
        self.assertEqual({e["current_symbol"] for e in warming},{"AAA","BBB","CCC"})
        self.assertEqual(events[-1]["stage"],"COMPLETE")
        self.assertEqual(events[-1]["processed"],3)

    def test_daily_history_over_threshold_but_progressing_is_not_hung(self):
        e=eng.Engine()
        e.workers={"daily_history":_Thread()}
        e.worker_specs={"daily_history":(90,None)}
        e.worker_runtime={"daily_history":{
            "state":"RUNNING",
            "started_at":(datetime.now(IST)-timedelta(seconds=420)).isoformat(),
            "last_ok_at":None,
            "last_error":None,
        }}
        eng.note_scan_progress(
            "DAILY_HISTORY","WARMING",processed=12,total=64,current="AAA",
            meta={"ready":10,"errors":2,"deferred_rate_limit":0},
        )
        w=e.worker_status_cached()["daily_history"]
        self.assertTrue(w["runtime_over_threshold"])
        self.assertFalse(w["hung"])
        self.assertEqual(w["current_stage"],"WARMING")
        self.assertEqual(w["processed"],12)
        self.assertEqual(w["remaining"],52)
        self.assertEqual(w["current_item"],"AAA")
        self.assertEqual(w["progress_detail"]["ready"],10)

    def test_daily_history_stale_progress_is_hung(self):
        e=eng.Engine()
        e.workers={"daily_history":_Thread()}
        e.worker_specs={"daily_history":(90,None)}
        e.worker_runtime={"daily_history":{
            "state":"RUNNING",
            "started_at":(datetime.now(IST)-timedelta(seconds=700)).isoformat(),
            "last_ok_at":None,
            "last_error":None,
        }}
        eng.note_scan_progress("DAILY_HISTORY","FETCHING",processed=8,total=64,current="BBB")
        eng._SCAN_PROGRESS_MEMORY["DAILY_HISTORY"]["last_progress_at"]=(datetime.now(IST)-timedelta(seconds=240)).isoformat()
        w=e.worker_status_cached()["daily_history"]
        self.assertTrue(w["runtime_over_threshold"])
        self.assertTrue(w["hung"])
        self.assertGreater(w["progress_age_seconds"],w["stall_grace_seconds"])

    def test_support_bundle_status_exposes_age(self):
        original=dict(sb._STATUS)
        try:
            sb._STATUS.clear()
            sb._STATUS.update({
                "ready":True,
                "generated_at":(datetime.now(IST)-timedelta(seconds=120)).isoformat(),
                "payload_ready":True,
            })
            status=sb.support_bundle_status()
            self.assertIsNotNone(status["generated_age_seconds"])
            self.assertTrue(status["incident_capture_fresh"])
            self.assertEqual(status["incident_capture_note"],"PREBUILT_BACKGROUND_BUNDLE_MAY_LAG_LIVE_STATE")
        finally:
            sb._STATUS.clear()
            sb._STATUS.update(original)

    def test_command_center_distinguishes_busy_from_attention(self):
        html=(Path(__file__).resolve().parents[1]/"static"/"index.html").read_text()
        self.assertIn("long-running but progressing:",html)
        self.assertIn("incident_capture_fresh",html)
        self.assertIn("progress_age_seconds",html)

    def test_release_and_bash_fix_identity(self):
        self.assertGreaterEqual(tuple(int(x) for x in VERSION.split(".")),(6,8,17))
        script=(Path(__file__).resolve().parents[1]/"tools"/"apply_v6817_website_fix.sh").read_text()
        self.assertIn("#!/bin/bash",script)
        self.assertIn("post_install_validate.py",script)


if __name__ == "__main__":
    unittest.main()
