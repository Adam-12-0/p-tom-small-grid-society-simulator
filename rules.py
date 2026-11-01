"""Hard constraints, shortest paths, and named manual behavior rules."""
from collections import deque

DIRECTIONS=(('up',(0,-1)),('left',(-1,0)),('right',(1,0)),('down',(0,1)))
RULES={
 'LIB_MOVE':'Reader moves one cell on a shortest path to the help desk.',
 'LIB_QUEUE':'Arriving reader joins the service queue for the next step.',
 'LIB_SERVE':'Open desk serves at most one previously queued reader.',
 'LIB_READ':'Reader without a help request keeps reading.',
 'WORK_MOVE':'Worker moves to counter or workstation along a shortest path.',
 'WORK_QUEUE':'Arriving worker joins loan or return queue for the next step.',
 'WORK_LOAN':'Storekeeper lends one available drill to a queued worker.',
 'WORK_RETURN':'Storekeeper accepts one returned drill before any loan.',
 'WORK_JOB':'Worker holding a drill completes one work unit at workstation.'}

def next_move(world, start, target):
    if start==target: return None
    todo=deque([(start,[])])
    seen={start}
    while todo:
        pos,path=todo.popleft()
        for name,(dx,dy) in DIRECTIONS:
            nxt=(pos[0]+dx,pos[1]+dy)
            if nxt in seen or not world.valid_cell(nxt): continue
            route=path+[name]
            if nxt==target:
                first=route[0]
                delta=dict(DIRECTIONS)[first]
                return first,(start[0]+delta[0],start[1]+delta[1])
            seen.add(nxt)
            todo.append((nxt,route))
    raise ValueError(f'No path from {start} to {target}')

def check_invariants(world):
    if len(world.queue)!=len(set(world.queue)) or len(world.return_queue)!=len(set(world.return_queue)):
        raise AssertionError('Duplicate queue entry')
    if world.config['case']=='workshop':
        held=sum(p.has_tool for p in world.people.values())
        if world.tools_at_counter+held != world.tool_count:
            raise AssertionError('Drill inventory changed unexpectedly')
    for p in world.people.values():
        if not world.valid_cell(p.position): raise AssertionError(f'Illegal position: {p.id}')

RULE_SPECS={
 'LIB_MOVE':{'description':RULES['LIB_MOVE'],'conditions':['reader needs help','reader is not at desk','walkable path exists'],'effect':'move one legal cell toward desk'},
 'LIB_QUEUE':{'description':RULES['LIB_QUEUE'],'conditions':['reader arrives at desk'],'effect':'append to queue for next step'},
 'LIB_SERVE':{'description':RULES['LIB_SERVE'],'conditions':['desk open','reader queued before step'],'effect':'serve one reader and remove from queue'},
 'LIB_READ':{'description':RULES['LIB_READ'],'conditions':['reader has no help request and is reading'],'effect':'remain reading'},
 'WORK_MOVE':{'description':RULES['WORK_MOVE'],'conditions':['worker has a destination','walkable path exists'],'effect':'move one legal cell'},
 'WORK_QUEUE':{'description':RULES['WORK_QUEUE'],'conditions':['worker arrives at counter'],'effect':'append to loan or return queue for next step'},
 'WORK_LOAN':{'description':RULES['WORK_LOAN'],'conditions':['drill available','worker queued before step','no return handover this step'],'effect':'transfer one drill to worker'},
 'WORK_RETURN':{'description':RULES['WORK_RETURN'],'conditions':['worker with drill queued to return before step'],'effect':'transfer one drill to counter and complete job'},
 'WORK_JOB':{'description':RULES['WORK_JOB'],'conditions':['worker holds drill','worker at workstation','work remains'],'effect':'reduce work_left by one'}
}

def action(name,**arguments): return {'action':name,'arguments':arguments}

def legal_moves(world,position):
    return [action('move',direction=name) for name,(dx,dy) in DIRECTIONS
            if world.valid_cell((position[0]+dx,position[1]+dy))]

