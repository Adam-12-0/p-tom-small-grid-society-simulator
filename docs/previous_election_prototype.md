# PSL election turnout grid world

This is a small, runnable example for the P-ToM project. It asks how an accurate voting reminder could spread through a community, and whether a reminder alone changes turnout when access to the polling place is uneven. Dr. Karmaker agreed that an election could be a useful next case after the library prototype, while asking us to choose a case with data. The people, contact network, scores, weights, and outcomes here are synthetic. This is a mechanism test, not an election forecast.

The example has 16 adults on a 10 by 10 grid, four neighborhoods, one polling place, and a fixed network of contacts. It is large enough to trace a reminder across several people and to compare individual and neighborhood outcomes. It is still intentionally small enough to inspect by hand.

## Starting grid

`P01` to `P16` are people, `POLL` is the polling site, `#` is a blocked cell, and `·` is an open cell. People can move one open cell per step toward the polling site. The contact network is separate from physical proximity, so two people can communicate without standing next to each other.

```text
P01  ·    P02  ·    ·    ·    ·    P05  ·    P06
·    ·    ·    ·    ·    ·    ·    ·    ·    ·
P03  ·    P04  ·    ·    ·    ·    P07  ·    P08
·    ·    ·    ·    ·    ·    ·    ·    ·    ·
·    ·    ·    ·    #    ·    #    ·    ·    ·
·    ·    ·    ·    ·    POLL ·    ·    ·    ·
·    ·    ·    ·    #    ·    #    ·    ·    ·
P09  ·    P10  ·    ·    ·    ·    P13  ·    P14
·    ·    ·    ·    ·    ·    ·    ·    ·    ·
P11  ·    P12  ·    ·    ·    ·    P15  ·    P16
```

The full case, including all contacts and initial values, is in [`cases/election_turnout.json`](cases/election_turnout.json). Three people start with the reminder. There are 16 undirected contact links, including four links across neighborhoods. A person's `trust_peer` value applies to messages received from their contacts.

## State and predicates

| Level | Supplied or stored state | PSL inference |
| --- | --- | --- |
| Person | ID, position, neighborhood, registration, prior turnout, interest, access, trust, age band, education band | `Aware`, `Intent`, `ShareNow`, `Travel`, `VoteNow` |
| Contact | Pair of people and receiver's trust in a peer message | A contact's earlier sharing supports the receiver's awareness |
| Neighborhood | Mean inferred intent, mean access, and observed turnout | `Ready`, a descriptive readiness score |
| World | Grid, blocked cells, polling site, step count, interventions, action thresholds | No world-wide target in this first model |

`AwarePrev`, `SharePrev`, `VotedPrev`, and `AtPoll` are observations rebuilt each step from the stored state. `Reach` summarizes the number of contacts. Age and education are recorded for future subgroup checks. They do not drive behavior in these rules. The inferred PSL values are degrees of support from 0 to 1, not calibrated probabilities of voting.

## Hand-written PSL rules

`P` and `Q` refer to people, and `N` to a neighborhood. Each weighted line is a soft rule. `^2` means its violation is penalized quadratically. A larger weight makes a violation cost more, but it does not make a rule mandatory. The lines ending in `.` are hard PSL constraints. These are the executable rules in [`psl_rules/election_individual.psl`](psl_rules/election_individual.psl) and [`psl_rules/election_group.psl`](psl_rules/election_group.psl).

**Reminder exposure and sharing**

```psl
5: AwarePrev(P) -> Aware(P) ^2
4: SharePrev(P) & Contact(P,Q) & Trust(Q,P) -> Aware(Q) ^2
1: !Aware(P) ^2
3: Aware(P) & Reach(P) -> ShareNow(P) ^2
1: !ShareNow(P) ^2
!Aware(P) -> !ShareNow(P) .
```

The contact rule is the first interpersonal inference. If a person shared in the previous step, contact and trust can support another person's awareness. The negative rules keep unsupported awareness and sharing low.

**Intent and action**

```psl
4: Aware(P) & Interest(P) -> Intent(P) ^2
2: PastVoter(P) -> Intent(P) ^2
3: !Access(P) -> !Intent(P) ^2
1: !Intent(P) ^2
4: Intent(P) & Access(P) & Registered(P) & !VotedPrev(P) -> Travel(P) ^2
1: !Travel(P) ^2
5: AtPoll(P) & Intent(P) & Registered(P) & !VotedPrev(P) -> VoteNow(P) ^2
1: !VoteNow(P) ^2
!Registered(P) -> !Travel(P) .
VotedPrev(P) -> !Travel(P) .
!Registered(P) -> !VoteNow(P) .
VotedPrev(P) -> !VoteNow(P) .
!AtPoll(P) -> !VoteNow(P) .
```

Awareness and interest support intent, past voting gives a separate reason for intent, and low access works against it. Intent and access support travel. Voting needs the person to be at the poll. The hard constraints block travel or voting when registration or prior voting makes the action impossible. A PSL implication only contributes a penalty when it is violated. It does not set its target equal to the rule body.

