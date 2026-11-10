"""Synthetic civilian-assistance grid world with hand-written PSL rules."""
from __future__ import annotations

import argparse
from collections import deque
from copy import deepcopy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PERSON_RULES = ROOT / 'psl_rules/aid_person.psl'
GROUP_RULES = ROOT / 'psl_rules/aid_group.psl'
DIRECTIONS = ((0, -1), (-1, 0), (1, 0), (0, 1))


def read_case(path: Path) -> dict:
    data = json.loads(path.read_text())
    if 'extends' in data:
        parent = (path.parent / data.pop('extends')).resolve()
        if parent.parent != path.parent.resolve():
            raise ValueError('Case inheritance must stay in the case folder')
        base = read_case(parent)
        base.update(data)
        data = base
    ids = [p['id'] for p in data['people']]
    if len(ids) < 2 or len(ids) != len(set(ids)):
        raise ValueError('People must have distinct IDs')
    if not 0 <= data['goal_uptake'] <= 1 or data['step_limit'] < 1:
        raise ValueError('Invalid goal or step limit')
    if any(not 0 <= v <= 1 for v in data['thresholds'].values()):
        raise ValueError('Invalid action threshold')
    for p in data['people']:
        if not valid_cell(data, p['position']):
            raise ValueError(f'Invalid position for {p["id"]}')
        for field in ('need', 'access', 'safety', 'trust_peer'):
            if not 0 <= p[field] <= 1:
                raise ValueError(f'Invalid {field} for {p["id"]}')
    if not valid_cell(data, data['aid_site']):
        raise ValueError('Invalid aid site')
    for a, b in data['contacts']:
        if a not in ids or b not in ids or a == b:
            raise ValueError('Invalid contact')
    for kind in ('scheduled_announcements', 'scheduled_access_support'):
        for event in data.get(kind, []):
            if not 1 <= event['step'] <= data['step_limit'] or any(pid not in ids for pid in event['people']):
                raise ValueError(f'Invalid {kind} event')
            if kind == 'scheduled_access_support' and not 0 <= event['access'] <= 1:
                raise ValueError('Invalid access support')
    return data


def valid_cell(case: dict, pos) -> bool:
    x, y = pos
    return 0 <= x < case['width'] and 0 <= y < case['height'] and list(pos) not in case['blocked']


def next_cell(case: dict, start, end) -> list[int]:
    start, end = tuple(start), tuple(end)
    if start == end:
        return list(start)
    todo = deque([start])
    previous = {start: None}
    while todo:
        x, y = todo.popleft()
        for dx, dy in DIRECTIONS:
            nxt = (x + dx, y + dy)
            if nxt in previous or not valid_cell(case, nxt):
                continue
            previous[nxt] = (x, y)
            if nxt == end:
                while previous[nxt] != start:
                    nxt = previous[nxt]
                return list(nxt)
            todo.append(nxt)
    raise ValueError(f'No path from {start} to {end}')


def rule_lines(path: Path) -> list[str]:
    return [s.strip() for s in path.read_text().splitlines() if s.strip() and not s.lstrip().startswith('#')]


def infer(predicates: dict[str, int], rules: list[str], observations: dict[str, list[tuple]],
          targets: dict[str, list[tuple]]) -> dict[str, dict[str, float]]:
    from pslpython.model import Model
    from pslpython.partition import Partition
    from pslpython.predicate import Predicate
    from pslpython.rule import Rule
    model = Model('civilian-assistance')
    for name, size in predicates.items():
        model.add_predicate(Predicate(name, size=size))
    for line in rules:
        model.add_rule(Rule(line))
    for name, rows in observations.items():
        model.get_predicate(name).add_data(Partition.OBSERVATIONS, rows)
    for name, rows in targets.items():
        model.get_predicate(name).add_data(Partition.TARGETS, rows)
    result = model.infer(psl_options={'runtime.log.level': 'ERROR'})
    return {name: {str(row[0]): float(row[-1]) for row in result[model.get_predicate(name)].itertuples(index=False, name=None)}
            for name in targets}


def person_inference(case: dict, people: dict) -> tuple[dict, dict]:
    ids = list(people)
    contacts, trusts = [], []
    neighbors = {pid: set() for pid in ids}
    for a, b in case['contacts']:
        for source, target in ((a, b), (b, a)):
            contacts.append((source, target, 1.0))
            trusts.append((target, source, people[target]['trust_peer']))
            neighbors[source].add(target)
    observations = {
        'AwarePrev': [(pid, people[pid]['awareness']) for pid in ids],
        'SharePrev': [(pid, float(people[pid]['shared_prev'])) for pid in ids],
        'Need': [(pid, people[pid]['need']) for pid in ids],
        'Access': [(pid, people[pid]['access']) for pid in ids],
        'Safety': [(pid, people[pid]['safety']) for pid in ids],
        'ServedPrev': [(pid, float(people[pid]['served'])) for pid in ids],
        'AtAid': [(pid, float(people[pid]['position'] == case['aid_site'])) for pid in ids],
        'Reach': [(pid, min(1.0, len(neighbors[pid]) / 3)) for pid in ids],
        'Contact': contacts,
        'Trust': trusts,
    }
    targets = {name: [(pid,) for pid in ids] for name in ('Aware', 'Intent', 'ShareNow', 'Travel', 'ReceiveNow')}
    predicates = {name: (2 if name in ('Contact', 'Trust') else 1) for name in observations | targets}
    return infer(predicates, rule_lines(PERSON_RULES), observations, targets), observations


