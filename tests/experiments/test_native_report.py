import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('native_report', Path(__file__).parent/'native-efficiency/report.py')
report = importlib.util.module_from_spec(spec)
spec.loader.exec_module(report)


def state(**changes):
    return dict({'pid':2,'frontPid':2,'keyWindow':True,'cursor':[10,20],
                 'text':'','revision':0,'counters':{}}, **changes)


class EffectReportTest(unittest.TestCase):
    def test_provider_acceptance_does_not_prove_effect(self):
        r={'name':'background-button','seconds':.01,'result':{'accepted':True},
           'before':{'target':state(),'sentinel':state()},
           'after':{'target':state(),'sentinel':state()}}
        summary=report.summarize([r])[0]
        self.assertEqual(summary['refusalsOrErrors'],0)
        self.assertEqual(summary['effectPasses'],0)

    def test_restored_cursor_still_counts_as_disturbance(self):
        r={'name':'background-button','seconds':.01,'result':{'accepted':True},
           'before':{'target':state(),'sentinel':state()},
           'after':{'target':state(revision=1),
                    'sentinel':state(counters={'cursorMoved':2})}}
        summary=report.summarize([r])[0]
        self.assertEqual(summary['effectPasses'],1)
        self.assertEqual(summary['disturbances'],1)


if __name__=='__main__':unittest.main()
