"""Synchronous simulation with serializable, inspectable transitions."""
from copy import deepcopy
import json
from rules import next_move,check_invariants,DIRECTIONS,action,legal_moves

def goal(world):
    spec=world.config['goal']
    if spec['type']=='readers_served': return sum(p.served_step is not None for p in world.people.values())>=spec['count']
    if spec['type']=='jobs_completed':
        enough=sum(p.completed_step is not None for p in world.people.values())>=spec['count']
        return enough and (not spec.get('all_tools_returned',False) or world.tools_at_counter==world.tool_count)
    raise ValueError('Unknown goal type')

def add(actions,p,action,rule=None,detail='',partner=None,kind='action'):
    actions.append({'person':p,'action':action,'rule':rule,'detail':detail,'partner':partner,'kind':kind})

def scheduled(world,actions):
    for event in world.config['scheduled_changes']:
        if event['step']!=world.step: continue
        if event['field']=='desk_open':
            world.desk_open=event['value']
            add(actions,'WORLD','desk_open',detail=str(event['value']),kind='scheduled')
        elif event['field']=='add_tools':
            n=event['value']
            if not isinstance(n,int) or n<1: raise ValueError('add_tools must be a positive integer')
            world.tool_count+=n; world.tools_at_counter+=n
            add(actions,'WORLD','add_tools',detail=str(n),kind='scheduled')

def decide(world,pid,options,manual,agent):
    return agent.choose(world,pid,options) if agent else manual

def move_choice(world,p,goal,agent):
    if agent:
        selected=decide(world,p.id,legal_moves(world,p.position)+[action('wait')],None,agent)
        if selected['action']!='move': return None
        direction=selected['arguments']['direction']
        dx,dy=dict(DIRECTIONS)[direction]
        return direction,(p.position[0]+dx,p.position[1]+dy)
    return next_move(world,p.position,goal)

def library_step(world,actions,agent=None):
    desk=world.places['desk']
    old_queue=list(world.queue)
    serving=world.desk_open and bool(old_queue)
    if serving and agent:
        serving=decide(world,'L1',[action('serve',person=old_queue[0]),action('wait')],None,agent)['action']=='serve'
    if serving:
        pid=old_queue[0];p=world.people[pid]
        world.queue.remove(pid);p.needs_help=False;p.status='served';p.served_step=world.step
        p.wait_steps=world.step-p.arrival_step
        add(actions,'L1','serve','LIB_SERVE',pid,partner=pid)
    else: add(actions,'L1','wait',detail='desk closed' if not world.desk_open else 'queue empty')
    arrivals=[]
    for p in sorted(world.people.values(),key=lambda q:q.id):
        if p.role!='reader': continue
        if not p.needs_help:
            if p.status=='reading':
                selected=decide(world,p.id,[action('read'),action('wait')],action('read'),agent)
                add(actions,p.id,'read' if selected['action']=='read' else 'wait','LIB_READ' if selected['action']=='read' else None)
            else: add(actions,p.id,'stay',detail='already served',kind='state')
        elif p.id in world.queue: add(actions,p.id,'wait',detail='in queue')
        elif p.position==desk: arrivals.append(p.id)
        else:
            move=move_choice(world,p,desk,agent)
            if move:
                before=p.position;p.position=move[1]
                add(actions,p.id,'move '+move[0],'LIB_MOVE',f'{before} -> {p.position}')
                if p.position==desk: arrivals.append(p.id)
            else: add(actions,p.id,'wait',detail='agent choice or invalid answer')
    for pid in sorted(arrivals):
        p=world.people[pid];p.arrival_step=world.step;p.status='waiting';world.queue.append(pid)
        add(actions,pid,'join queue','LIB_QUEUE',kind='effect')

