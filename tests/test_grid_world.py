import sys
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from grid_world import Config, initial_positions, move, run
import random


class GridWorldTests(unittest.TestCase):
    def test_default_grid_size(self):
        self.assertEqual(Config().size, 25)

    def test_reproducible_and_monotone(self):
        config = Config(size=8, people=20, max_steps=40, seed=11)
        a, b = run(config, 'direct'), run(config, 'direct')
        self.assertEqual(a, b)
        for before, after in zip(a, a[1:]):
            self.assertLessEqual(before.informed, after.informed)
            for (x0, y0), (x1, y1) in zip(before.positions, after.positions):
                self.assertLessEqual(abs(x0 - x1) + abs(y0 - y1), 1)
            self.assertEqual(len(after.positions), len(set(after.positions)))
            self.assertTrue(all(0 <= x < config.size and 0 <= y < config.size
                                for x, y in after.positions))

    def test_zero_sharing_keeps_exactly_one_informed(self):
        history = run(Config(size=5, people=10, share_probability=0, max_steps=15), 'direct')
        self.assertTrue(all(frame.informed == frozenset({0}) for frame in history))

    def test_exactly_one_informed_person_starts_at_center(self):
        for people in (1, 10, 40, 625):
            frame = run(Config(people=people, max_steps=0), 'direct')[0]
            self.assertEqual(frame.positions[0], (12, 12))
            self.assertEqual(frame.informed, frozenset({0}))

    def test_layout_is_nested_and_independent_of_movement_seed(self):
        small = initial_positions(Config(size=8, people=10, seed=1))
        large = initial_positions(Config(size=8, people=20, seed=99))
        self.assertEqual(small, large[:10])
        self.assertEqual(len(large), len(set(large)))

    def test_shared_people_have_identical_paths_across_populations(self):
        small = initial_positions(Config(size=8, people=10))
        large = initial_positions(Config(size=8, people=20))
        rng_small, rng_large = random.Random(7), random.Random(7)
        for _ in range(15):
            small = move(small, 8, rng_small)
            large = move(large, 8, rng_large)
            self.assertEqual(small, large[:10])

    def test_psl_does_not_inform_without_peer_support(self):
        from psl_model import infer_known
        self.assertEqual(infer_known(3, frozenset({0}), set(), set()),
                         frozenset({0}))

    def test_dense_grid_can_move_by_swapping(self):
        config = Config(size=3, people=9)
        rng = random.Random(7)
        before = initial_positions(config)
        after = move(before, config.size, rng)
        self.assertEqual(set(before), set(after))
        self.assertNotEqual(before, after)

    def test_psl_matches_direct_update(self):
        config = Config(size=5, people=10, max_steps=5, seed=3)
        self.assertEqual(run(config, 'direct'), run(config, 'psl'))


if __name__ == '__main__':
    unittest.main()
