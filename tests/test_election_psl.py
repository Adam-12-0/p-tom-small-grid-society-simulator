"""Checks for PSL grounding, hard constraints, and full-run mechanics."""
import unittest
from copy import deepcopy
from pathlib import Path

import election_psl as sim

CASE = Path(__file__).resolve().parents[1] / 'cases/election_turnout.json'


class ElectionPSLTests(unittest.TestCase):
    def test_contact_changes_awareness_inference(self):
        case = sim.read_case(CASE)
        people = sim.initial_people(case)
        people['P01']['shared_prev'] = 1
        linked, _ = sim.individual_inference(case, people)
        isolated = deepcopy(case)
        isolated['contacts'] = [pair for pair in case['contacts'] if 'P01' not in pair]
        unlinked, _ = sim.individual_inference(isolated, people)
        self.assertGreater(linked['Aware']['P02'], unlinked['Aware']['P02'] + 0.1)

    def test_hard_vote_constraints(self):
        case = sim.read_case(CASE)
        people = sim.initial_people(case)
        people['P01']['position'] = list(case['polling_site'])
        people['P01']['registered'] = 0
        people['P05']['position'] = list(case['polling_site'])
        people['P05']['voted'] = 1
        scores, _ = sim.individual_inference(case, people)
        self.assertLess(scores['VoteNow']['P01'], 1e-4)
        self.assertLess(scores['VoteNow']['P05'], 1e-4)
        self.assertLess(scores['VoteNow']['P02'], 1e-4)

    def test_completed_runs_obey_grid_and_vote_rules(self):
        cases = ['election_turnout', 'election_turnout_reminder', 'election_turnout_reminder_access']
        totals = []
        for name in cases:
            result = sim.run_case(CASE.parent / f'{name}.json')
            totals.append(result['result']['turnout'])
            seen_votes = set()
            seen_shares = set()
            for record in result['trace']:
                for action in record['actions']:
                    pid = action['person']
                    if action['action'] == 'move':
                        start, end = action['from'], action['to']
                        self.assertEqual(abs(start[0] - end[0]) + abs(start[1] - end[1]), 1)
                        self.assertTrue(sim.valid_cell(result['configuration'], end))
                    elif action['action'] == 'vote':
                        self.assertNotIn(pid, seen_votes)
                        seen_votes.add(pid)
                        self.assertEqual(record['before'][pid]['registered'], 1)
                        self.assertEqual(record['before'][pid]['position'], result['configuration']['polling_site'])
                    elif action['action'] == 'share':
                        self.assertNotIn(pid, seen_shares)
                        seen_shares.add(pid)
            self.assertEqual(result['result']['turnout'], len(seen_votes) / 16)
        self.assertEqual(totals[:2], [0.25, 0.25])
        self.assertGreater(totals[2], totals[1])


if __name__ == '__main__':
    unittest.main()
