"""Checks for aid-case PSL grounding, hard constraints, and complete traces."""
import unittest
from copy import deepcopy
from pathlib import Path

import aid_psl as sim

CASE = Path(__file__).resolve().parents[1] / 'cases/aid_baseline.json'


class AidPSLTests(unittest.TestCase):
    def test_trusted_contact_changes_awareness(self):
        case = sim.read_case(CASE)
        people = sim.initial_people(case)
        people['P01']['shared_prev'] = 1
        linked, _ = sim.person_inference(case, people)
        isolated = deepcopy(case)
        isolated['contacts'] = [pair for pair in case['contacts'] if 'P01' not in pair]
        unlinked, _ = sim.person_inference(isolated, people)
        self.assertGreater(linked['Aware']['P02'], unlinked['Aware']['P02'] + .1)

    def test_hard_receipt_constraints(self):
        case = sim.read_case(CASE)
        people = sim.initial_people(case)
        people['P01']['position'] = list(case['aid_site'])
        people['P01']['served'] = 1
        scores, _ = sim.person_inference(case, people)
        self.assertLess(scores['ReceiveNow']['P01'], 1e-4)
        self.assertLess(scores['ReceiveNow']['P02'], 1e-4)

    def test_lower_perceived_safety_reduces_intent(self):
        case = sim.read_case(CASE)
        people = sim.initial_people(case)
        people['P04']['awareness'] = 1.0
        high, _ = sim.person_inference(case, people)
        people['P04']['safety'] = 0.2
        low, _ = sim.person_inference(case, people)
        self.assertLess(low['Intent']['P04'], high['Intent']['P04'] - .05)

    def test_completed_runs_and_intervention_order(self):
        outcomes = {}
        for name in ('aid_baseline', 'aid_outreach', 'aid_access', 'aid_outreach_access'):
            result = sim.run_case(CASE.parent / f'{name}.json')
            self.assertEqual(len(result['trace']), 20)
            outcomes[name] = result['result']
            served, shared = set(), set()
            for record in result['trace']:
                for action in record['actions']:
                    pid = action['person']
                    if action['action'] == 'move':
                        start, end = action['from'], action['to']
                        self.assertEqual(abs(start[0]-end[0]) + abs(start[1]-end[1]), 1)
                        self.assertTrue(sim.valid_cell(result['configuration'], end))
                    if action['action'] == 'receive':
                        self.assertNotIn(pid, served)
                        self.assertEqual(record['before'][pid]['position'], result['configuration']['aid_site'])
                        served.add(pid)
                    if action['action'] == 'share':
                        self.assertNotIn(pid, shared)
                        shared.add(pid)
            self.assertEqual(result['result']['uptake'], len(served) / 16)
        self.assertEqual([outcomes[name]['uptake'] for name in
                          ('aid_baseline', 'aid_outreach', 'aid_access', 'aid_outreach_access')],
                         [.375, .375, .5625, .5625])
        self.assertGreater(outcomes['aid_outreach']['awareness'],
                           outcomes['aid_baseline']['awareness'] + .3)


if __name__ == '__main__':
    unittest.main()
