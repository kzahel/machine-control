import unittest
from report_batch import summarize


class BatchReportTest(unittest.TestCase):
    def test_incomplete_batch_and_invalid_fast_trial(self):
        plan={'plan':[{'task':'save','route':'cli','repetition':n} for n in (1,2,3)]}
        rows=[{'task':'save','route':'cli','repetition':1,'validTrial':True,'passed':True,
               'agentSeconds':20,'toolCalls':4,'released':'discarded'},
              {'task':'save','route':'cli','repetition':2,'validTrial':False,'passed':False,
               'agentSeconds':1,'toolCalls':1,'timedOut':True,'released':'discarded'}]
        result=summarize(plan,rows)
        self.assertFalse(result['complete'])
        self.assertEqual(result['missingTrials'],1)
        self.assertEqual(result['groups'][0]['successfulAgentSeconds']['median'],20)
        self.assertEqual(result['groups'][0]['timedOut'],1)

    def test_duplicate_cannot_make_batch_complete(self):
        row={'task':'save','route':'cli','repetition':1}
        result=summarize({'plan':[row]},[row,row])
        self.assertFalse(result['complete'])
        self.assertEqual(result['duplicateTrials'],1)


if __name__=='__main__':unittest.main()
