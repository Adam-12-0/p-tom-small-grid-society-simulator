"""Compare hand-set rule weights. No observed data are used for fitting."""
from __future__ import annotations
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import election_psl as sim

ROOT = Path(__file__).resolve().parent
CASES = ('election_turnout', 'election_turnout_reminder', 'election_turnout_reminder_access')
VARIANTS = {
    'reference': {},
    'stronger_diffusion': {'SharePrev(P) & Contact(P,Q) & Trust(Q,P) -> Aware(Q)': 8,
                           'Aware(P) & Reach(P) -> ShareNow(P)': 6},
    'stronger_action': {'Aware(P) & Interest(P) -> Intent(P)': 6,
                        'Intent(P) & Access(P) & Registered(P) & !VotedPrev(P) -> Travel(P)': 7,
                        'AtPoll(P) & Intent(P) & Registered(P) & !VotedPrev(P) -> VoteNow(P)': 7},
    'combined': {'SharePrev(P) & Contact(P,Q) & Trust(Q,P) -> Aware(Q)': 8,
                 'Aware(P) & Reach(P) -> ShareNow(P)': 6,
                 'Aware(P) & Interest(P) -> Intent(P)': 6,
                 'Intent(P) & Access(P) & Registered(P) & !VotedPrev(P) -> Travel(P)': 7,
                 'AtPoll(P) & Intent(P) & Registered(P) & !VotedPrev(P) -> VoteNow(P)': 7},
}


def revise_rules(lines: list[str], changes: dict[str, int]) -> str:
    output = []
    found = set()
    for line in lines:
        body = line.split(': ', 1)[-1].removesuffix(' ^2')
        if body in changes:
            line = f'{changes[body]}: {body} ^2'
            found.add(body)
        output.append(line)
    if found != changes.keys():
        raise ValueError(f'Rule not found: {changes.keys() - found}')
    return '\n'.join(output) + '\n'


def summarize(result: dict) -> dict:
    trace = result['trace']
    final = trace[-1]
    return {'turnout': result['result']['turnout'], 'aware_mean': result['result']['awareness'],
            'aware_count_ge_half': sum(p['awareness'] >= 0.5 for p in final['after'].values()),
            'shares': sum(a['action'] == 'share' for t in trace for a in t['actions']),
            'moves': sum(a['action'] == 'move' for t in trace for a in t['actions']),
            'votes': sum(a['action'] == 'vote' for t in trace for a in t['actions']),
            'first_goal_step': result['result']['first_goal_step']}


def main() -> None:
    original = sim.INDIVIDUAL_RULES
    lines = original.read_text().splitlines()
    report = {'note': 'Illustrative sensitivity check, not fitted or validated weights.', 'variants': {}}
    try:
        with TemporaryDirectory() as tmp:
            for name, changes in VARIANTS.items():
                path = Path(tmp) / f'{name}.psl'
                path.write_text(revise_rules(lines, changes))
                sim.INDIVIDUAL_RULES = path
                report['variants'][name] = {'changed_weights': changes, 'cases': {}}
                for case in CASES:
                    result = sim.run_case(ROOT / 'cases' / f'{case}.json')
                    report['variants'][name]['cases'][case] = summarize(result)
                    s = report['variants'][name]['cases'][case]
                    print(f'{name:20} {case:34} turnout={s["turnout"]:.3f} '
                          f'aware={s["aware_mean"]:.3f} shares={s["shares"]}')
    finally:
        sim.INDIVIDUAL_RULES = original
    out = ROOT / 'runs/election_weight_sweep.json'
    out.write_text(json.dumps(report, indent=2) + '\n')
    print(f'Saved {out}')


if __name__ == '__main__':
    main()
