from __future__ import annotations

import unittest
from contextlib import contextmanager
from datetime import datetime, timedelta
from unittest.mock import patch

import pandas as pd

from psscanner_quant import engine as eng
from psscanner_quant import portfolio_risk as pr
from psscanner_quant.constants import IST


class _Cursor:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return list(self._rows)


class _Connection:
    def __init__(self, rows):
        self._rows = rows

    def execute(self, _sql, _args=()):
        return _Cursor(self._rows)


class _Thread:
    name = "psq-weekly"

    def is_alive(self):
        return True


class V6816WeeklyFinalistRuntimeTests(unittest.TestCase):
    def test_scan_local_cluster_cache_reads_each_symbol_once(self):
        rows = [
            {"recommendation_id": "R1", "symbol": "PEER1", "side": "LONG", "book": "WEEKLY"},
            {"recommendation_id": "R2", "symbol": "PEER2", "side": "LONG", "book": "MONTHLY"},
            {"recommendation_id": "R3", "symbol": "PEER3", "side": "LONG", "book": "ETF"},
        ]

        @contextmanager
        def fake_db(*_args, **_kwargs):
            yield _Connection(rows)

        calls = []

        def fake_history(symbol, interval, allow_network=False):
            self.assertEqual(interval, "1day")
            self.assertFalse(allow_network)
            calls.append(symbol)
            idx = pd.date_range("2026-01-01", periods=60, freq="D")
            base = 100.0 + (sum(map(ord, symbol)) % 7)
            return pd.DataFrame({"close": [base + i for i in range(60)]}, index=idx)

        with patch.object(pr, "db", fake_db), patch.object(pr, "history", side_effect=fake_history):
            prepared = pr.prepare_recommendation_cluster(["AAA", "BBB"], "LONG")
            self.assertEqual(prepared["symbols_loaded"], 5)
            self.assertEqual(len(calls), 5)
            self.assertEqual(set(calls), {"AAA", "BBB", "PEER1", "PEER2", "PEER3"})

            a = pr.recommendation_cluster("AAA", "LONG", prepared=prepared)
            b = pr.recommendation_cluster("BBB", "LONG", prepared=prepared)

        # Finalist correlation evaluation must not re-parse any history file.
        self.assertEqual(len(calls), 5)
        self.assertEqual(a["correlation_source"], "PREPARED_SCAN_CACHE")
        self.assertEqual(b["correlation_source"], "PREPARED_SCAN_CACHE")
        self.assertTrue(a["hard_block"])
        self.assertTrue(b["hard_block"])

    def test_passive_worker_health_distinguishes_long_running_from_stalled(self):
        eng._SCAN_PROGRESS_MEMORY.clear()
        e = eng.Engine()
        e.workers = {"weekly": _Thread()}
        e.worker_specs = {"weekly": (300, None)}
        e.worker_runtime = {
            "weekly": {
                "state": "RUNNING",
                "started_at": (datetime.now(IST) - timedelta(seconds=1300)).isoformat(),
                "last_ok_at": None,
                "last_error": None,
            }
        }

        eng.note_scan_progress(
            "WEEKLY", "FINALIST_REFRESH", processed=17, total=46, current="AAA"
        )
        live = e.worker_status_cached()["weekly"]
        self.assertTrue(live["runtime_over_threshold"])
        self.assertFalse(live["hung"])
        self.assertEqual(live["current_stage"], "FINALIST_REFRESH")
        self.assertEqual(live["processed"], 17)
        self.assertEqual(live["remaining"], 29)

        eng._SCAN_PROGRESS_MEMORY["WEEKLY"]["last_progress_at"] = (
            datetime.now(IST) - timedelta(seconds=360)
        ).isoformat()
        stalled = e.worker_status_cached()["weekly"]
        self.assertTrue(stalled["runtime_over_threshold"])
        self.assertTrue(stalled["hung"])
        self.assertGreater(stalled["progress_age_seconds"], stalled["stall_grace_seconds"])

        eng._SCAN_PROGRESS_MEMORY.clear()


if __name__ == "__main__":
    unittest.main()