RULE_TEXT={
 'urgency':'3: Waiting(W) & Urgency(W) -> Priority(W) ^2',
 'low_default':'1: !Priority(W) ^2',
}

def priority_scores(world,waiting):
    from pslpython.model import Model
    from pslpython.partition import Partition
    from pslpython.predicate import Predicate
    from pslpython.rule import Rule
    model=Model('workshop-priority')
    for name in ('Waiting','Urgency','Priority'):
        model.add_predicate(Predicate(name,size=1))
    for rule in RULE_TEXT.values(): model.add_rule(Rule(rule))
    model.get_predicate('Waiting').add_data(Partition.OBSERVATIONS,[(pid,1.0) for pid in waiting])
    model.get_predicate('Urgency').add_data(Partition.OBSERVATIONS,[(pid,world.people[pid].urgency) for pid in waiting])
    model.get_predicate('Priority').add_data(Partition.TARGETS,[(pid,) for pid in waiting])
    result=model.infer(psl_options={'runtime.log.level':'ERROR'})
    frame=result[model.get_predicate('Priority')]
    return {str(row[0]):float(row[1]) for row in frame.itertuples(index=False,name=None)}


FIELDS={'library':{'role','task','status','needs_help'},
        'workshop':{'role','task','status','has_tool','work_left','urgency'}}
TARGET={'library':('LIB_MOVE','move','reader'),
        'workshop':('WORK_MOVE','move','worker')}
OPS={'eq':lambda a,b:a==b,'ne':lambda a,b:a!=b,'gt':lambda a,b:a>b,
     'ge':lambda a,b:a>=b,'lt':lambda a,b:a<b,'le':lambda a,b:a<=b}

def validate_generated_rule(case_path,body):
    from world import load_case
    from simulation import run
    world=load_case(case_path)
    case=world.config['case']
    if not isinstance(body,dict) or not isinstance(body.get('rules'),list) or len(body['rules'])!=1:
        raise ValueError('Exactly one replacement rule is required')
    rule=body['rules'][0]
    if not isinstance(rule,dict) or not {'id','description','conditions','effect'} <= rule.keys(): raise ValueError('Malformed rule')
    target,action,role=TARGET[case]
    if rule['id'] != 'ALT_'+target: raise ValueError('Rule ID must identify the requested replacement')
    if rule['effect'] != {'action':action}: raise ValueError('Effect must name only the permitted behavior action')
    if not isinstance(rule['conditions'],list) or not rule['conditions']: raise ValueError('Conditions are required')
    for condition in rule['conditions']:
        if not isinstance(condition,dict) or set(condition)!={'field','op','value'}: raise ValueError('Malformed condition')
        if condition['field'] not in FIELDS[case] or condition['op'] not in OPS: raise ValueError('Field or operator is not allowed for this case')
        if condition['field'] in {'urgency'} and not isinstance(condition['value'],(int,float)): raise ValueError('Numeric value required')
    if not any(c=={'field':'role','op':'eq','value':role} for c in rule['conditions']):
        raise ValueError('Rule must specify the relevant role')
    trace=run(world,mode='quiet')
    matches=0;mismatches=[]
    for record in trace[1:]:
        for pid,person in record['before']['people'].items():
            if person['role']!=role: continue
            if not all(OPS[c['op']](person[c['field']],c['value']) for c in rule['conditions']): continue
            matches+=1
            acts=[a['action'] for a in record['actions'] if a['person']==pid]
            if not any(a.startswith(action+' ') for a in acts): mismatches.append({'step':record['step'],'person':pid,'manual_actions':acts})
    if not matches: raise ValueError('Rule never applies in the reference case')
    if mismatches: raise ValueError(f'Rule disagrees with reference behavior: {mismatches[:3]}')
    return {'target':target,'matched_actions':matches,'mismatches':mismatches,
            'hard_constraints':'effects are action choices only; Python enforces movement and resources'}
