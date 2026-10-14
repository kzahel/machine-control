import collections
import unittest
from campaign import plan_rounds, MATRICES


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


if __name__=='__main__':unittest.main()
