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

Suppose a librarian is working at a help desk while two readers need assistance. A third reader is already reading. The case file supplies their starting values. The simulator then records how those values change at each step.

This is the library at **step 0**, before anyone acts. Coordinates use `(x, y)`, with `x` increasing to the right and `y` increasing downward.

```text
        x0     x1     x2     x3     x4
y0       .      .    L1/D      .      .
y1       .      .      .       .      .
y2       .      .      #       .      .
y3       .      .      .     R3/R     .
y4      R1      .      .       .     R2
```

`D` is the help desk at `(2, 0)`, `R` is the reading place at `(3, 3)`, and `#` is a blocked shelf at `(2, 2)`. A label such as `L1/D` means that L1 occupies the desk cell. People may share a walkable cell, so the queue records service order rather than separate waiting positions.

#### Individual state

Each person has the fields below. The table shows the value type and what it means in this library. Coordinates are pairs of integers. In JSON they are written as two-element arrays.

| Field | Type | Meaning and initial example |
| --- | --- | --- |
| `id` | string | Stable person ID, such as `R1`. |
| `role` | string | `librarian` or `reader`. |
| `position` | pair of integers | Current `[x, y]` cell, such as `[0, 4]`. |
| `task` | string | `serve_readers`, `get_help`, or `read`. |
| `status` | string | Starts as `available`, `moving`, or `reading`; a reader can later be `waiting` or `served`. |
| `needs_help` | Boolean | `true` for R1 and R2; `false` for R3. It becomes `false` when a reader is served. |
| `arrival_step` | integer or `null` | Starts as `null`; set to the step when the reader joins the queue. |
| `served_step` | integer or `null` | Starts as `null`; set to the step when service occurs. |
| `wait_steps` | integer | Starts at `0`; after service, `served_step - arrival_step`. |

The starting values for the four people are:

| Person | Role | Position | Task | Status | `needs_help` |
| --- | --- | --- | --- | --- | --- |
| L1 | librarian | `[2, 0]` | `serve_readers` | `available` | `false` |
| R1 | reader | `[0, 4]` | `get_help` | `moving` | `true` |
| R2 | reader | `[4, 4]` | `get_help` | `moving` | `true` |
| R3 | reader | `[3, 3]` | `read` | `reading` | `false` |

`arrival_step` and `served_step` are `null` for everyone at step 0, and `wait_steps` is `0`. The saved state also includes shared person fields used by the workshop, such as `has_tool` and `work_left`. They stay at their defaults in the library.

#### Society and goal state

The case configuration describes the grid and fixed settings. The run state holds values that change as the simulation advances.

| Key | Type | Library value at step 0 | Role |
| --- | --- | --- | --- |
| `case` | string | `library` | Selects the library behavior. |
| `people` | list of person objects in the case; ID-keyed map in a saved state | L1, R1, R2, R3 | The individuals described above. |
| `policy` | string | `manual` | Selects manual or Azure choices for this case. |
| `rules` | list of rule ID strings | `LIB_MOVE`, `LIB_QUEUE`, `LIB_SERVE`, `LIB_READ` | Descriptive names; this list does not currently control execution. |
| `width`, `height` | integers | `5`, `5` | Grid size from the case file. |
| `blocked` | list of coordinate pairs | `[[2, 2]]` | Cells no one can enter. |
| `places` | map from names to coordinate pairs | `desk: [2, 0]`, `reading: [3, 3]` | Named locations. |
| `desk_open` | Boolean | `true` | Whether the librarian can serve someone this step. |
| `queue` | list of person IDs | `[]` | Readers waiting for service, in order. |
| `step` | integer | `0` | Current committed step. |
| `served` | integer | `0` | Derived count of people with a non-`null` `served_step`. |
| `scheduled_changes` | list of event objects | `[]` | Changes applied at specified steps; used for the desk closure. |

The library goal is `{"type": "readers_served", "count": 2}`, with `step_limit: 12`. The goal check is true when at least two people have a non-`null` `served_step`. In this case those people are R1 and R2, the two readers who start needing help. Each trace record saves this result as a Boolean `goal` value. The run stops when the goal is reached or after step 12.

#### Manual library rules

These are the rules used by the built-in manual policy. Each rule has a condition and an effect, so it can be checked against the trace.

1. **`LIB_MOVE`:** If a reader still needs help, is not queued, and has not reached the desk, move one cell along a shortest walkable path to `(2, 0)`. For equally short paths, try up, left, right, then down. A move cannot leave the grid or enter the blocked shelf.
2. **`LIB_QUEUE`:** If a reader who needs help reaches the desk, append their ID to `queue`, set `status="waiting"`, and set `arrival_step` to the current step. The new arrival is eligible for service from the next step onward. Readers arriving together are ordered by ID.
3. **`LIB_SERVE`:** If `desk_open=true` and the queue was nonempty at the start of the step, serve its first reader. Remove that ID from `queue`, set `needs_help=false` and `status="served"`, and record `served_step` and `wait_steps`. At most one reader is served per step.
4. **`LIB_READ`:** If a reader does not need help and is already reading, keep reading. R3 stays at the reading place in these runs.

The available choices and automatic effects are different things:

