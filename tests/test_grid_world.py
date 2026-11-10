import sys
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from grid_world import Config, initial_positions, move, run
import random


class GridWorldTests(unittest.TestCase):
    def test_reproducible_and_monotone(self):
        config = Config(size=8, people=20, max_steps=40, seed=11)
        a, b = run(config), run(config)
        self.assertEqual(a, b)
        for before, after in zip(a, a[1:]):
            self.assertLessEqual(before.informed, after.informed)
            self.assertEqual(len(after.positions), len(set(after.positions)))
            self.assertTrue(all(0 <= x < config.size and 0 <= y < config.size
                                for x, y in after.positions))

    def test_zero_sharing_cannot_spread(self):
        history = run(Config(size=5, people=10, share_probability=0, max_steps=15))
        self.assertEqual(len(history[-1].informed), 1)

    def test_dense_grid_can_move_by_swapping(self):
        config = Config(size=3, people=9)
        rng = random.Random(7)
        before = initial_positions(config, rng)
        after = move(before, config.size, rng)
        self.assertEqual(set(before), set(after))
        self.assertNotEqual(before, after)

    def test_psl_matches_direct_update(self):
        config = Config(size=5, people=10, max_steps=5, seed=3)
        self.assertEqual(run(config), run(config, 'psl'))


if __name__ == '__main__':
    unittest.main()
