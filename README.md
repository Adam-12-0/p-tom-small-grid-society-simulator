# Grid information flow

Run `grid_world.py` to open an interactive 25 by 25 society. Enter a population from 1 to 625 and press **Restart simulation**. The high contrast dark grid uses red for people who have not heard the information and green for people who have heard it. The counter shows how many people know it at the selected time. Drag the slider to inspect earlier or later steps, or use Play and Pause. A second dark window plots the number informed against time. Its yellow line marks the time selected in the grid window, and its dashed line marks the full-population goal.

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python grid_world.py
```

The window computes new steps in the background, so it stays responsive while PSL runs. A restarted simulation uses the same random seed. This makes two population settings easier to compare. There is no LLM.

## Rules

The simulation starts with one informed person near the center. At each time step, the model randomly pairs neighboring cells. No cell belongs to more than one pair. All pairs swap their contents at once, so a person moves into an empty cell or exchanges places with another person. Anyone without a pair stays for that step. This avoids collisions and lets dense populations move too. People share only with adjacent neighbors after moving. The sharing likelihood is fixed at 1 in the window, so each eligible contact succeeds. A new recipient can share at the next step. The goal is reached when everyone is informed, or the run stops at 500 steps.

The population is the society parameter. Density is `population / 625`. Movement and sharing rules are identical for all people. The code keeps the physical movement and contact sampling in `grid_world.py`. The actual PSL rules are grouped and commented in `psl_model.py`, in the `psl_rules()` function:

```text
KnownPrev(P) -> Known(P) .
KnownPrev(P) & Adjacent(P,Q) & ShareEvent(P,Q) -> Known(Q) .
1: !Known(P) ^2
```

PSL infers the next awareness state from the previous state and observed sharing contacts. The hard rules make the state Boolean here. The final weak rule keeps unsupported awareness at zero. Movement and any future sharing chance are outside PSL. A PSL soft truth value or rule weight is not automatically a probability of sharing.

For a small check without the window:

```bash
.venv/bin/python -m unittest discover -s tests
```
