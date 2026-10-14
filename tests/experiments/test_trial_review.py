import json
from pathlib import Path
import tempfile
import unittest
from review_trial import annotation, calls_from, load_review, reevaluate, load_receipt


class TrialReviewTest(unittest.TestCase):
    def transcript(self):
        call={'type':'response_item','payload':{'type':'custom_tool_call',
              'call_id':'first','name':'exec','input':'read docs'}}
        return '\n'.join(map(json.dumps,[call,call,
            {'type':'event_msg','payload':{'type':'token_count','info':{
                'total_token_usage':{'input_tokens':100,'output_tokens':20,'cached_input_tokens':30}}}},
            {'type':'response_item','payload':{'type':'custom_tool_call',
             'call_id':'second','name':'exec','input':'observe and act'}}]))

    def test_deduplicated_call_indices_and_reported_usage_checkpoint(self):
        text=self.transcript()
        self.assertEqual(len(calls_from(text,'codex')),2)
        value=annotation(text,'codex',adherence='conforming',first_ui=2,discovery=[1],notes='Reviewed')
        self.assertEqual(value['preUIDiscoveryCalls'],[1])
        self.assertEqual(value['usageReportedBeforeFirstUICall']['totalTokens'],120)
        self.assertEqual(value['firstUICall'],2)

    def test_claude_streamed_tool_blocks_are_counted_once(self):
        row={'type':'assistant','message':{'content':[{'type':'tool_use','id':'call','name':'Bash','input':{'command':'help'}}]}}
        self.assertEqual(len(calls_from('\n'.join(map(json.dumps,[row,row])),'claude')),1)

    def test_confirmation_judgment_is_separate_and_defaults_unknown(self):
        args=dict(adherence='conforming',first_ui=2,discovery=[1],notes='Reviewed')
        value=annotation(self.transcript(),'codex',**args)
        self.assertEqual(value['confirmationPolicyAdherence'],'unreviewed')
        value=annotation(self.transcript(),'codex',**args,confirmation_adherence='violated')
        self.assertEqual(value['routeAdherence'],'conforming')
        self.assertEqual(value['confirmationPolicyAdherence'],'violated')
        with self.assertRaises(ValueError):
            annotation(self.transcript(),'codex',**args,confirmation_adherence='guessed')

    def test_invalid_indices_do_not_become_discovery_metrics(self):
        for first,discovery in [(3,[1]),(2,[2]),(2,[1,1]),(None,[4])]:
            with self.assertRaises(ValueError):
                annotation(self.transcript(),'codex',adherence='conforming',first_ui=first,discovery=discovery,notes='')

    def test_review_is_bound_to_the_exact_transcript(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)
            self.assertIsNone(load_review(path))
            text=self.transcript()
            (path/'transcript.jsonl').write_text(text)
            value=annotation(text,'codex',adherence='uncertain',first_ui=2,discovery=[],notes='Inspect result')
            (path/'review.json').write_text(json.dumps(value))
            self.assertEqual(load_review(path)['routeAdherence'],'uncertain')
            (path/'transcript.jsonl').write_text(text+'\n')
            with self.assertRaisesRegex(ValueError,'bound to this transcript'):load_review(path)

    def test_reanalysis_preserves_original_and_cannot_promote_failed_oracle(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)
            receipt={'provider':'claude','requestedModel':'claude-opus-5-5',
                     'requestedEffort':'medium','effectiveProcess':{},'oracleExit':0,
                     'oracle':{'passed':True},'validTrial':False}
            (path/'trial.json').write_text(json.dumps(receipt))
            original=(path/'trial.json').read_bytes()
            rows=[{'type':'user','timestamp':'2026-01-01T00:00:00Z','message':{'content':'task'}},
                  {'type':'user','isMeta':True,'timestamp':'2026-01-01T00:00:01Z','message':{'content':'image metadata'}},
                  {'type':'assistant','timestamp':'2026-01-01T00:00:02Z','effort':'medium',
                   'message':{'id':'m1','model':'claude-opus-5-5','stop_reason':'end_turn',
                              'usage':{'speed':'standard','service_tier':'standard'}}}]
            (path/'transcript.jsonl').write_text('\n'.join(map(json.dumps,rows)))
            evaluation=reevaluate(path,reason='metadata correction')
            self.assertTrue(evaluation['record']['passed'])
            self.assertEqual((path/'trial.json').read_bytes(),original)
            (path/'evaluation.json').write_text(json.dumps(evaluation))
            self.assertEqual(load_receipt(path)['agentSeconds'],2)
            self.assertFalse(reevaluate(path,reason='bad oracle',invalidate_oracle=True)['record']['validTrial'])
            receipt['oracle']['passed']=False
            (path/'trial.json').write_text(json.dumps(receipt))
            self.assertFalse(reevaluate(path,reason='metadata correction')['record']['passed'])
            with self.assertRaisesRegex(ValueError,'not bound'):load_receipt(path)


if __name__=='__main__':unittest.main()
