# Election Turnout Grid World Design

## Research question
Can a small, explicit model show how an accurate voting reminder spreads through contacts, changes individual intentions, and changes a group's turnout under fixed access constraints? This is a hypothetical mechanism test. It does not predict a real election, party preference, or vote choice.

Dr. Karmaker agreed that an election could be a useful case, then asked for any specific case with data. The November 5 guest identified verified registration and turnout as possible behavioral measures. He noted that vote choice is not available in voter records. The Cooperative Election Study (CES) 2024 common-content release includes a vote-validated file, and ANES has a 2024 vote-validation release. Pew publishes survey microdata that may help characterize attitudes or demographics, subject to its access terms. These sources do not supply the social ties in this toy grid. The first run therefore tests internal logic. Later work must check which variables can actually be estimated from each dataset.

Sources: [CES 2024 common content](https://doi.org/10.7910/DVN/X11EP6), [ANES 2024 Time Series](https://electionstudies.org/data-center/2024-time-series-study/), [Pew ATP datasets](https://www.pewresearch.org/american-trends-panel-datasets/).

## World and state
The example has 16 adults on a 10 by 10 grid, one polling site, four neighborhoods, and a fixed contact network. Each person has an ID, age band, education band, neighborhood, grid position, registration status, past turnout, civic interest, access to the polling site, and trust in peer information. These are synthetic, hand-set inputs. Age and education are recorded for later subgroup checks; they do not directly determine behavior in the first model. This avoids encoding unsupported demographic stereotypes as rules.

At each step, the observed inputs include prior awareness, prior sharing, prior voting, position relative to the polling site, contacts, and the fixed attributes above. A person keeps awareness once they receive a notice and shares at most once. PSL infers awareness, intent, sharing, travel, and voting-action support for each person. It also infers a neighborhood readiness score from aggregate intent, access, and actual turnout. These inferred scores are soft truth values, not event probabilities. The trace records each observed input and inferred value before any action is applied.

The simulator then applies a declared action policy: a score above a threshold can trigger sharing, one legal grid move toward the polling site, or a vote at the site. These thresholds and the grid's legal-move and one-person-one-vote checks are explicit mechanics. They are not hidden behavioral rules. To make a rule truly mandatory, use a hard constraint. Binary evidence alone does not turn a weighted PSL rule into a hard rule.

## First hand-authored PSL rule set
The executable rules are in `psl_rules/election_individual.psl` and `psl_rules/election_group.psl`. The weights are illustrative and are not learned from data. `P` and `Q` are people; `N` is a neighborhood. A grounded rule is produced by replacing these symbols with concrete IDs. Every rule's observed and target predicates are listed below.

| Role | Observed inputs | PSL target | Intended effect |
| --- | --- | --- | --- |
| Memory | `AwarePrev(P)` | `Aware(P)` | Keep earlier awareness unless other evidence conflicts. |
| Interaction | `SharePrev(P)`, `Contact(P,Q)`, `Trust(Q,P)` | `Aware(Q)` | A trusted contact can carry the reminder to another person. |
| Intent | `Aware(P)`, `Interest(P)`, `PastVoter(P)`, `Access(P)` | `Intent(P)` | Awareness, interest, and prior behavior support intention; limited access can oppose it. |
| Sharing | `Aware(P)`, `Reach(P)` | `ShareNow(P)` | An aware person with contacts may pass the reminder on. |
| Travel | `Intent(P)`, `Access(P)`, `Registered(P)`, `VotedPrev(P)` | `Travel(P)` | A registered person who intends to vote can head toward the site. |
| Vote | `AtPoll(P)`, `Intent(P)`, `Registered(P)`, `VotedPrev(P)` | `VoteNow(P)` | At the site, a registered and willing person may vote once. |
| Society | `MeanIntent(N)`, `MeanAccess(N)`, `CurrentTurnout(N)` | `Ready(N)` | Summarize collective readiness using another PSL model. |

Negative priors keep unsupported targets low. They make the inference determinate in this small model. The individual rule file also has hard PSL constraints: an unregistered person or a person who already voted cannot travel or vote, a person away from the poll cannot vote, and sharing cannot exceed awareness. An access rule pushes against intent when access is low. Competing weighted rules can disagree; MAP chooses the joint assignment with lowest total penalty. A PSL implication does not assert equality between its body and head.

## Step order and experiment
1. Apply a scheduled official reminder or access support to selected people. These interventions are recorded as input evidence.
2. Build the PSL observation and target tables. Infer the five individual target predicates together.
3. Apply the declared thresholds. People can share a reminder while traveling. A traveler moves at most one legal cell; only someone at the poll can cast a vote.
4. Aggregate the resulting state by neighborhood. Run the group PSL rules and record readiness plus measured turnout.
5. Save observed inputs, grounded rule text, inferred scores, actions, and outcome for that step.

The reminder case gives four additional people an official notice at step 3. A third case gives those same people the notice and improved access. With the provisional weights and fixed thresholds, final turnout is 4/16 in the baseline, 4/16 with reminders, and 7/16 with reminders plus access. Mean awareness rises from 0.343 to 0.690 with reminders. All cases run for 20 steps and miss the illustrative 60% turnout goal. The comparison asks whether each specified change affects awareness, actions, and turnout under these hypothetical rules. It cannot establish the causal effect of reminders in the real world. A later data-backed study should estimate or test parameters, compare subgroup turnout with held-out CES or ANES observations, and seek separate evidence for contact and message exposure.

## Known limits and next checks
The grid coordinates are a visual abstraction, not real addresses. Contact ties, trust, interests, access scores, thresholds, and rule weights are synthetic. CES or ANES vote validation can check turnout outcomes and some individual associations, but not this model's invented contact network. Targeted tests now check contact propagation, hard voting constraints, legal moves, and one vote per person. A four-setting weight sweep shows that stronger diffusion increases awareness without increasing turnout, while stronger action weights increase baseline turnout. These weights are not validated. Next, vary weights and thresholds more widely, test different networks, and compare measurable outcomes with data before asking an LLM to propose alternative rules for review. Theory of mind remains a later extension.
