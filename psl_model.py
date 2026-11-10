"""PSL infers awareness from observed previous awareness and sampled contact events."""
from __future__ import annotations


def infer_known(people: int, prior: frozenset[int], events: set[tuple[int, int]],
                positions: tuple[tuple[int, int], ...], size: int) -> frozenset[int]:
    from pslpython.model import Model
    from pslpython.partition import Partition
    from pslpython.predicate import Predicate
    from pslpython.rule import Rule
    from grid_world import neighbors

    model = Model("information-flow")
    model.add_predicate(Predicate("KnownPrev", size=1))
    model.add_predicate(Predicate("Adjacent", size=2))
    model.add_predicate(Predicate("ShareEvent", size=2))
    model.add_predicate(Predicate("Known", size=1))
    model.add_rule(Rule("KnownPrev(P) -> Known(P) ."))
    model.add_rule(Rule("KnownPrev(P) & Adjacent(P,Q) & ShareEvent(P,Q) -> Known(Q) ."))
    model.add_rule(Rule("1: !Known(P) ^2"))
    model.get_predicate("KnownPrev").add_data(Partition.OBSERVATIONS,
                                              [(str(i), float(i in prior)) for i in range(people)])
    by_cell = {point: i for i, point in enumerate(positions)}
    adjacency = [(str(i), str(by_cell[point]), 1.0)
                 for i, location in enumerate(positions)
                 for point in neighbors(location, size) if point in by_cell]
    if adjacency:
        model.get_predicate("Adjacent").add_data(Partition.OBSERVATIONS, adjacency)
    if events:
        model.get_predicate("ShareEvent").add_data(Partition.OBSERVATIONS,
                                                 [(str(source), str(target), 1.0) for source, target in sorted(events)])
    model.get_predicate("Known").add_data(Partition.TARGETS, [(str(i),) for i in range(people)])
    table = model.infer(psl_options={"runtime.log.level": "ERROR"})[model.get_predicate("Known")]
    return frozenset(int(person) for person, value in table.itertuples(index=False, name=None)
                     if value > 0.5)
