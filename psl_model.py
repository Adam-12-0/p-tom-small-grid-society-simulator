"""The PSL rules for one information-sharing time step."""
from __future__ import annotations

import warnings

warnings.filterwarnings("ignore", category=FutureWarning, module=r"pslpython\.predicate")


def psl_rules() -> tuple[str, ...]:
    """Return the actual rules used by PSL inference.

    KnownPrev(P) is whether P knew the information at the start of this step.
    Adjacent(P,Q) means their cells touch along an edge after movement.
    ShareEvent(P,Q) records a successful sharing action this step.
    SourceContact(P) means P is on or next to the fixed information source.
    Known(P) is the awareness state PSL must infer for the next step.
    """
    return (
        # The fixed source is always active. Direct contact informs a person.
        "SourceContact(P) -> Known(P) .",
        # Once a person knows, they keep knowing. This is a hard rule.
        "KnownPrev(P) -> Known(P) .",
        # A successful adjacent contact informs its recipient. New recipients
        # cannot share until the next time step because KnownPrev is fixed.
        "KnownPrev(P) & Adjacent(P,Q) & ShareEvent(P,Q) -> Known(Q) .",
        # Without support from either rule, awareness stays at zero.
        "1: !Known(P) ^2",
    )


def infer_known(people: int, prior: frozenset[int],
                adjacency: set[tuple[int, int]],
                events: set[tuple[int, int]],
                source_contact: frozenset[int]) -> frozenset[int]:
    """Run PSL on observed positions and sharing actions for one step."""
    from pslpython.model import Model
    from pslpython.partition import Partition
    from pslpython.predicate import Predicate
    from pslpython.rule import Rule

    model = Model("information-flow")
    for name, arity in (("KnownPrev", 1), ("Adjacent", 2),
                        ("ShareEvent", 2), ("SourceContact", 1), ("Known", 1)):
        model.add_predicate(Predicate(name, size=arity))
    for rule in psl_rules():
        model.add_rule(Rule(rule))

    model.get_predicate("KnownPrev").add_data(
        Partition.OBSERVATIONS,
        [(str(i), float(i in prior)) for i in range(people)],
    )
    model.get_predicate("SourceContact").add_data(
        Partition.OBSERVATIONS,
        [(str(i), float(i in source_contact)) for i in range(people)],
    )
    if adjacency:
        model.get_predicate("Adjacent").add_data(
            Partition.OBSERVATIONS,
            [(str(a), str(b), 1.0) for a, b in sorted(adjacency)],
        )
    if events:
        model.get_predicate("ShareEvent").add_data(
            Partition.OBSERVATIONS,
            [(str(a), str(b), 1.0) for a, b in sorted(events)],
        )
    model.get_predicate("Known").add_data(
        Partition.TARGETS, [(str(i),) for i in range(people)],
    )
    values = model.infer(psl_options={"runtime.log.level": "ERROR"})[
        model.get_predicate("Known")]
    return frozenset(int(person) for person, value in values.itertuples(index=False, name=None)
                     if value > 0.5)
