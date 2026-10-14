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

    def test_failed_attempt_usage_is_retained_with_coverage(self):
        rows=[{'task':'save','route':'cli','repetition':n,'validTrial':True,
               'passed':n==1,'tokenUsage':{'input_tokens':n*100,'output_tokens':10}}
              for n in (1,2)]
        rows.append({'task':'save','route':'cli','repetition':3})
        group=summarize({'plan':rows},rows)['groups'][0]
        self.assertEqual(group['successfulTokenUsage']['totalTokens']['median'],110)
        self.assertEqual(group['allRecordedTokenUsage']['totalTokens']['median'],160)
        self.assertEqual(group['allRecordedTokenUsage']['totalTokens']['n'],2)
        self.assertIsNone(group['allRecordedTokenUsage']['cachedInputTokens'])


if __name__=='__main__':unittest.main()
