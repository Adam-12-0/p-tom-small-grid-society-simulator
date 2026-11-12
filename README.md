# Grid information flow

Run `grid_world.py` to open a dark 25 by 25 grid and a separate live line plot of people informed against time. Enter a population from 1 to 625 and restart. White dots are uninformed and red dots know the information. Exactly one person starts informed at cell **(12, 12)** and then moves with everyone else. Drag the grid's time slider to inspect positions and awareness. The yellow cursor in the line plot follows that selection.

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python grid_world.py
```

## Controlled setup

The initial layout is deterministic. Starting with person 0 at the center, it repeatedly adds the cell farthest from the cells already selected, with fixed tie breaking. This spreads people across the grid. Increasing population from N to N+1 adds one person without relocating the first N people. The layout is a deliberately structured experimental choice, not a sample of a real society.

Person 0 always starts at the center, already informed. All other people start uninformed, including adjacent people. Sharing begins after the first movement step. The center cell has no special behavior after initialization. Information spreads only through people; the initial informed person follows the same movement and sharing rules as everyone else.

Movement is the only effective randomness with sharing fixed at 1. Time is the turn number. On each turn, every person independently proposes one adjacent cell, chosen uniformly from valid up/down/left/right neighbors. If multiple people choose the same destination, a random priority selects one winner. A move into an occupied cell is allowed only if its occupant also has an accepted move. Blocked moves are cancelled repeatedly until no collisions remain. Accepted moves happen simultaneously, followed by information sharing. Losing or blocked people stay for that turn without choosing again. Mutual swaps, cycles, and chains leading to an empty cell are allowed. There is no automatic swap with a stationary occupant, overlap, or wraparound.

The default movement seed is 1. Each person receives an independent reproducible random stream for each turn. Adding people preserves the random streams for existing person IDs, but paths can change because crowding changes which moves are accepted. Restarting the same configuration reproduces the same history. Changing `Config.seed` changes movement while leaving the layout and initial informed person fixed. A separate random stream is used if sharing is later set below 1; at 1, sharing does not draw random numbers.

A single controlled run describes one movement pattern. For population experiments, repeat each population with the same set of movement seeds, compare matched outcomes, and report variation and incomplete runs. Fixed initial placement removes one source of variation, but conclusions can still depend on that placement and the initial informed person's location. The goal is full awareness; the default time limit is 500 steps.

## PSL rules

`psl_model.py` groups the executable rules in `psl_rules()`:

```text
KnownPrev(P) -> Known(P) .
KnownPrev(P) & Adjacent(P,Q) & ShareEvent(P,Q) -> Known(Q) .
1: !Known(P) ^2
```

These rules are fixed. They contain no random choices. The two hard rules encode keeping information and learning from a successful adjacent peer contact. The weak negative prior keeps unsupported awareness at zero. PSL performs inference on these observations at each step. The direct reference update is checked against actual PSL inference.

Movement is implemented in Python's `move()` function, not in PSL. Python also samples sharing events if their chance is below 1. The window fixes that chance at 1, so every eligible peer contact succeeds. Newly informed people can share starting at the next step. A PSL truth value or rule weight is not automatically a sharing probability.

The display implementation is in `display.py`. It runs PSL in the background while keeping both windows responsive. No LLM is used.

```bash
.venv/bin/python -m unittest discover -s tests
```