def workshop_step(world,actions,priority_fn=None,agent=None):
    counter=world.places['counter']
    old_returns=list(world.return_queue);old_loans=list(world.queue)
    handed_to=None
    handover=None
    if old_returns:
        pid=sorted(old_returns,key=lambda x:(world.people[x].arrival_step,x))[0]
        handover=('return',pid)
    elif old_loans and world.tools_at_counter:
        if priority_fn:
            scores=priority_fn(world,old_loans)
            pid=sorted(old_loans,key=lambda x:(-scores[x],world.people[x].arrival_step,x))[0]
            add(actions,'S1','priority scores',detail=str(scores),kind='diagnostic')
        else: pid=sorted(old_loans,key=lambda x:(world.people[x].arrival_step,x))[0]
        handover=('loan',pid)
    if handover and agent:
        kind,pid=handover
        verb='return' if kind=='return' else 'loan'
        if decide(world,'S1',[action(verb,person=pid),action('wait')],None,agent)['action']=='wait': handover=None
    if handover:
        kind,pid=handover;p=world.people[pid]
        if kind=='return':
            p.has_tool=False;p.status='completed';p.completed_step=world.step
            p.wait_steps+=world.step-p.arrival_step
            world.return_queue.remove(pid);world.tools_at_counter+=1
            add(actions,'S1','accept return','WORK_RETURN',pid,partner=pid)
        else:
            p.has_tool=True;p.status='carrying';p.wait_steps+=world.step-p.arrival_step
            handed_to=pid;world.queue.remove(pid);world.tools_at_counter-=1
            add(actions,'S1','loan drill','WORK_LOAN',pid,partner=pid)
    else: add(actions,'S1','wait',detail='no handover')
    loan_arrivals=[];return_arrivals=[]
    for p in sorted(world.people.values(),key=lambda q:q.id):
        if p.role!='worker': continue
        if p.completed_step is not None: add(actions,p.id,'stay',detail='job completed',kind='state');continue
        if p.id==handed_to: add(actions,p.id,'receive drill',detail='moves next step',kind='effect');continue
        if p.id in world.queue or p.id in world.return_queue: add(actions,p.id,'wait',detail='queued');continue
        if p.has_tool and p.work_left==0:
            if p.position==counter: return_arrivals.append(p.id)
            else:
                move=move_choice(world,p,counter,agent)
                if move:
                    before=p.position;p.position=move[1]
                    add(actions,p.id,'move '+move[0],'WORK_MOVE',f'{before} -> {p.position}')
                    if p.position==counter: return_arrivals.append(p.id)
                else: add(actions,p.id,'wait')
        elif p.has_tool:
            if p.position==p.workstation:
                selected=decide(world,p.id,[action('work'),action('wait')],action('work'),agent)
                if selected['action']=='work':
                    p.work_left-=1;p.status='working' if p.work_left else 'returning'
                    add(actions,p.id,'work','WORK_JOB',f'work_left={p.work_left}')
                else: add(actions,p.id,'wait')
            else:
                move=move_choice(world,p,p.workstation,agent)
                if move:
                    before=p.position;p.position=move[1]
                    add(actions,p.id,'move '+move[0],'WORK_MOVE',f'{before} -> {p.position}')
                else: add(actions,p.id,'wait')
        elif p.position==counter: loan_arrivals.append(p.id)
        else:
            move=move_choice(world,p,counter,agent)
            if move:
                before=p.position;p.position=move[1]
                add(actions,p.id,'move '+move[0],'WORK_MOVE',f'{before} -> {p.position}')
                if p.position==counter: loan_arrivals.append(p.id)
            else: add(actions,p.id,'wait')
    for pid in sorted(loan_arrivals):
        p=world.people[pid];p.status='waiting';p.arrival_step=world.step;world.queue.append(pid)
        add(actions,pid,'join loan queue','WORK_QUEUE',kind='effect')
    for pid in sorted(return_arrivals):
        p=world.people[pid];p.status='return_wait';p.arrival_step=world.step;world.return_queue.append(pid)
        add(actions,pid,'join return queue','WORK_QUEUE',kind='effect')

def run(world,mode='print',delay=0,priority_fn=None,agent=None,initial_trace=None,on_commit=None):
    from display import render
    check_invariants(world)
    if initial_trace:
        records=list(initial_trace)
        if json.dumps(records[-1]['after'],sort_keys=True)!=json.dumps(world.state(),sort_keys=True):
            raise ValueError('Checkpoint state does not match trace')
        if records[-1]['goal']: return records
    else:
        records=[]
        initial=world.state()
        record={'step':0,'before':deepcopy(initial),'after':deepcopy(initial),'actions':[],
                'interactions':[],'rule_ids':[],'goal':goal(world),'llm_calls':[], 'chosen_actions':[]}
        records.append(record);render(world,record,mode,delay)
        if on_commit: on_commit(records)
        if record['goal']: return records
    for step in range(world.step+1,world.config['step_limit']+1):
        before=world.state();world.step=step;actions=[]
        scheduled(world,actions)
        log_start=len(agent.logs) if agent else 0
        if agent: agent.snapshot=world.state()
        if world.config['case']=='library': library_step(world,actions,agent)
        else: workshop_step(world,actions,priority_fn,agent)
        check_invariants(world)
        record={'step':step,'before':before,'after':world.state(),'actions':actions,
                'interactions':[{'from':a['person'],'to':a['partner'],'action':a['action']} for a in actions if a['partner']],
                'rule_ids':[a['rule'] for a in actions if a['rule']], 'goal':goal(world),
                'chosen_actions':[a for a in actions if a['kind']=='action'],
                'llm_calls':agent.logs[log_start:] if agent else []}
        records.append(record);render(world,record,mode,delay)
        if on_commit: on_commit(records)
        if record['goal']: break
    return records
