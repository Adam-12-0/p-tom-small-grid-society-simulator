# Civilian assistance grid world with PSL

This is the current toy case for the P-ToM Grid World. It represents a **fictional district in Afghanistan** after an announcement about a civilian assistance point. The question is whether the announcement reaches households and whether people who need the service can get to the site. The people, network, inputs, weights, and outcomes are invented. The model does not predict the behavior of Afghan civilians or assess a real US Government operation.

Sono's follow-up pointed us toward transparent agent-based models for this kind of question. We use PSL to make the behavior and contact rules inspectable. The grid then turns inferred action scores into a step-by-step trace. This is an internal mechanism test until suitable evidence and real outcome data are identified.

## Why this is a toy model

Here, "toy" means deliberately simplified. It is a small model in which we can inspect every input, rule, inferred value, and action. It is not a representative sample of Afghanistan. It does not estimate how a real population would respond to a US Government action. The point is to find out whether the proposed mechanism is coherent and which observations we would need for a later study.

The intervention in this case is a hypothetical announcement of a civilian assistance point. We ask how the message spreads, who considers visiting, and who actually receives assistance. The simulator holds 16 people, one site, and a contact network fixed while changing the announcement and access conditions.

## Research question and testable hypotheses

**Question:** How do information sharing and physical access affect awareness and service uptake in this explicitly defined community?

These are candidate hypotheses about a mechanism. The current runs test whether the *model* behaves as expected. Testing claims about people would require suitable observed data.

| Hypothesis | Controlled comparison | Measure | What would count as support in this model? |
| --- | --- | --- | --- |
| H1. Additional direct announcements increase awareness. | Outreach versus baseline | Mean inferred awareness at step 20 | Awareness is higher with outreach. |
| H2. Improving access increases service uptake. | Access support versus baseline | Share served by step 20 | More people reach the site and receive assistance. |
| H3. Announcements and access may interact. | All four conditions below | Difference in uptake for combined versus single changes | The combined effect exceeds what the single changes explain. A zero interaction is also informative. |
| H4. Lower perceived safety reduces intent when other inputs are held fixed. | Change only Safety for the same person and step | Inferred Intent | Intent falls when Safety falls. |

H1, H2, and H3 use a two-by-two design: baseline, outreach only, access only, and both. H4 is a controlled inference check. Trust in a contact is another testable mechanism. We test it by removing one contact link and checking whether the receiver's inferred awareness falls. None of these tests establish an empirical effect.

## Starting grid

`P01` to `P16` are people, `AID` is the civilian assistance point, `#` is a blocked cell, and `·` is an open cell. Four neighborhoods occupy the corners of this 10 by 10 grid. Contact links are defined separately from physical distance.

```text
P01  ·    P02  ·    ·    ·    ·    P05  ·    P06
·    ·    ·    ·    ·    ·    ·    ·    ·    ·
P03  ·    P04  ·    ·    ·    ·    P07  ·    P08
·    ·    ·    ·    ·    ·    ·    ·    ·    ·
·    ·    ·    ·    #    ·    #    ·    ·    ·
·    ·    ·    ·    ·    AID  ·    ·    ·    ·
·    ·    ·    ·    #    ·    #    ·    ·    ·
P09  ·    P10  ·    ·    ·    ·    P13  ·    P14
·    ·    ·    ·    ·    ·    ·    ·    ·    ·
P11  ·    P12  ·    ·    ·    ·    P15  ·    P16
```

The full synthetic starting values and contact network are in [`cases/aid_baseline.json`](cases/aid_baseline.json). Three people start aware of the announcement. Other people may learn about it from trusted contacts. No party, ethnic, religious, or other population label is used to set behavior.

## State

| Level | Fixed input or stored state | Value inferred by PSL |
| --- | --- | --- |
| Person | Position, neighborhood, need for assistance, access, perceived safety, trust in peer information | `Aware`, `Intent`, `ShareNow`, `Travel`, `ReceiveNow` |
| Contact | Pair of people and the receiver's trust in a peer message | Contact sharing can support another person's awareness |
| Neighborhood | Mean need, mean access, mean intent, observed service uptake | `ServiceGap`, a descriptive unmet-service score |
| Grid | Open and blocked cells, assistance point, step number, interventions | No grid target in this version |