**Neighborhood summary**

```psl
4: MeanIntent(N) & MeanAccess(N) -> Ready(N) ^2
2: CurrentTurnout(N) -> Ready(N) ^2
1: !Ready(N) ^2
```

`Ready` summarizes inferred intent, access, and observed turnout after each step. It does not yet feed back into individual behavior. Adding a justified social norm or peer expectation mechanism is future work.

## From PSL scores to a completed run

At each step the code applies scheduled notices or access support, jointly infers the five person-level PSL targets, and then applies the action thresholds. A person may share a notice once, move one legal cell, and vote once at the polling site. Awareness persists after a person receives a notice. These memory, movement, and one-vote conditions are declared world mechanics. The PSL hard constraints also encode the action restrictions inside inference. The neighborhood model then infers `Ready` from the updated state. Every step records its observations, inferred scores, actions, and resulting state.

The action thresholds are `share = 0.25`, `travel = 0.30`, and `vote = 0.35`. They turn soft scores into discrete events. Like the weights, these thresholds are hypothetical, not fitted to data. All three cases run for 20 steps against the same illustrative 60% turnout goal.

| Case | Change at step 3 | Final awareness mean | Final turnout | Reached 60% goal? |
| --- | --- | ---: | ---: | --- |
| Baseline | None | 0.343 | 4/16 (25.0%) | No |
| Reminder | Four more people receive an official notice | 0.690 | 4/16 (25.0%) | No |
| Reminder plus access | The same notice, plus improved access for those four people | 0.690 | 7/16 (43.8%) | No |

In this model, extra reminders spread information but do not move the people whose access is limited. Access support lets three more people reach the poll and vote. This is a result of the chosen rules and starting values. It is not an estimate of a real intervention effect. Full traces are in [`runs/election_turnout-psl.json`](runs/election_turnout-psl.json), [`runs/election_turnout_reminder-psl.json`](runs/election_turnout_reminder-psl.json), and [`runs/election_turnout_reminder_access-psl.json`](runs/election_turnout_reminder_access-psl.json).

## Why these provisional weights?

The first run with higher action thresholds produced no movement. I lowered the thresholds to values that allow a small number of supported actions, then kept them fixed during the weight sweep. The weights in the rule files are moderate, round numbers for an inspectable first model. The sweep changes related weights together while leaving the people and thresholds fixed.

| Weight setting | Baseline turnout | Reminder turnout | Reminder plus access turnout | Main observation |
| --- | ---: | ---: | ---: | --- |
| Reference, rules above | 4/16 | 4/16 | 7/16 | Reminder changes awareness; access also changes turnout. |
| Stronger diffusion | 4/16 | 4/16 | 7/16 | More sharing and awareness, with no extra votes. |
| Stronger action | 7/16 | 7/16 | 9/16 | More people vote even without the intervention. |
| Both changes | 7/16 | 7/16 | 9/16 | Action weights still control this turnout result. |

The stronger diffusion setting doubles the contact weight from 4 to 8 and the sharing weight from 3 to 6. The stronger action setting raises the awareness-to-intent weight from 4 to 6, travel from 4 to 7, and voting from 5 to 7. I kept the reference weights because they leave room to see the effect of the access change and do not imply that many people vote without it. This is a modeling choice for a transparent prototype, not a claim that these weights are correct. The complete sweep is in [`runs/election_weight_sweep.json`](runs/election_weight_sweep.json). The next step is to vary thresholds and weights over a wider range and compare with data before making substantive claims.

## Run it

The project uses Python 3 and `pslpython` with Java. With the project environment available:

```bash
.venv/bin/python -W ignore::FutureWarning election_psl.py election_turnout --show-grid
.venv/bin/python -W ignore::FutureWarning election_psl.py election_turnout
.venv/bin/python -W ignore::FutureWarning election_psl.py election_turnout_reminder
.venv/bin/python -W ignore::FutureWarning election_psl.py election_turnout_reminder_access
.venv/bin/python -W ignore::FutureWarning weight_sweep.py
.venv/bin/python -W ignore::FutureWarning -m unittest discover -s tests -v
```

The older library and workshop setup is kept only in [`docs/legacy_library_workshop.md`](docs/legacy_library_workshop.md) and its existing source files. It is no longer the primary example.

## What data can eventually check

The [2024 Cooperative Election Study common content](https://doi.org/10.7910/DVN/X11EP6) and [2024 ANES Time Series](https://electionstudies.org/data-center/2024-time-series-study/) provide vote-validation material. [Pew American Trends Panel datasets](https://www.pewresearch.org/american-trends-panel-datasets/) may help study attitudes and demographics, subject to access terms. We have not loaded any of these data into this example. Voter records can check registration or turnout, but they do not reveal a person's vote choice. None of these sources establishes this invented contact network or the causal effect of a reminder. We would need separate evidence for ties, exposure, access, and intervention effects. The next research step is to choose measurable variables, then fit or stress-test weights against a real dataset. Theory of mind can be added after the basic behavior and interaction rules have a defensible empirical target.
