"""Validated case files and mutable world state."""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from pathlib import Path
import copy
import json

@dataclass
class Person:
    id: str
    role: str
    position: tuple[int, int]
    task: str
    status: str
    needs_help: bool = False
    has_tool: bool = False
    work_left: int = 0
    urgency: float = 0.0
    workstation: tuple[int, int] | None = None
    arrival_step: int | None = None
    served_step: int | None = None
    completed_step: int | None = None
    wait_steps: int = 0

@dataclass
class World:
    config: dict
    people: dict[str, Person]
    blocked: set[tuple[int, int]]
    places: dict[str, tuple[int, int]]
    queue: list[str] = field(default_factory=list)
    return_queue: list[str] = field(default_factory=list)
    desk_open: bool = True
    tool_count: int = 0
    tools_at_counter: int = 0
    step: int = 0

    def state(self) -> dict:
        return {"step": self.step, "people": {k: asdict(v) for k,v in sorted(self.people.items())},
                "queue": list(self.queue), "return_queue": list(self.return_queue),
                "desk_open": self.desk_open, "tool_count": self.tool_count,
                "tools_at_counter": self.tools_at_counter,
                "served": sum(p.served_step is not None for p in self.people.values()),
                "completed": sum(p.completed_step is not None for p in self.people.values())}

    def valid_cell(self, position: tuple[int,int]) -> bool:
        x,y=position
        return 0 <= x < self.config['width'] and 0 <= y < self.config['height'] and position not in self.blocked


def _load_data(path: Path, seen: set[Path]) -> dict:
    path=path.resolve()
    if path in seen: raise ValueError('Circular case inheritance')
    seen.add(path)
    data=json.loads(path.read_text())
    if 'extends' in data:
        base=(path.parent/data.pop('extends')).resolve()
        if base.parent != path.parent: raise ValueError('Case inheritance must stay in the case folder')
        merged=_load_data(base,seen)
        merged.update(data)
        return merged
    return data


def load_case(path: str | Path) -> World:
    data=_load_data(Path(path),set())
    required={'case','width','height','blocked','places','people','step_limit','goal'}
    missing=required-data.keys()
    if missing: raise ValueError('Missing case fields: '+', '.join(sorted(missing)))
    data=copy.deepcopy(data)
    data.setdefault('policy','manual')
    data.setdefault('scheduled_changes',[])
    data.setdefault('rules',[])
    data.setdefault('desk_open',True)
    data.setdefault('tool_count',0)
    if data['case'] not in {'library','workshop'}: raise ValueError('Unknown case')
    if not isinstance(data['width'],int) or not isinstance(data['height'],int) or min(data['width'],data['height']) < 1: raise ValueError('Invalid grid size')
    if not isinstance(data['step_limit'],int) or data['step_limit'] < 0: raise ValueError('Invalid step_limit')
    blocked={tuple(v) for v in data['blocked']}
    places={k:tuple(v) for k,v in data['places'].items()}
    people={}
    for row in data['people']:
        missing={'id','role','position','task','status'}-row.keys()
        if missing: raise ValueError(f"Person missing fields: {', '.join(sorted(missing))}")
        row=copy.deepcopy(row)
        row['position']=tuple(row['position'])
        if 'workstation' in row: row['workstation']=tuple(row['workstation'])
        try: p=Person(**row)
        except TypeError as exc: raise ValueError(f"Invalid person {row.get('id')}: {exc}") from exc
        if p.id in people: raise ValueError(f'Duplicate person ID: {p.id}')
        if not 0 <= p.urgency <= 1: raise ValueError(f'Invalid urgency: {p.id}')
        people[p.id]=p
    world=World(config=data,people=people,blocked=blocked,places=places,
                desk_open=data['desk_open'],tool_count=data['tool_count'],tools_at_counter=data['tool_count'])
    for cell in blocked:
        x,y=cell
        if not (0 <= x < data['width'] and 0 <= y < data['height']): raise ValueError(f'Blocked cell outside grid: {cell}')
    for name,cell in places.items():
        if not world.valid_cell(cell): raise ValueError(f'Invalid place {name}: {cell}')
    for p in people.values():
        if not world.valid_cell(p.position): raise ValueError(f'Invalid position for {p.id}: {p.position}')
        if p.workstation is not None and not world.valid_cell(p.workstation): raise ValueError(f'Invalid workstation for {p.id}')
    needed='desk' if data['case']=='library' else 'counter'
    if needed not in places: raise ValueError(f'Missing required place: {needed}')
    if data['case']=='library' and len([p for p in people.values() if p.role=='librarian']) != 1: raise ValueError('Library needs one librarian')
    if data['case']=='workshop':
        if len([p for p in people.values() if p.role=='storekeeper']) != 1: raise ValueError('Workshop needs one storekeeper')
        if not isinstance(data['tool_count'],int) or data['tool_count'] < 0: raise ValueError('Invalid tool_count')
        for p in people.values():
            if p.role=='worker' and p.workstation is None: raise ValueError(f'Missing workstation: {p.id}')
    for event in data['scheduled_changes']:
        if not {'step','field','value'} <= event.keys(): raise ValueError('Scheduled change needs step, field, value')
        if not 1 <= event['step'] <= data['step_limit']: raise ValueError('Scheduled change step outside run')
        if event['field'] not in ({'desk_open'} if data['case']=='library' else {'add_tools'}): raise ValueError('Unsupported scheduled change')
    world.config['people']=[asdict(p) for p in people.values()]
    return world


def restore_case(path: str | Path, configuration: dict, state: dict) -> World:
    """Restore a committed checkpoint for retry after an API failure."""
    world=load_case(path)
    if world.config['case'] != configuration['case']:
        raise ValueError('Checkpoint case does not match the case file')
    world.config=copy.deepcopy(configuration)
    people={}
    for pid,row in state['people'].items():
        row=copy.deepcopy(row)
        row['position']=tuple(row['position'])
        if row['workstation'] is not None: row['workstation']=tuple(row['workstation'])
        people[pid]=Person(**row)
    world.people=people
    world.queue=list(state['queue'])
    world.return_queue=list(state['return_queue'])
    world.desk_open=state['desk_open']
    world.tool_count=state['tool_count']
    world.tools_at_counter=state['tools_at_counter']
    world.step=state['step']
    from rules import check_invariants
    check_invariants(world)
    return world