The values in `[0,1]` are illustrative soft truth values, not calibrated chances of a real action. `AwarePrev`, `SharePrev`, `ServedPrev`, and `AtAid` are observed at each step from the stored state. `Reach` is calculated from the contact network. `Safety` is the person's supplied perception of whether visiting the site is safe, not an assessed real-world security condition.

## PSL rules

The following are the exact executable rules in [the person model](psl_rules/aid_person.psl) and [the neighborhood model](psl_rules/aid_group.psl). P and Q are people. N is a neighborhood. A numbered rule is soft, its number is a hand-set weight, and ^2 means a squared violation. A rule ending with a period is hard. The compiled PSL lesson for grounding, violations, inference, and probability is in the adjacent local documents-and-slides folder.

Each row gives the formal rule and its plain-English meaning. The English is a proposed mechanism, not a claim about Afghan behavior.

### Information and contact

| PSL rule | Meaning |
| --- | --- |
| <code>5: AwarePrev(P) -> Aware(P) ^2</code> | Awareness carried from the previous step supports awareness now. |
| <code>4: SharePrev(P) &amp; Contact(P,Q) &amp; Trust(Q,P) -> Aware(Q) ^2</code> | A prior share from P can inform Q when they are linked and Q trusts P. |
| <code>1: !Aware(P) ^2</code> | A weak prior resists unsupported awareness. |
| <code>3: Aware(P) &amp; Reach(P) -> ShareNow(P) ^2</code> | An aware person with reachable contacts has support for sharing. |
| <code>1: !ShareNow(P) ^2</code> | A weak prior resists sharing when the positive rule gives little support. |
| <code>!Aware(P) -> !ShareNow(P) .</code> | A person cannot have a sharing score above their awareness score. |

### Intent and movement

| PSL rule | Meaning |
| --- | --- |
| <code>4: Aware(P) &amp; Need(P) -> Intent(P) ^2</code> | Awareness combined with need supports intent to visit. |
| <code>2: Need(P) -> Intent(P) ^2</code> | Need can also support seeking help through background knowledge, even without this announcement. This assumption is why outreach need not change uptake. |
| <code>3: !Safety(P) -> !Intent(P) ^2</code> | Low perceived safety pushes intent downward. |
| <code>1: !Intent(P) ^2</code> | A weak prior resists unsupported intent. |
| <code>4: Intent(P) &amp; Access(P) &amp; !ServedPrev(P) -> Travel(P) ^2</code> | Intent and access support travel for a person who has not been served. |
| <code>1: !Travel(P) ^2</code> | A weak prior resists travel without support. |
| <code>ServedPrev(P) -> !Travel(P) .</code> | A person already served cannot travel for service again. |

### Receiving assistance

| PSL rule | Meaning |
| --- | --- |
| <code>5: AtAid(P) &amp; Need(P) &amp; !ServedPrev(P) -> ReceiveNow(P) ^2</code> | Need supports receipt when a person is at the site and has not received help. |
| <code>1: !ReceiveNow(P) ^2</code> | A weak prior resists receipt without support. |
| <code>ServedPrev(P) -> !ReceiveNow(P) .</code> | Receipt cannot occur twice. |
| <code>!AtAid(P) -> !ReceiveNow(P) .</code> | Receipt cannot occur away from the site. |

### Neighborhood summary

| PSL rule | Meaning |
| --- | --- |
| <code>4: MeanNeed(N) &amp; !CurrentUptake(N) -> ServiceGap(N) ^2</code> | High need together with low observed uptake supports a larger service gap. |
| <code>2: MeanNeed(N) &amp; !MeanAccess(N) -> ServiceGap(N) ^2</code> | High need together with low access gives another reason for a service gap. |
| <code>1: !ServiceGap(N) ^2</code> | A weak prior resists an unsupported gap. |

The person-level targets Aware, Intent, ShareNow, Travel, and ReceiveNow are inferred jointly each step. ServiceGap is inferred afterward from neighborhood summaries. It is descriptive and does not feed back into decisions yet. The model assumes unlimited service capacity. That assumption would need to change before studying queues or scarce supplies.

## One simulation step

1. Apply any scheduled announcement or access support. Record the changed input.
2. Infer the five person-level PSL targets jointly from fixed observations and weighted rules.
3. Use the declared thresholds to let someone share once, move one legal cell, or receive assistance at the site. Awareness persists after a person learns the announcement.
4. Calculate neighborhood inputs and infer `ServiceGap` with the group rules.
5. Save the observations, inferred values, actions, and state after the step.

