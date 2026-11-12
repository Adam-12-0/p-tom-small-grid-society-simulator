# Grid information flow

Run `grid_world.py` to open a dark 25 by 25 grid and a separate live line plot of people informed against time. Enter a population from 1 to 625 and restart. White dots are uninformed and red dots know the information. An outlined square marks the fixed source at cell **(12, 12)**. Drag the grid's time slider to inspect positions and awareness. The yellow cursor in the line plot follows that selection.

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python grid_world.py
```

## Controlled setup

The initial layout is deterministic. Starting at (0, 0), it repeatedly adds the cell farthest from the cells already selected, with fixed tie breaking. This spreads people across the grid. Increasing population from N to N+1 adds one person without relocating the first N people. The layout is a deliberately structured experimental choice, not a sample of a real society.

There is no randomly selected informed person. The center source stays active throughout the run. A person on the source cell or a cardinal neighbor learns from it, including at time zero. The initial informed count can therefore be zero or more, depending on the chosen population. The source is an environmental feature, so a person can occupy its cell.

Movement is the only effective randomness with sharing fixed at 1. Each time step shuffles all neighboring grid edges and greedily selects disjoint pairs. Paired cells swap contents simultaneously. People move into empty cells or swap with another person. Unpaired people stay for that step. Every move is at most one cardinal cell, with no collisions or wraparound.

The cell pairing schedule depends only on grid size, movement seed, and time. It does not depend on population or sharing events. With the same seed, the people common to two population settings follow exactly the same paths. The default seed is 1. Restarting the same configuration reproduces the same history. Changing `Config.seed` changes movement while leaving the layout and source fixed. A separate random stream is used if sharing is later set below 1; at 1, sharing does not draw random numbers.

A single controlled run describes one movement pattern. For population experiments, repeat each population with the same set of movement seeds, compare matched outcomes, and report variation and incomplete runs. Fixed initial placement removes one source of variation, but conclusions can still depend on that placement and the source location. The goal is full awareness; the default time limit is 500 steps.

## PSL rules

`psl_model.py` groups the executable rules in `psl_rules()`:

```text
SourceContact(P) -> Known(P) .
KnownPrev(P) -> Known(P) .
KnownPrev(P) & Adjacent(P,Q) & ShareEvent(P,Q) -> Known(Q) .
1: !Known(P) ^2
```

These rules are fixed. They contain no random choices. The first three hard rules encode learning from the fixed source, keeping information, and learning from a successful adjacent peer contact. The weak negative prior keeps unsupported awareness at zero. PSL performs inference on these observations at each step. The direct reference update is checked against actual PSL inference.

Movement is implemented in Python's `move()` function, not in PSL. Python also samples sharing events if their chance is below 1. The window fixes that chance at 1, so every eligible peer contact succeeds. Newly informed people can share starting at the next step. A PSL truth value or rule weight is not automatically a sharing probability.

The display implementation is in `display.py`. It runs PSL in the background while keeping both windows responsive. No LLM is used.

```bash
.venv/bin/python -m unittest discover -s tests
```
