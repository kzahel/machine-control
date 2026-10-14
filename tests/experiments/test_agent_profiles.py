import json
import unittest
from agent_profiles import launch_request,qualify
from measurements import claude_transcript_metrics


def row(kind, second, message, **extra):
    return {'type':kind,'timestamp':f'2026-01-01T00:00:{second:02}Z','message':message,**extra}


class ClaudeMetricsTest(unittest.TestCase):
    def test_streamed_blocks_and_repeated_usage_are_deduplicated(self):
        usage={'input_tokens':3,'cache_creation_input_tokens':10,'cache_read_input_tokens':20,
               'output_tokens':4,'service_tier':'standard','speed':'standard'}
        assistant={'id':'m1','model':'claude-opus-5-5','usage':usage,'stop_reason':'tool_use',
                   'content':[{'type':'tool_use','id':'t1','name':'Bash','input':{}}]}
        final={'id':'m2','model':'claude-opus-5-5','usage':{**usage,'output_tokens':6},
               'stop_reason':'end_turn','content':[{'type':'text','text':'done'}]}
        rows=[row('user',0,{'content':'task'}),row('assistant',1,assistant,effort='medium'),
              row('assistant',2,assistant,effort='medium'),
              row('user',3,{'content':[{'type':'tool_result','tool_use_id':'t1','content':'ok'}]}),
              row('assistant',4,final,effort='medium')]
        result=claude_transcript_metrics('\n'.join(json.dumps(r) for r in rows))
        self.assertEqual(result['agentSeconds'],4)
        self.assertEqual(result['toolCalls'],1)
        self.assertEqual(result['tokenUsage']['output_tokens'],10)
        self.assertEqual(result['tokenUsage']['input_tokens'],6)
        self.assertEqual(result['toolOutputBytes'],2)
        self.assertTrue(qualify('claude','claude-opus-5-5','medium',result,{})['qualified'])

    def test_partial_turn_is_not_complete(self):
        value=claude_transcript_metrics(json.dumps(row('user',0,{'content':'task'})))
        self.assertFalse(value['transcriptComplete'])
        self.assertIsNone(value['tokenUsage'])

    def test_wrong_effort_and_speed_refuse(self):
        metrics={'modelContexts':[{'model':'claude-opus-5-5','effort':'high','speed':'fast','service_tier':'standard'}]}
        value=qualify('claude','claude-opus-5-5','medium',metrics,{})
        self.assertFalse(value['qualified'])
        self.assertEqual(len(value['reasons']),2)

    def test_request_is_explicit_and_missing_effective_settings_refuse(self):
        request=launch_request('codex','gpt-6.1-sol','medium','task')
        self.assertEqual(request['thinking'],'medium')
        self.assertEqual(request['serviceTier'],'default')
        self.assertFalse(qualify('codex','gpt-6.1-sol','medium',{}, {})['qualified'])


if __name__=='__main__':unittest.main()
