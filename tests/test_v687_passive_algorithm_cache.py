import inspect
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from psscanner_quant import institutional_intelligence as inst
from psscanner_quant import trading_algorithm as algo
from psscanner_quant.constants import VERSION


class V687PassiveAlgorithmCacheTests(unittest.TestCase):
    def setUp(self):
        with algo._CACHE_LOCK:
            algo._CACHE.clear()
        with inst._LOCK:
            inst._SUMMARY_CACHE.clear()

    def test_version(self):
        self.assertEqual(VERSION, "6.8.13")

    def test_institutional_summary_drops_deep_arrays(self):
        deep={
            "captured_at":"2026-10-04T09:00:00+05:30",
            "status":"READY",
            "large_deal_count":2,
            "large_deals":[
                {"symbol":"AAA","price":100.0},
                {"symbol":"BBB","price":0.0},
            ],
            "delivery":{"count":3262,"symbols":{"AAA":{"delivery_pct":55.0}}},
            "disclosures":{
                "insider_transactions":[{"symbol":"AAA"}],
                "regulatory_announcements":[{"symbol":"BBB"}],
            },
            "derivatives":{"AAA":{"pcr_oi":1.1}},
            "derivatives_status":{"ready":1,"budget_exhausted":False},
            "flows":{"FII_FPI":{"net_crore":10},"DII":{"net_crore":20}},
            "errors":[],
        }
        out=inst._compact_summary(deep)
        self.assertEqual(out["large_deal_count"],2)
        self.assertEqual(out["large_deals_with_price"],1)
        self.assertEqual(out["delivery_count"],3262)
        self.assertNotIn("large_deals",out)
        self.assertNotIn("delivery",out)
        self.assertNotIn("derivatives",out)
        self.assertNotIn("disclosures",out)

    def test_status_never_rebuilds_snapshot(self):
        cached={
            "policy":algo.POLICY,
            "cache_ready":True,
            "algorithm_contract":{"passive_cached":True,"network_calls":False,"deep_institutional_payload":False},
        }
        with algo._CACHE_LOCK:
            algo._CACHE.update(cached)
        with patch.object(algo,"snapshot",side_effect=AssertionError("passive status must not rebuild")), \
             patch.object(algo,"get_state",side_effect=AssertionError("passive status must not read DB")):
            out=algo.status()
        self.assertTrue(out["cache_ready"])
        self.assertTrue(out["algorithm_contract"]["passive_cached"])

    def test_empty_status_is_immediate_warming_not_inline_rebuild(self):
        with patch.object(algo,"snapshot",side_effect=AssertionError("must not rebuild")), \
             patch.object(algo,"get_state",side_effect=AssertionError("must not read DB")):
            out=algo.status()
        self.assertFalse(out["cache_ready"])
        self.assertEqual(out["accuracy_target"]["status"],"WARMING")
        self.assertTrue(out["algorithm_contract"]["passive_cached"])

    def test_refresh_caches_compact_background_payload(self):
        institutional={
            "status":"READY","large_deal_count":343,"delivery_count":3262,
            "derivatives_status":{"ready":2},"errors":[],
        }
        acc={"overall":{"sample_size":10,"target_hit_rate":.5,"confidence_supported_80":False,
                        "observed_target_met":False,"target_hit_wilson_95":{"low":.2,"high":.8}},
             "by_book":{}}
        with patch.object(algo,"_strategy_manifest",return_value=[]), \
             patch.object(algo,"accuracy",return_value=acc), \
             patch.object(algo,"_live_outputs",return_value={b:[] for b in algo.BOOKS}), \
             patch.object(algo,"fabric_status",return_value={"policy":"V680_ONE_OBSERVATION_MANY_CONSUMERS","domains":{}}), \
             patch.object(algo,"institutional_summary",return_value=institutional), \
             patch.object(algo,"get_state",return_value={}), \
             patch.object(algo,"set_state") as state_write, \
             patch.object(algo,"_record"), \
             patch.object(algo,"history",return_value=[]):
            out=algo.refresh()
        self.assertTrue(out["cache_ready"])
        self.assertEqual(out["institutional_intelligence"],institutional)
        self.assertFalse(out["algorithm_contract"]["deep_institutional_payload"])
        self.assertTrue(any(call.args and call.args[0]=="adaptive_algorithm_status_cache" for call in state_write.call_args_list))
        self.assertLess(len(json.dumps(out,default=str)),100000)

    def test_installer_primes_compact_cache_before_launch(self):
        src=(Path(__file__).resolve().parents[1]/"install.sh").read_text()
        backfill=src.index("backfill_compact_summary")
        refresh=src.index("from psscanner_quant.trading_algorithm import refresh")
        launch=src.index('mkdir -p "$HOME/Library/LaunchAgents"',refresh)
        self.assertLess(backfill,refresh)
        self.assertLess(refresh,launch)

    def test_validator_requires_passive_algorithm_contract(self):
        src=(Path(__file__).resolve().parents[1]/"tools"/"post_install_validate.py").read_text()
        self.assertIn('algorithm.get("cache_ready") is not True',src)
        self.assertIn('algorithm_contract.get("passive_cached") is not True',src)
        self.assertIn('algorithm_contract.get("network_calls") is not False',src)
        self.assertIn('algorithm_contract.get("deep_institutional_payload") is not False',src)

    def test_algorithm_route_is_backed_by_status_cache(self):
        from psscanner_quant import main
        src=inspect.getsource(main.adaptive_algorithm)
        self.assertIn("algorithm_status()",src)


if __name__ == "__main__":
    unittest.main()
