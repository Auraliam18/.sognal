import unittest
from unittest.mock import patch
from hamid import execution_gate, killswitch


class IntentContract(unittest.TestCase):
    base=dict(sym='BTCUSDT',dir='LONG',entry=100,sl=95,tp1=115,trend4='up',trend1='up')

    def check_signal(self, **updates):
        with patch.object(killswitch,'guard',return_value=True):
            return execution_gate.evaluate(dict(self.base,**updates))

    def test_valid_reference_sizing_and_fees(self):
        r=self.check_signal()
        self.assertTrue(r['ok'])
        self.assertLessEqual(r['intent']['sizing_ref_10k']['notional_usd'],2000)

    def test_missing_or_opposed_trend_veto(self):
        self.assertFalse(self.check_signal(trend4=None)['ok'])
        self.assertFalse(self.check_signal(trend4='down',trend1='down')['ok'])

    def test_countertrend_needs_evidence_and_label(self):
        self.assertFalse(self.check_signal(trend1='down',counter_trend_note='counter')['ok'])
        evidence=dict(trend1='down',counter_trend_note='counter',inOB=True,swept=True,choch=True,fvg=True,quality=70)
        self.assertTrue(self.check_signal(**evidence)['ok'])
        self.assertFalse(self.check_signal(**dict(evidence,quality=69))['ok'])

    def test_invalid_geometry_prices_and_missing_target(self):
        for update in ({'entry':float('nan')},{'sl':105},{'tp1':90},{'tp1':None},{'dir':'BUY'}):
            self.assertFalse(self.check_signal(**update)['ok'])

    def test_tripped_killswitch_blocks_intent(self):
        with patch.object(killswitch,'guard',return_value=False):
            self.assertFalse(execution_gate.evaluate(self.base)['ok'])


if __name__=='__main__':
    unittest.main()
