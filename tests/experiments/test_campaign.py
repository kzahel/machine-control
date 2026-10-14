import collections
import unittest
from campaign import plan_rounds


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


if __name__=='__main__':unittest.main()
