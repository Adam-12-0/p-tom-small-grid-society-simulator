"""Information spreading on a 25 by 25 grid. Run this file to open the viewer."""
from __future__ import annotations

from dataclasses import dataclass
import random
from functools import lru_cache
from typing import Iterator


@dataclass(frozen=True)
class Config:
    size: int = 25
    people: int = 40
    share_probability: float = 1.0
    max_steps: int = 500
    seed: int = 1

    def __post_init__(self):
        if self.size < 2 or not 1 <= self.people <= self.size * self.size:
            raise ValueError("Population must fit in a grid at least 2 by 2.")
        if not 0 <= self.share_probability <= 1 or self.max_steps < 0:
            raise ValueError("Invalid sharing likelihood or time limit.")


@dataclass(frozen=True)
class Frame:
    step: int
    positions: tuple[tuple[int, int], ...]
    informed: frozenset[int]

    @property
    def fraction_informed(self) -> float:
        return len(self.informed) / len(self.positions)


def neighbors(point: tuple[int, int], size: int) -> list[tuple[int, int]]:
    """The four adjacent cells, excluding cells beyond the grid edge."""
    x, y = point
    return [(a, b) for a, b in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1))
            if 0 <= a < size and 0 <= b < size]


@lru_cache(maxsize=None)
def layout_cells(size: int) -> tuple[tuple[int, int], ...]:
    """A fixed, nested layout: repeatedly choose the farthest unfilled cell.

    Put person 0 at the center. Break distance ties in row-major order. This distributes
    sparse populations across the grid without consuming any random numbers.
    The first N cells are unchanged when the population is increased.
    """
    remaining = [(x, y) for y in range(size) for x in range(size)]
    distances = {cell: float("inf") for cell in remaining}
    ordered = []
    chosen = (size // 2, size // 2)
    while remaining:
        remaining.remove(chosen)
        ordered.append(chosen)
        for cell in remaining:
            distance = (cell[0] - chosen[0]) ** 2 + (cell[1] - chosen[1]) ** 2
            distances[cell] = min(distances[cell], distance)
        if remaining:
            chosen = max(remaining, key=lambda cell: distances[cell])
    return tuple(ordered)


def initial_positions(config: Config) -> tuple[tuple[int, int], ...]:
    return layout_cells(config.size)[:config.people]


def move(positions: tuple[tuple[int, int], ...], size: int,
         rng: random.Random) -> tuple[tuple[int, int], ...]:
    """Move people simultaneously through disjoint random neighboring pairs.

    Every person is considered for a move. A selected pair swaps its contents:
    a person enters an empty cell, or two people exchange occupied cells.
    Because no cell belongs to two pairs, there are no collisions or update
    order effects. Unpaired people stay at their current cells for this step.
    """
    occupied = {point: i for i, point in enumerate(positions)}
    # Include every grid edge, even between empty cells. The resulting cell
    # pairing schedule is identical across populations when the seed is fixed.
    edges = {(min(point, other), max(point, other))
             for y in range(size) for x in range(size)
             for point in [(x, y)] for other in neighbors(point, size)}
    candidates = sorted(edges)
    rng.shuffle(candidates)
    used_cells = set()
    moved = list(positions)
    for a, b in candidates:
        if a in used_cells or b in used_cells:
            continue
        used_cells.update((a, b))
        person_a = occupied.get(a)
        person_b = occupied.get(b)
        if person_a is not None:
            moved[person_a] = b
        if person_b is not None:
            moved[person_b] = a
    return tuple(moved)


def adjacent_pairs(positions: tuple[tuple[int, int], ...],
                   size: int) -> set[tuple[int, int]]:
    """Observed directed contacts for the current time step."""
    by_cell = {point: i for i, point in enumerate(positions)}
    return {(i, by_cell[point]) for i, location in enumerate(positions)
            for point in neighbors(location, size) if point in by_cell}


def sharing_events(adjacency: set[tuple[int, int]], informed: frozenset[int],
                   chance: float, rng: random.Random) -> set[tuple[int, int]]:
    """Only people informed before this step can share during this step."""
    eligible = {(source, target) for source, target in adjacency
                if source in informed and target not in informed}
    if chance == 1:
        return eligible
    return {event for event in sorted(eligible) if rng.random() < chance}


def run_steps(config: Config, engine: str = "psl") -> Iterator[Frame]:
    """Yield frames as they are computed so the window stays responsive."""
    if engine not in {"psl", "direct"}:
        raise ValueError("Engine must be 'psl' or 'direct'.")
    movement_rng = random.Random(config.seed)
    sharing_rng = random.Random(config.seed + 1)
    positions = initial_positions(config)
    # The same designated person starts at the center in every population.
    # Information then travels with people, without an environmental source.
    informed = frozenset({0})
    yield Frame(0, positions, informed)
    for step in range(1, config.max_steps + 1):
        if len(informed) == config.people:
            break
        positions = move(positions, config.size, movement_rng)
        adjacency = adjacent_pairs(positions, config.size)
        events = sharing_events(adjacency, informed, config.share_probability, sharing_rng)
        if engine == "psl":
            from psl_model import infer_known
            informed = infer_known(config.people, informed, adjacency, events)
        else:
            informed = informed | frozenset(target for _, target in events)
        yield Frame(step, positions, informed)


def run(config: Config, engine: str = "psl") -> list[Frame]:
    """Return the complete history for a small experiment or test."""
    return list(run_steps(config, engine))


if __name__ == "__main__":
    from display import display
    display(run_steps, Config)
