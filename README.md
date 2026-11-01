# Small Grid Society Simulator

This is the first working version of the P-ToM grid society idea. It puts a few people in a small place, gives each person a task, and shows what happens one step at a time. The first two places are a library and a workshop. The rules are simple enough to inspect by hand. The goal is to see the world change, check that the rules work, and create a starting point for later P-ToM experiments.

The main result so far is that both worlds run from start to finish with manual rules. A small probabilistic soft logic (PSL) policy also runs in the workshop. Azure GPT-6 Luna can choose actions for the people. It completed the library task in the saved run, but did not complete the workshop task within its 40-step limit. These are checks of this small simulator. They are not evidence that it predicts real human behavior.

## Start by watching a saved run

Open [World Progression.txt](<runs/World Progression.txt>). It shows every saved run from step 0 onward. Each step has a complete grid, the actions and events, the values that changed, and a short summary of everyone’s state. Model runs also show the model’s choices and any validation errors. The file has clear `RUN:` headings, so you can search for `RUN: library-manual` or `RUN: workshop-azure-full` to jump to a case.

Open [World States.tsv](<runs/World States.tsv>) when you want a compact table. Each row is one person at one step. The columns include position, task, status, help or tool state, work remaining, queue, chosen action, and goal status. A TSV is a tab-separated text file. It opens in a spreadsheet, and it is also easy to read with a script.

The JSON files in `runs/` hold the complete records behind those two views. They include the starting configuration, rule descriptions, every before and after state, actions, model responses, and the final result. The text and TSV views were made from those saved records without calling Azure again.

For example, the first library run begins with R1 at (0, 4), R2 at (4, 4), the librarian at the desk (2, 0), and R3 reading at (3, 3). At step 1, R1 and R2 each move up one cell. At step 6, both reach the desk and join the queue. R1 is served at step 7 and R2 at step 8. You can follow each of those changes in the text file or find the corresponding rows in the TSV.

## The two worlds

A cell is an (x, y) position. x increases to the right and y increases downward. The top left cell is (0, 0). Both worlds use a 5 by 5 grid. A person can move one cell per step, up, left, right, or down. The program prevents moves outside the grid or into a blocked cell. People may share a walkable cell.

### Library

The library has a help desk at (2, 0), one blocked shelf cell at (2, 2), one librarian, and three readers. R1 and R2 need help. R3 keeps reading. Readers who need help move toward the desk along a shortest path. If two paths are equally short, the manual policy tries up, left, right, then down. A reader who arrives at the desk joins a queue and cannot be served until the next step. The librarian serves at most one queued reader per step while the desk is open. Readers who arrive together are ordered by ID.

The library goal is to serve the two readers who initially need help within 12 steps. There are two saved versions. In one, the desk stays open. In the other, it closes during steps 6, 7, and 8, then opens again at step 9. This changes only the desk schedule. It does not change how service works.

### Workshop

The workshop has a tool counter at (2, 0), one storekeeper, and two workers. Each worker starts at a different workstation. Both need a drill for two work steps. They first travel to the counter and join the loan queue. Once a worker gets a drill, they carry it back to their workstation, work for two steps, then return it. The storekeeper handles at most one loan or return in a step. Returns take priority over loans, and a returned drill can be loaned again on the next step.

The workshop goal is to finish both jobs and return every drill within 40 steps. One saved version starts with one drill. Another starts with two. At every committed step, the program checks that the number of drills at the counter plus the number held by workers equals the configured total. No worker can hold a drill that does not exist.

## What one step means

The program prints and saves the starting world as step 0. It checks whether the goal is already reached. For each later step, it follows this order:

1. Apply any scheduled change, such as closing the desk or adding a drill.
2. Find the actions that are allowed from the current world.
3. Choose one action per person. The manual policy uses the written rules. The Azure policy asks the model to choose from a list of legal actions.
4. Apply actions and their effects. Service and handover decisions use the queue as it stood at the start of the step. New arrivals enter for the next step.
5. Check the grid and drill rules, update the goal, print the new world, and save the full state.

The `Actions and events` section in the text trace includes voluntary actions and automatic effects. For example, `move up` is a reader’s action, while `join queue` is the effect of arriving at the desk. The saved JSON marks those separately. `State changes` lists the values that actually changed between the before and after states.

## Results from the saved runs

| Run | Goal result | What happened |
| --- | --- | --- |
| Library, manual, desk open | Reached at step 8 | R1 was served at 7, R2 at 8. They waited 1 and 2 steps. |
| Library, manual, desk closed at 6 to 8 | Reached at step 10 | R1 was served at 9, R2 at 10. They waited 3 and 4 steps. |
| Workshop, manual, one drill | Reached at step 38 | W1 finished and returned the drill at 22. W2 finished at 38. |
| Workshop, manual, two drills | Reached at step 23 | W1 finished at 22 and W2 at 23. Both drills were returned. |
| Workshop, PSL queue policy, one drill | Reached at step 38 | The priority choice agreed with the manual queue order in this case. |
| Library, Azure agent policy | Reached at step 8 | The model made 22 choices. All were valid. Both readers were served on the same steps as in the manual run. |
| Workshop, Azure agent policy | Not reached by step 40 | The model made 80 choices. Four were invalid and became waits. W1 finished its work but had not returned the drill. W2 had not received a drill. |

The two manual library runs show the effect of the desk closure in this encoded world. The two manual workshop runs show the effect of starting with one more drill. The Azure workshop result shows a limitation of that single model run: its action choices did not finish the task in time. It does not tell us how often the model would succeed across repeated runs. Both Azure runs were replayed from their saved responses. Each replay produced the same actions and final state without another API call.

