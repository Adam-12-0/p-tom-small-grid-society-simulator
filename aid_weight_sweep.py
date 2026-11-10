"""Sensitivity check for provisional civilian-assistance PSL weights."""
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import aid_psl as sim

ROOT = Path(__file__).resolve().parent
CASES = ('aid_baseline', 'aid_outreach', 'aid_access', 'aid_outreach_access')
VARIANTS = {
    'reference': {},
    'stronger_diffusion': {'SharePrev(P) & Contact(P,Q) & Trust(Q,P) -> Aware(Q)': 8,
                           'Aware(P) & Reach(P) -> ShareNow(P)': 6},
    'stronger_action': {'Aware(P) & Need(P) -> Intent(P)': 6,
                        'Intent(P) & Access(P) & !ServedPrev(P) -> Travel(P)': 7,
                        'AtAid(P) & Need(P) & !ServedPrev(P) -> ReceiveNow(P)': 7},
    'weaker_safety_effect': {'!Safety(P) -> !Intent(P)': 1},
}


def revise(lines, changes):
    output, found = [], set()
    for line in lines:
        body = line.split(': ', 1)[-1].removesuffix(' ^2')
        if body in changes:
            line = f'{changes[body]}: {body} ^2'
            found.add(body)
        output.append(line)
    if found != changes.keys():
        raise ValueError(f'Rule not found: {changes.keys() - found}')
    return '\n'.join(output) + '\n'


def summary(result):
    trace = result['trace']
    actions = [a for t in trace for a in t['actions']]
    return {'uptake': result['result']['uptake'], 'awareness': result['result']['awareness'],
            'shares': sum(a['action'] == 'share' for a in actions),
            'moves': sum(a['action'] == 'move' for a in actions),
            'receives': sum(a['action'] == 'receive' for a in actions),
            'first_goal_step': result['result']['first_goal_step']}


def main():
    original = sim.PERSON_RULES
    lines = original.read_text().splitlines()
    report = {'note': 'Illustrative sensitivity check, not fitted to observed behavior.', 'variants': {}}
    try:
        with TemporaryDirectory() as tmp:
            for name, changes in VARIANTS.items():
                path = Path(tmp) / f'{name}.psl'
                path.write_text(revise(lines, changes))
                sim.PERSON_RULES = path
                report['variants'][name] = {'changed_weights': changes, 'cases': {}}
                for case in CASES:
                    result = sim.run_case(ROOT / 'cases' / f'{case}.json')
                    item = summary(result)
                    report['variants'][name]['cases'][case] = item
                    print(f'{name:20} {case:24} uptake={item["uptake"]:.3f} '
                          f'aware={item["awareness"]:.3f} moves={item["moves"]}')
    finally:
        sim.PERSON_RULES = original
    out = ROOT / 'runs/aid_weight_sweep.json'
    out.write_text(json.dumps(report, indent=2) + '\n')
    print(f'Saved {out}')


if __name__ == '__main__':
    main()