The thresholds are `share = 0.25`, `travel = 0.20`, and `receive = 0.33`. A threshold changes a soft score into a discrete action. It is a simulator choice, not a PSL probability. Grid movement, persistent awareness, one-time sharing, and one-time receipt are world mechanics. The hard PSL rules also restrict action scores inside inference.

## Completed synthetic runs

All four cases have the same 16 people, network, rules, and 20-step limit. The only differences are the events at step 3. The illustrative goal is at least 50% service uptake.

| Case | Step 3 change | Mean awareness | People served | Reached goal? |
| --- | --- | ---: | ---: | --- |
| [`aid_baseline`](cases/aid_baseline.json) | None | 0.343 | 6/16 (37.5%) | No |
| [`aid_outreach`](cases/aid_outreach.json) | Four more people hear the announcement | 0.729 | 6/16 (37.5%) | No |
| [`aid_access`](cases/aid_access.json) | Access support for the same four people | 0.344 | 9/16 (56.3%) | Yes, at step 10 |
| [`aid_outreach_access`](cases/aid_outreach_access.json) | Same announcement plus access support | 0.729 | 9/16 (56.3%) | Yes, at step 10 |

In these runs, outreach spreads awareness but does not increase receipt. Access support increases receipt with or without outreach. The combined case adds no further uptake beyond access alone. One reason is the explicit Need-to-Intent rule: a person can seek help without hearing this announcement. P04, P08, and P12 receive assistance in both access cases. These are results of hypothetical rules and inputs, not evidence of a real intervention effect. The uptake interaction is 0.5625 - 0.375 - 0.5625 + 0.375 = 0. That does not support H3 in this setup. Full traces are in [`runs/aid_baseline-psl.json`](runs/aid_baseline-psl.json), [`runs/aid_outreach-psl.json`](runs/aid_outreach-psl.json), [`runs/aid_access-psl.json`](runs/aid_access-psl.json), and [`runs/aid_outreach_access-psl.json`](runs/aid_outreach_access-psl.json).

A [four-setting weight sweep](runs/aid_weight_sweep.json) compares the reference rules with stronger diffusion, stronger action, and a weaker safety effect across all four cases. In this small range, the final service counts did not change. Stronger diffusion did raise awareness. That means the current action thresholds and starting conditions matter at least as much as these weight changes for the measured outcome. We should not treat the present weights as fitted or stable. The next sensitivity check should vary thresholds, network links, and initial values as well.

## Run it

The project uses Python 3, `pslpython`, and Java. With the project environment:

```bash
.venv/bin/python -W ignore::FutureWarning aid_psl.py aid_baseline --show-grid
.venv/bin/python -W ignore::FutureWarning aid_psl.py aid_baseline
.venv/bin/python -W ignore::FutureWarning aid_psl.py aid_outreach
.venv/bin/python -W ignore::FutureWarning aid_psl.py aid_access
.venv/bin/python -W ignore::FutureWarning aid_psl.py aid_outreach_access
.venv/bin/python -W ignore::FutureWarning aid_weight_sweep.py
.venv/bin/python -W ignore::FutureWarning -m unittest discover -s tests -v
```

The earlier election example and its traces are retained as a previous prototype. It is no longer the case described by this README.

## What would make this a research result?

A transparent toy model is a starting point. We still need to identify observations for message exposure, contact, trust, perceived safety, physical access, and service uptake in a specific civilian setting. Two possible sources to screen are [UNHCR’s Afghanistan Rapid Household Assessments 2024](https://microdata.worldbank.org/catalog/6537/data-dictionary/hh_data), which include questions about humanitarian-assistance information and access, and [the Asia Foundation’s 2019 Survey of the Afghan People](https://asiafoundation.org/insight/afghanistan-in-2019-a-survey-of-the-afghan-people/), which covers security, institutions, media, and services. We have not shown that either source measures the message spread or intervention outcome in this toy case. We also need a way to test whether our rules generalize beyond one hand-set grid. Sono recommended [Epstein's agent-based model](https://doi.org/10.1073/pnas.092080199) as an example of transparent individual rules and pointed us to [Chuang et al.](https://aclanthology.org/2024.findings-naacl.211/) for LLM opinion dynamics. Both are useful for designing comparisons, but neither validates the rules here. LLM-generated rules should be treated as proposals that need syntax checks, grounding checks, and comparison with observed behavior. Theory of mind can be added after the basic contact and action mechanisms have an empirical target.
