"""Constrained generated-rule checks against a manual trajectory."""
from simulation import run
from world import load_case

FIELDS={'library':{'role','task','status','needs_help'},
        'workshop':{'role','task','status','has_tool','work_left','urgency'}}
TARGET={'library':('LIB_MOVE','move','reader'),
        'workshop':('WORK_MOVE','move','worker')}
OPS={'eq':lambda a,b:a==b,'ne':lambda a,b:a!=b,'gt':lambda a,b:a>b,
     'ge':lambda a,b:a>=b,'lt':lambda a,b:a<b,'le':lambda a,b:a<=b}

def validate(case_path,body):
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