def group_inference(people: dict, intent: dict) -> tuple[dict, dict]:
    names = sorted({p['neighborhood'] for p in people.values()})
    observations = {'MeanNeed': [], 'MeanAccess': [], 'MeanIntent': [], 'CurrentUptake': []}
    metrics = {}
    for name in names:
        members = [p for p in people.values() if p['neighborhood'] == name]
        need = sum(p['need'] for p in members) / len(members)
        access = sum(p['access'] for p in members) / len(members)
        intended = sum(intent[p['id']] for p in members) / len(members)
        uptake = sum(p['served'] for p in members) / len(members)
        for key, value in (('MeanNeed', need), ('MeanAccess', access), ('MeanIntent', intended), ('CurrentUptake', uptake)):
            observations[key].append((name, value))
        metrics[name] = {'mean_need': need, 'mean_access': access, 'mean_intent': intended, 'uptake': uptake}
    scores = infer({name: 1 for name in observations | {'ServiceGap': []}}, rule_lines(GROUP_RULES),
                   observations, {'ServiceGap': [(name,) for name in names]})['ServiceGap']
    for name in names:
        metrics[name]['service_gap'] = scores[name]
    return metrics, observations


def initial_people(case: dict) -> dict:
    seeds = set(case['seed_ids'])
    return {p['id']: {**deepcopy(p), 'awareness': float(p['id'] in seeds),
                      'shared_prev': 0, 'shared_once': 0, 'served': 0} for p in case['people']}


def step(case: dict, people: dict, number: int) -> dict:
    before = deepcopy(people)
    announcements, access_support = [], []
    for event in case.get('scheduled_access_support', []):
        if event['step'] == number:
            for pid in event['people']:
                people[pid]['access'] = max(people[pid]['access'], event['access'])
                access_support.append(pid)
    for event in case.get('scheduled_announcements', []):
        if event['step'] == number:
            for pid in event['people']:
                people[pid]['awareness'] = 1.0
                announcements.append(pid)
    scores, observations = person_inference(case, people)
    actions = []
    threshold = case['thresholds']
    for pid, p in people.items():
        p['awareness'] = max(p['awareness'], scores['Aware'][pid])
        share = not p['shared_once'] and scores['ShareNow'][pid] >= threshold['share']
        p['shared_prev'] = int(share)
        if share:
            p['shared_once'] = 1
            actions.append({'person': pid, 'action': 'share', 'score': scores['ShareNow'][pid]})
        if p['served']:
            continue
        if p['position'] == case['aid_site'] and scores['ReceiveNow'][pid] >= threshold['receive']:
            p['served'] = 1
            actions.append({'person': pid, 'action': 'receive', 'score': scores['ReceiveNow'][pid]})
        elif p['position'] != case['aid_site'] and scores['Travel'][pid] >= threshold['travel']:
            old = list(p['position'])
            p['position'] = next_cell(case, old, case['aid_site'])
            actions.append({'person': pid, 'action': 'move', 'from': old, 'to': p['position'],
                            'score': scores['Travel'][pid]})
    groups, group_observations = group_inference(people, scores['Intent'])
    uptake = sum(p['served'] for p in people.values()) / len(people)
    return {'step': number, 'announcements': announcements, 'access_support': access_support,
            'before': before, 'observations': observations, 'scores': scores, 'actions': actions,
            'after': deepcopy(people), 'group_observations': group_observations, 'groups': groups,
            'uptake': uptake, 'goal': uptake >= case['goal_uptake']}


def run_case(path: Path) -> dict:
    case = read_case(path)
    people = initial_people(case)
    trace, first_goal_step = [], None
    for number in range(1, case['step_limit'] + 1):
        record = step(case, people, number)
        trace.append(record)
        if record['goal'] and first_goal_step is None:
            first_goal_step = number
    return {'case_file': str(path), 'configuration': case,
            'rules': {'person': rule_lines(PERSON_RULES), 'group': rule_lines(GROUP_RULES)},
            'trace': trace, 'result': {'goal': trace[-1]['goal'], 'first_goal_step': first_goal_step,
                                     'steps': trace[-1]['step'], 'uptake': trace[-1]['uptake'],
                                     'awareness': sum(p['awareness'] for p in people.values()) / len(people)}}


def grid(case: dict, people: dict) -> str:
    cells = {(x, y): '.' for y in range(case['height']) for x in range(case['width'])}
    for x, y in case['blocked']:
        cells[x, y] = '#'
    cells[tuple(case['aid_site'])] = 'AID'
    for pid, p in people.items():
        cell = tuple(p['position'])
        cells[cell] = pid if cells[cell] in ('.', 'AID') else cells[cell] + '/' + pid
    return '\n'.join(' '.join(f'{cells[x,y]:>8}' for x in range(case['width'])) for y in range(case['height']))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('case', nargs='?', default='aid_baseline', help='Bundled case name or JSON path')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--show-grid', action='store_true')
    args = parser.parse_args()
    path = Path(args.case)
    if not path.exists():
        path = ROOT / 'cases' / f'{args.case}.json'
    if args.show_grid:
        case = read_case(path)
        print(grid(case, initial_people(case)))
        return
    result = run_case(path)
    output = args.output or ROOT / 'runs' / f'{path.stem}-psl.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + '\n')
    print(f'{path.stem}: uptake {result["result"]["uptake"]:.3f}, '
          f'awareness {result["result"]["awareness"]:.3f}, '
          f'goal {result["result"]["goal"]}, steps {result["result"]["steps"]}')
    print(f'Saved {output}')


if __name__ == '__main__':
    main()