The workshop’s PSL policy uses two weighted rules. Higher urgency pushes a waiting worker’s priority up with weight 3. A second rule pushes priority down with weight 1. The official PSL inference engine balances them. With the assigned urgencies, W1 receives a score near 0.600 and W2 near 0.375. These numbers are queue decision scores, not probabilities of being served. Both workers reach the counter together in this case, so W1 is first under either queue policy.

A high-reasoning Azure call also proposed one replacement movement rule for the workshop. The program checked its field names and action, then compared it with the manual run. It matched 12 worker movement decisions in that one reference case. The proposal is saved in `runs/workshop-rule-proposal-validated.json`. It is not installed as a live rule, and this check does not show that it works in new worlds.

## Run it yourself

Run these commands from this folder. First, make a Python 3.11 environment and install the packages. The PSL policy also needs Java installed.

```bash
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

Then run a case:

```bash
.venv/bin/python run.py library
.venv/bin/python run.py library_closed --display quiet
.venv/bin/python run.py workshop
.venv/bin/python run.py workshop_two_drills --display delay --delay 0.5
.venv/bin/python run.py workshop --policy psl
```

The default display prints every step and leaves the history in the terminal. `--display interactive` waits for Enter after each step. `--display delay` pauses for the number of seconds given by `--delay`. `--display quiet` saves the JSON result without printing grids. Each command saves a new JSON file in `runs/`. Use `--output` if you want a particular filename.

To rebuild the readable observation files from saved results, run:

```bash
.venv/bin/python display.py runs/library-manual.json runs/library-closed-manual.json runs/workshop-manual.json runs/workshop-two-drills-manual.json runs/workshop-psl.json runs/library-azure-full.json runs/workshop-azure-full.json --text 'runs/World Progression.txt' --tsv 'runs/World States.tsv'
```

This command only reads saved JSON. It does not rerun the worlds or call Azure. You can also pass one JSON file to make a separate text transcript and TSV for just that run.

## Azure settings and model runs

The saved model runs used the existing Azure GPT-6 Luna deployment. Action choices request low reasoning. Rule proposals request high reasoning. A live check confirmed that both settings work. The deployment rejects `temperature=0`, so the client leaves temperature out of every request by default. The response record still notes `temperature: null` to make that omission clear. It never silently retries with different settings.

Azure credentials stay outside this folder. The client reads `AZURE_OPENAI_BASE_URL` and `AZURE_OPENAI_API_KEY` (or `AZURE_AI_FOUNDRY_API_KEY`) from the environment. You can point it to an existing environment file with `--env-file`. The deployment name defaults to `gpt-6-luna`; `PTOM_AZURE_DEPLOYMENT` can override it. No API key or endpoint is saved in a case or run trace.

```bash
.venv/bin/python run.py library --policy azure --env-file /path/to/existing/.env
.venv/bin/python run.py workshop --policy azure --env-file /path/to/existing/.env
.venv/bin/python run.py workshop --propose-rules --env-file /path/to/existing/.env
```

The model receives one person’s task and visible surroundings, plus its allowed actions. It cannot directly edit positions, queues, or inventory. Python checks the chosen action before changing the world. A malformed or illegal answer becomes a wait, and the validation error appears in the JSON and readable trace. An API failure stops the run. The runner saves each committed step, so you can continue from the last saved state:

```bash
.venv/bin/python run.py --resume runs/your-run.json --env-file /path/to/existing/.env
```

To repeat a saved model run without new API calls, use `--replay`:

```bash
.venv/bin/python run.py library --policy azure --replay runs/library-azure-full.json
```

The two commands above serve different purposes. Resume continues an unfinished run from its last committed step. Replay starts again and reuses the model responses already in a saved run.

## Change a case

The `cases/` folder contains small JSON files. `library.json` and `workshop.json` give the full starting states. `library_closed.json` and `workshop_two_drills.json` inherit those states and change only the comparison input. You can copy a case file and change positions, the number of tools, the step limit, or the goal count. The program checks required fields and rejects invalid positions.

A scheduled change has a step, a field, and a value. The library closure file provides an example. The workshop can add a drill during a run with an event like `{"step": 10, "field": "add_tools", "value": 1}`. Scheduled changes alter the world state. They do not rewrite the behavior rules.

## Code and checks

The code is kept in six main Python files. `world.py` loads and checks cases. `rules.py` holds rule descriptions, movement, invariants, and the two small rule checks. `simulation.py` advances the world. `display.py` prints and exports observations. `azure_client.py` handles model calls and replay choices. `run.py` is the command-line entry point. The three test files check timing, queues, inventory, PSL scores, invalid model actions, and checkpoint resume.

```bash
.venv/bin/python -m unittest discover -s tests -v
```

Eleven tests passed on this setup. The final saved traces were also checked for continuous step numbers, at most one chosen action per person per step, drill conservation at every workshop step, and exact replay of both Azure runs. These checks confirm that the implementation follows its own rules. They do not measure whether the rules match real social behavior.

## Documents and next steps

The copied [Small Grid Society Simulator Plan](<P-ToM Small Grid Society Simulator Plan.docx>) is the implementation plan for this folder. The copied [Broader Modeling Framework](<P-ToM Broader Modeling Framework.docx>) explains the larger P-ToM goal, including beliefs, communication, and theory of mind. The advisor meeting transcript and whiteboard remain at their original OneDrive locations and were not copied here.

The next research step would be to choose more case variations before looking at model results, then run repeated manual and model comparisons. Beliefs about other people, a social network that persists over time, and real-world validation belong to later versions. This first version focuses on making the starting worlds visible, repeatable, and easy to check.
