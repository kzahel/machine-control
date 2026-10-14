import collections
import unittest
from campaign import plan_rounds, MATRICES, reusable, snapshot_attempt
import json
from pathlib import Path
import tempfile


class CampaignPlanTest(unittest.TestCase):
    def test_each_supported_cell_appears_once_per_round(self):
        tasks=[f'task-{n}' for n in range(7)]
        rounds=plan_rounds(tasks,3,125)
        self.assertEqual([len(rows) for rows in rounds],[35,35,35])
        for index, rows in enumerate(rounds,1):
            self.assertEqual({r['repetition'] for r in rows},{index})
            self.assertEqual(collections.Counter(r['provider'] for r in rows),{'codex':21,'claude':14})
            self.assertFalse(any(r['provider']=='claude' and r['route']=='computer-use' for r in rows))
            self.assertEqual(len({(r['provider'],r['route'],r['task']) for r in rows}),35)
        self.assertEqual(rounds,plan_rounds(tasks,3,125))
        self.assertNotEqual(rounds,plan_rounds(tasks,3,126))

    def test_python_matrix_has_two_models_and_three_matched_rounds(self):
        rounds=plan_rounds([f'task-{n}' for n in range(7)],3,125,MATRICES['python'])
        self.assertEqual([len(rows) for rows in rounds],[14,14,14])
        for index,rows in enumerate(rounds,1):
            self.assertEqual({row['repetition'] for row in rows},{index})
            self.assertEqual({row['route'] for row in rows},{'mc-python'})
            self.assertEqual(collections.Counter(row['provider'] for row in rows),{'codex':7,'claude':7})

    def test_only_unqualified_attempts_are_retried(self):
        def attempt(n,valid,passed):
            return {'record':{'provider':'codex','task':'save','route':'cli','repetition':n,
                             'validTrial':valid,'passed':passed,'released':'discarded'}}
        attempts=[attempt(1,True,True),attempt(2,True,False),attempt(3,False,False)]
        self.assertEqual(reusable(attempts),{('codex','save','cli',1),('codex','save','cli',2)})
        with self.assertRaisesRegex(ValueError,'Duplicate qualified'):reusable(attempts+[attempts[0]])
        attempts[0]['record']['released']=None
        with self.assertRaisesRegex(ValueError,'disposal unresolved'):reusable(attempts)

    def test_changed_evaluation_evidence_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)
            (path/'trial.json').write_text('{}')
            (path/'transcript.jsonl').write_text('original')
            (path/'evaluation.json').write_text(json.dumps({'schema':'route-comparison-evaluation/v1',
                                                          'receiptSha256':'wrong'}))
            with self.assertRaisesRegex(ValueError,'evidence changed'):snapshot_attempt(path)


if __name__=='__main__':unittest.main()
