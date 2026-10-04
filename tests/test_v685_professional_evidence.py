import inspect
import unittest
from datetime import datetime, date
from unittest.mock import patch

import pandas as pd

from psscanner_quant import engine as engine_mod, institutional_intelligence as inst, main, orders
from psscanner_quant.broker import GrowwBroker
from psscanner_quant.constants import VERSION
from psscanner_quant.features import latest_features
from psscanner_quant.trade_intelligence import evaluate


class V685ProfessionalEvidenceTests(unittest.TestCase):
    def test_version(self):
        self.assertEqual(VERSION, "6.8.6")

    def test_benchmark_relative_strength_uses_supplied_nifty_series(self):
        idx=pd.date_range("2026-01-01", periods=40, freq="D")
        stock=pd.DataFrame({
            "open":[100+i for i in range(40)],"high":[101+i for i in range(40)],
            "low":[99+i for i in range(40)],"close":[100+i*1.5 for i in range(40)],
            "volume":[1000+i for i in range(40)],
        }, index=idx)
        bench=pd.Series([100+i*.5 for i in range(40)], index=idx)
        out=latest_features(stock,benchmark=bench)
        self.assertTrue(out["benchmark_relative_available"])
        self.assertNotEqual(out["relative_strength20"],0.0)
        scan_src=inspect.getsource(engine_mod.scan_equities)
        self.assertIn('history("NIFTY",interval,allow_network=False)',scan_src)
        self.assertIn('latest_features(df,benchmark=benchmark_series)',scan_src)

    def test_broker_exposes_live_option_chain_and_segment_quote(self):
        src=inspect.getsource(GrowwBroker)
        self.assertIn('/v1/option-chain/exchange/',src)
        self.assertIn('segment: str = "CASH"',src)
        self.assertIn('"expiry_date": str(expiry_date)',src)

    def test_new_institutional_evidence_is_shadow_only(self):
        f={'close':100,'atr_pct':2,'gap_pct':0,'relative_strength20':2,'benchmark_relative_available':True,
           'ret20':5,'ret60':8,'trend':1,'volume_ratio':1.5,'turnover20':2_000_000,'range20_pos':.7,
           'ema12':102,'ema26':100,'adx14':25,'higher_tf_trend':1}
        ctx={'direction':'NEUTRAL','score':0,'confidence':0,
             'governance_risk_disclosures':[{'kind':'PLEDGE_ENCUMBRANCE'}],
             'delivery_evidence':{'delivery_pct':80},'derivatives_positioning':{'pcr_oi':2.0}}
        out=evaluate(book='WEEKLY',symbol='X',side='LONG',features=f,fundamentals={},
                     regime_state={'regime':'RANGE','trend_vote':.2,'breadth_up_pct':60,'breadth_down_pct':30},
                     global_ctx={'risk_state':'RISK_ON','moves_pct':{'US_TECH':1.0}},
                     sector_ctx={'status':'PASS','industry':'Information Technology','trend_up_pct':70,'trend_down_pct':10,
                                 'positive_pct':65,'stock_vs_industry_ret20_pct':1,'supportive':True,'sample':10},
                     institutional_ctx=ctx,target_pct=3,stop_pct=1.5,strategy_ids=['S1'],data_confidence=.9)
        filt={x['rank']:x for x in out['filters']}
        self.assertFalse(filt[17]['score_enabled'])
        self.assertFalse(filt[25]['score_enabled'])
        self.assertEqual(out['shadow_evidence']['delivery']['delivery_pct'],80)
        self.assertIn('EXCLUDED_FROM_SCORE',out['shadow_evidence']['policy'])

    def test_delivery_disclosure_and_derivative_sources_are_point_in_time_background_evidence(self):
        src=inspect.getsource(inst)
        self.assertIn('sec_bhavdata_full_',src)
        self.assertIn('/api/corporates-pit',src)
        self.assertIn('/api/corporate-announcements',src)
        self.assertIn('broker.option_chain',src)
        self.assertIn('GROWW_LIVE_OPTION_CHAIN_AND_FNO_QUOTE',src)
        self.assertIn('SHADOW_ONLY_UNTIL_OOS_VALIDATED',src)

    def test_delivery_uses_prior_session_before_post_market_publication(self):
        class Response:
            content=b"SYMBOL,DELIV_QTY,DELIV_PER,TTL_TRD_QNTY\nABC,100,50,200\n"
            def raise_for_status(self): return None
        now=datetime(2026,10,5,10,0,tzinfo=inst.IST)
        with patch.object(inst,'is_regular_trading_day',return_value=True),              patch.object(inst,'previous_trading_day',return_value=date(2026,10,2)) as prev,              patch.object(inst.requests,'get',return_value=Response()) as req:
            out=inst._fetch_delivery_snapshot(now)
        prev.assert_called_once_with(date(2026,10,4))
        self.assertIn('02102026',req.call_args.args[0])
        self.assertEqual(out['symbols']['ABC']['delivery_pct'],50.0)

    def test_derivative_priority_snapshot_has_aggregate_wall_clock_budget(self):
        rows=[{'exchange':'NSE','segment':'FNO','underlying_symbol':'ABC','expiry_date':'2026-10-29',
               'instrument_type':'OPT','trading_symbol':'ABCOPT'}]
        clock={'t':0.0}
        def mono():
            clock['t']+=7.0
            return clock['t']
        with patch.object(inst,'instrument_rows',return_value=rows),              patch.object(inst.time,'monotonic',side_effect=mono),              patch.object(inst.broker,'option_chain',return_value={'underlying_ltp':100,'strikes':{}}):
            out=inst._derivative_snapshot(['ABC','DEF'],{},datetime(2026,10,5,tzinfo=inst.IST),wall_clock_budget_seconds=10)
        self.assertTrue(out['budget_exhausted'])
        self.assertLessEqual(out['attempted'],1)
        self.assertIn('HARD_WALL_CLOCK',out['policy'])

    def test_order_preview_uses_actual_groww_depth_and_blocks_insufficient_counterparty(self):
        q={
            'last_price':100,'bid_price':99.9,'offer_price':100.1,
            'depth':{'buy':[{'price':99.9,'quantity':50}], 'sell':[{'price':100.1,'quantity':2}]},
            'upper_circuit_limit':120,'lower_circuit_limit':80,
        }
        with patch.object(orders.broker,'quote',return_value=q):
            out=orders._quote_execution_quality('X','LONG',100,quantity=5)
        self.assertTrue(out['hard_block'])
        self.assertIn('insufficient_displayed_depth_for_order_quantity',out['blockers'])
        self.assertEqual(out['sell_depth_quantity'],2.0)
        self.assertIsNotNone(out['depth_imbalance'])

    def test_research_framework_no_longer_calls_current_delivery_derivatives_or_pit_missing(self):
        out=main.research_framework()
        impl=' '.join(out['implemented_evidence_layers'])
        gaps=' '.join(out['remaining_data_gaps'])
        self.assertIn('NSE_DELIVERABLE_VOLUME',impl)
        self.assertIn('NSE_PIT_INSIDER',impl)
        self.assertIn('GROWW_FNO_OPTION_CHAIN',impl)
        self.assertNotIn('DERIVATIVES_POSITIONING_OI_PCR_IV_SKEW_WHERE_APPLICABLE',gaps)
        self.assertNotIn('AUTHORITATIVE_PER_STOCK_DELIVERABLE_VOLUME_PERCENTAGE_HISTORY',gaps)


if __name__ == '__main__':
    unittest.main()