| Item | Who or what uses it | Effect |
| --- | --- | --- |
| `move(direction)` | Reader | Moves one legal cell. The manual policy picks a shortest-path move; the Azure policy may choose any legal neighboring cell. |
| `wait` | Reader or librarian | Uses the step without moving or serving. |
| `read` | Reading reader | Continues reading, with no state change. |
| `serve(person)` | Librarian | Serves the first previously queued reader when the desk is open. |
| `join queue` | Automatic arrival effect | Adds a reader to the queue after reaching the desk; it is not a separate model choice. |
| `desk_open` change | Scheduled world event | Changes the desk state before actions for that step. |

The baseline leaves the desk open. R1 and R2 reach it at step 6, R1 is served at step 7, and R2 at step 8. Their waits are one and two steps. The paired run changes only the desk schedule: `desk_open=false` at step 6 and `desk_open=true` at step 9. The desk is therefore closed during steps 6, 7, and 8. The readers still arrive and queue at step 6. They are served at steps 9 and 10, with waits of three and four steps. The goal is met in both runs, but two steps later with the closure. These are results of the encoded rules, not claims about real library visitors.

### Workshop

The workshop has a tool counter at (2, 0), one storekeeper, and two workers. Each worker starts at a different workstation. Both need a drill for two work steps. They first travel to the counter and join the loan queue. Once a worker gets a drill, they carry it back to their workstation, work for two steps, then return it. The storekeeper handles at most one loan or return in a step. Returns take priority over loans, and a returned drill can be loaned again on the next step.

The workshop goal is to finish both jobs and return every drill within 40 steps. One saved version starts with one drill. Another starts with two. At every committed step, the program checks that the number of drills at the counter plus the number held by workers equals the configured total. No worker can hold a drill that does not exist.

The workshop uses the same `id`, `role`, `position`, `task`, `status`, and step fields. Its additional state is:

| Field | Type | Starting value or meaning |
| --- | --- | --- |
| `has_tool` | Boolean per person | `false` for W1 and W2; becomes `true` when a drill is loaned. |
| `work_left` | integer per worker | `2` for each worker; decreases by one for each work step. |
| `urgency` | number from 0 to 1 per worker | `0.8` for W1, `0.5` for W2; used by the PSL priority policy. |
| `workstation` | coordinate pair per worker | `[0, 4]` for W1, `[4, 4]` for W2. |
| `completed_step` | integer or `null` per person | Starts `null`; set when a worker returns the drill after finishing. |
| `tool_count`, `tools_at_counter` | integers for the world | Both start at `1` in the one-drill case. |
| `queue`, `return_queue` | lists of person IDs | Both start empty; they hold workers waiting to borrow or return a drill. |
| `completed` | integer for the world | Derived count of people with a non-`null` `completed_step`. |

The goal is `{"type": "jobs_completed", "count": 2, "all_tools_returned": true}`, with `step_limit: 40`. It requires two completed jobs and all configured drills back at the counter. In the two-drill case, `tool_count` and `tools_at_counter` both start at `2`.

## What one step means

The program prints and saves the starting world as step 0. It checks whether the goal is already reached. For each later step, it follows this order:

1. Apply any scheduled change, such as closing the desk or adding a drill.
2. Find the actions that are allowed from the current world.
3. Choose one action per person. The manual policy uses behavior implemented in code. The Azure policy asks the model to choose from a list of legal actions.
4. Apply actions and their effects. Service and handover decisions use the queue as it stood at the start of the step. New arrivals enter for the next step.
5. Check the grid and drill rules, update the goal, print the new world, and save the full state.

The `Actions and events` section in the text trace includes voluntary actions and automatic effects. For example, `move up` is a reader’s action, while `join queue` is the effect of arriving at the desk. The saved JSON marks those separately. `State changes` lists the values that actually changed between the before and after states.

## Where PSL fits

Probabilistic soft logic (PSL) combines weighted rules to infer a score when evidence can pull a decision in different directions. A rule weight expresses influence on that score. It is not the probability that a person will act.

The workshop’s PSL policy uses two weighted rules. Higher urgency pushes a waiting worker’s priority up with weight 3. A second rule pushes priority down with weight 1. The official PSL inference engine balances them. With the assigned urgencies, W1 receives a score near 0.600 and W2 near 0.375. These numbers are queue decision scores, not probabilities of being served. Both workers reach the counter together in this case, so W1 is first under either queue policy.

The two rules passed to PSL are:

```text
3: Waiting(W) & Urgency(W) -> Priority(W) ^2
1: !Priority(W) ^2
```

`Waiting` is observed as `1.0` for each queued worker. `Urgency` comes from each worker’s state (`0.8` for W1 and `0.5` for W2). PSL infers `Priority`, and the worker with the higher score goes first.

PSL is used only for workshop queue priority in this version. The library follows the manual movement, queue, and service rules described above. If we later use PSL there, we need to specify what it infers and make its result affect an actual action. The rule names in the case file do not yet control the simulation, so an LLM-drafted rule would need to be inspected, accepted, and made executable before we could test its effect.

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

The [Research Notes and Library Example](<P-ToM Research Notes and Library Example.docx>) give more context and walk through the library society, its starting values, rules, baseline, and desk closure. The immediate next step is to make accepted rules executable as simulation inputs and test them in this focused case. Information sharing, beliefs about other people, and real-world validation belong to later versions.
