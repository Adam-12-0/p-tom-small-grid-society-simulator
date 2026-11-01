"""Terminal rendering generated from committed trace records."""
import time
import argparse
import csv
import io
import json
from contextlib import redirect_stdout
from types import SimpleNamespace
from pathlib import Path

def render(world, record, mode='print', delay=0):
    if mode=='quiet': return
    state=record['after']
    width=world.config['width']; height=world.config['height']
    occupants={}
    for pid,p in state['people'].items(): occupants.setdefault(tuple(p['position']),[]).append(pid)
    labels={cell:','.join(ids) for cell,ids in occupants.items()}
    for name,cell in world.places.items(): labels[cell]=labels.get(cell,'.')+'/'+name[0].upper()
    for cell in world.blocked: labels[cell]='#'
    cell_width=max(5,max(map(len,labels.values()),default=1))+2
    print(f"\n{world.config['case'].upper()}  step {record['step']} / {world.config['step_limit']}  policy={world.config['policy']}  "+
          (f"desk={'open' if state['desk_open'] else 'closed'}" if world.config['case']=='library' else f"drills={state['tools_at_counter']}/{state['tool_count']}"))
    print('     '+''.join(f'x{x}'.center(cell_width+1) for x in range(width)))
    border='     +'+('+'.join('-'*cell_width for _ in range(width)))+'+'
    for y in range(height):
        print(border)
        print(f'y{y:<3} |'+'|'.join(labels.get((x,y),'.').ljust(cell_width) for x in range(width))+'|')
    print(border)
    print('Legend: . empty  # blocked  /D desk  /C counter  /R reading place')
    print('Actions and events')
    if not record['actions']: print('  None at step 0.')
    for item in record['actions']:
        print(f"{item['person']}: {item['action']}  {item.get('detail','')}  rule {item.get('rule') or '-'}")
    print('State changes')
    changes=state_changes(record)
    for change in changes: print('  '+change)
    if record.get('llm_calls'):
        print('Model choices')
        for call in record['llm_calls']:
            chosen=call['llm']['applied_action']
            args=chosen.get('arguments',{})
            label=chosen['action']+(' '+str(args.get('direction',args.get('person',''))) if args else '')
            try: reason=json.loads(call['llm']['response']).get('reason','')
            except (ValueError,TypeError,AttributeError): reason=''
            error=call['llm'].get('validation_error')
            print(f"  {call['person']}: {label}"+(f' | {reason}' if reason else '')+(f' | invalid: {error}' if error else ''))
    print('State summary')
    for pid,p in state['people'].items():
        extra=f" needs_help={str(p['needs_help']).lower()}" if p['role']=='reader' else (f" has_tool={str(p['has_tool']).lower()} work_left={p['work_left']}" if p['role']=='worker' else '')
        print(f"{pid}: {p['status']}{extra}")
    print(f"Queue={state['queue']} Return queue={state['return_queue']} Served={state['served']} Completed={state['completed']} Goal={'reached' if record['goal'] else 'pending'}")
    if mode=='interactive': input('Press Enter for next step...')
    elif mode=='delay': time.sleep(delay)


def state_changes(record):
    if record['step']==0: return ['Initial world and person states.']
    before=record['before'];after=record['after']
    changes=[]
    fields=('position','status','needs_help','has_tool','work_left','arrival_step','served_step','completed_step','wait_steps')
    for pid,person in after['people'].items():
        old=before['people'][pid]
        for field in fields:
            if old.get(field)!=person.get(field):
                changes.append(f'{pid} {field}: {old.get(field)} -> {person.get(field)}')
    for field in ('queue','return_queue','desk_open','tools_at_counter','tool_count','served','completed'):
        if before.get(field)!=after.get(field):
            changes.append(f'{field}: {before.get(field)} -> {after.get(field)}')
    return changes or ['No state value changed.']

def export_runs(saved_paths,text_path=None,tsv_path=None):
    """Export saved JSON runs as one readable timeline and one state table."""
    saved_paths=[Path(path) for path in saved_paths]
    if not saved_paths: raise ValueError('At least one saved run is required')
    first=saved_paths[0]
    text_path=Path(text_path) if text_path else first.with_suffix('.txt')
    tsv_path=Path(tsv_path) if tsv_path else first.with_suffix('.tsv')
    text_path.parent.mkdir(parents=True,exist_ok=True)
    tsv_path.parent.mkdir(parents=True,exist_ok=True)
    runs=[]
    for saved_path in saved_paths:
        data=json.loads(saved_path.read_text())
        config=data['configuration']
        world=SimpleNamespace(config=config,
            places={name:tuple(cell) for name,cell in config['places'].items()},
            blocked={tuple(cell) for cell in config['blocked']})
        runs.append((saved_path,data,world))
    buffer=io.StringIO()
    with redirect_stdout(buffer):
        print('WORLD PROGRESSION')
        print('Each run starts at step 0. Every later section shows the committed world after that step.')
        print('Actions and events explain what happened. State changes list the values that actually changed.')
        print('Runs in this file:')
        for saved_path,data,_ in runs:
            last=data['trace'][-1]
            print(f"  {saved_path.stem}: {'goal reached' if last['goal'] else 'goal not reached'} at step {last['step']}")
        for saved_path,data,world in runs:
            print('\n'+'='*78)
            print(f"RUN: {saved_path.stem} | world: {world.config['case']} | policy: {world.config['policy']}")
            print('='*78)
            for record in data['trace']: render(world,record)
            last=data['trace'][-1]
            print(f"\nFinal result for {saved_path.stem}: {'goal reached' if last['goal'] else 'goal not reached'} at step {last['step']}.")
    text_path.write_text(buffer.getvalue())
    columns=('run','step','goal','person','role','x','y','task','status','needs_help','has_tool',
             'work_left','arrival_step','served_step','completed_step','wait_steps',
             'queue','return_queue','desk_open','tools_at_counter','tool_count','chosen_action','validation_error')
    with tsv_path.open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=columns,delimiter='\t')
        writer.writeheader()
        for saved_path,data,_ in runs:
            for record in data['trace']:
                state=record['after']
                chosen={a['person']:a['action'] for a in record.get('chosen_actions',[])}
                errors={a['person']:a['llm'].get('validation_error') for a in record.get('llm_calls',[])}
                for pid,person in state['people'].items():
                    row={'run':saved_path.stem,'step':record['step'],'goal':record['goal'],
                         'person':pid,'role':person['role'],
                         'x':person['position'][0],'y':person['position'][1],
                         'queue':json.dumps(state['queue']),'return_queue':json.dumps(state['return_queue']),
                         'desk_open':state['desk_open'],'tools_at_counter':state['tools_at_counter'],
                         'tool_count':state['tool_count'],'chosen_action':chosen.get(pid,''),
                         'validation_error':errors.get(pid) or ''}
                    row.update({field:person[field] for field in columns if field in person})
                    writer.writerow(row)
    return text_path,tsv_path

if __name__=='__main__':
    parser=argparse.ArgumentParser(description='Export saved runs as a readable timeline and TSV state table')
    parser.add_argument('run_json',type=Path,nargs='+')
    parser.add_argument('--text',type=Path)
    parser.add_argument('--tsv',type=Path)
    args=parser.parse_args()
    text_path,tsv_path=export_runs(args.run_json,args.text,args.tsv)
    print(f'Saved {text_path} and {tsv_path}')
