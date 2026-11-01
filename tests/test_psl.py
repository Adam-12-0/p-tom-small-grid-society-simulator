import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from world import load_case
from rules import priority_scores

class PSLTests(unittest.TestCase):
    def test_weighted_priority(self):
        world=load_case(Path(__file__).resolve().parents[1]/'cases/workshop.json')
        scores=priority_scores(world,['W1','W2'])
        self.assertAlmostEqual(scores['W1'],0.6,places=2)
        self.assertAlmostEqual(scores['W2'],0.375,places=2)
        self.assertGreater(scores['W1'],scores['W2'])

if __name__=='__main__': unittest.main()
