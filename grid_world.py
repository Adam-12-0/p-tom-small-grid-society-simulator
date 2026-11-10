"""Minimal information-spread grid world. No LLM is used."""
from __future__ import annotations

from dataclasses import dataclass
import random


@dataclass(frozen=True)
class Config:
    size: int = 20
    people: int = 40
    share_probability: float = 1.0
    max_steps: int = 500
    seed: int = 1
    source: str = "center"  # or "edge"

    def __post_init__(self):
        if self.size < 2 or not 1 <= self.people <= self.size**2:
            raise ValueError("size must be at least 2 and people must fit in the grid")
        if not 0 <= self.share_probability <= 1 or self.max_steps < 0:
            raise ValueError("invalid sharing probability or step limit")
        if self.source not in {"center", "edge"}:
            raise ValueError("source must be center or edge")


@dataclass(frozen=True)
class Frame:
    step: int
    positions: tuple[tuple[int, int], ...]
    informed: frozenset[int]

    @property
    def fraction_informed(self) -> float:
        return len(self.informed) / len(self.positions)


def neighbors(point: tuple[int, int], size: int) -> list[tuple[int, int]]:
    x, y = point
    return [(a, b) for a, b in ((x-1,y), (x+1,y), (x,y-1), (x,y+1))
            if 0 <= a < size and 0 <= b < size]


def initial_positions(config: Config, rng: random.Random) -> tuple[tuple[int, int], ...]:
    cells = [(x, y) for y in range(config.size) for x in range(config.size)]
    return tuple(rng.sample(cells, config.people))


def source_id(positions: tuple[tuple[int, int], ...], config: Config) -> int:
    center = (config.size - 1) / 2
    if config.source == "center":
        return min(range(len(positions)), key=lambda i: ((positions[i][0]-center)**2 +
                                                         (positions[i][1]-center)**2, i))
    return min(range(len(positions)), key=lambda i: (min(positions[i][0], positions[i][1],
                                config.size-1-positions[i][0], config.size-1-positions[i][1]), i))


def move(positions: tuple[tuple[int, int], ...], size: int, rng: random.Random) -> tuple[tuple[int, int], ...]:
    """Each person attempts one cardinal move. Occupied destinations cause a swap."""
    places = list(positions)
    by_cell = {point: i for i, point in enumerate(places)}
    order = list(range(len(places)))
    rng.shuffle(order)
    for person in order:
        destination = rng.choice(neighbors(places[person], size))
        old = places[person]
        occupant = by_cell.get(destination)
        places[person] = destination
        by_cell[destination] = person
        if occupant is None:
            del by_cell[old]
        else:
            places[occupant] = old
            by_cell[old] = occupant
    return tuple(places)


def contact_events(positions: tuple[tuple[int, int], ...], informed: frozenset[int],
                   config: Config, rng: random.Random) -> set[tuple[int, int]]:
    """Sample directed sharing events, with no within-step cascade."""
    by_cell = {point: i for i, point in enumerate(positions)}
    events = set()
    for source in sorted(informed):
        for point in neighbors(positions[source], config.size):
            target = by_cell.get(point)
            if target is not None and target not in informed and rng.random() < config.share_probability:
                events.add((source, target))
    return events


def run(config: Config, engine: str = "direct") -> list[Frame]:
    if engine not in {"direct", "psl"}:
        raise ValueError("engine must be direct or psl")
    rng = random.Random(config.seed)
    positions = initial_positions(config, rng)
    informed = frozenset({source_id(positions, config)})
    history = [Frame(0, positions, informed)]
    for step in range(1, config.max_steps + 1):
        if len(informed) == config.people:
            break
        positions = move(positions, config.size, rng)
        receivers = contact_events(positions, informed, config, rng)
        if engine == "psl":
            from psl_model import infer_known
            updated = infer_known(config.people, informed, receivers, positions, config.size)
        else:
            updated = informed | {target for _, target in receivers}
        informed = frozenset(updated)
        history.append(Frame(step, positions, informed))
    return history
