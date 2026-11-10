# Grid society information flow

A minimal model of how one piece of information spreads through a moving population. There is no LLM, aid scenario, or person-specific behavior. All people follow the same rules.

## Rules

- The world is a square grid. Each cell holds at most one person.
- One person near the center starts informed. You can instead choose an edge source.
- At each discrete time step, every person selects one cardinal neighbor. They move there if it is empty and swap places if it is occupied. This permits motion even at full density.
- After moving, each informed person may tell each adjacent uninformed person. For the first experiment, `share_probability=1`, so every such contact succeeds. New recipients begin sharing at the next time step.
- Informed people never forget the information. The goal is reached when all people know it. A run that reaches `max_steps` first is censored, not counted as completed.

The society parameter is population density, `people / size²`. Grid size is 20 by 20 by default. The share likelihood is present in the code for later experiments but is fixed at 1 for the baseline. Movement is fixed across all people and runs. A random seed makes each run reproducible.

## Run

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python run_experiment.py --compare
.venv/bin/python run_experiment.py --people 40 --seed 1
.venv/bin/python run_experiment.py --people 8 --size 5 --max-steps 20 --engine psl
.venv/bin/python visualize.py --people 40
.venv/bin/jupyter notebook information_flow.ipynb
```

`visualize.py` uses PyQtGraph for a live red/green scatter plot and a progress curve. The notebook opens the same interactive Qt window. It needs a graphical desktop. `run_experiment.py` works without a display.

## What PSL does here

The direct model computes the exact Boolean update. The PSL model observes `KnownPrev(P)` and the sharing events created after movement. It then infers `Known(P)` from two hard rules:

```text
KnownPrev(P) -> Known(P) .
KnownPrev(P) & ShareEvent(P,Q) -> Known(Q) .
```

A weak negative prior keeps unsupported `Known` atoms at zero. The model uses genuine PSL inference, but the hard rules make its result match the direct baseline. PSL does not choose movements or sample sharing events here. A PSL truth value or rule weight should not be called a calibrated chance of sharing. To represent a literal 50% sharing likelihood, the simulator samples a Bernoulli event before PSL inference. We can later test soft PSL rules as graded support, but they would need an explicit interpretation and validation before comparing them with behavioral probabilities.

## Measurements

`--compare` runs five seeds at three densities and reports completed runs and mean time to full awareness among completed runs. The completion count matters because incomplete runs are censored. For the default 20 by 20 grid, five seeded runs at each density all completed by step 500. Mean completion times were 209.8 steps for 10 people, 91.0 for 40 people, and 34.8 for 120 people. These are synthetic mechanism checks, not claims about real societies.
