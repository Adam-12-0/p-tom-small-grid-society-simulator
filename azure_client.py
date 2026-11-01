"""Isolated Azure GPT client. No credentials or endpoint values are logged."""
from __future__ import annotations
import json
import os
from pathlib import Path
from openai import OpenAI

class AzureClient:
    def __init__(self,env_file=None,deployment=None):
        if env_file:
            for line in Path(env_file).read_text().splitlines():
                if '=' not in line or line.lstrip().startswith('#'): continue
                key,value=line.split('=',1)
                key=key.strip().removeprefix('export ')
                if key.startswith('AZURE_'): os.environ.setdefault(key,value.strip().strip('"\''))
        base=os.getenv('AZURE_OPENAI_BASE_URL')
        key=os.getenv('AZURE_OPENAI_API_KEY') or os.getenv('AZURE_AI_FOUNDRY_API_KEY')
        self.deployment=deployment or os.getenv('PTOM_AZURE_DEPLOYMENT','gpt-6-luna')
        if not base or not key: raise RuntimeError('Azure endpoint and API key are not configured')
        self.client=OpenAI(base_url=base.rstrip('/')+'/',api_key=key,timeout=60,max_retries=0)

    def request(self,prompt,reasoning='low',max_output_tokens=300):
        settings={'model':self.deployment,'input':prompt,'reasoning':{'effort':reasoning},
                  'max_output_tokens':max_output_tokens}
        try:
            response=self.client.responses.create(**settings)
        except Exception as exc:
            raise RuntimeError(f'Azure request with reasoning={reasoning} failed: {exc}') from exc
        return {'prompt':prompt,'response':response.output_text,'model':self.deployment,
                'settings':{'reasoning':reasoning,'temperature':None,'max_output_tokens':max_output_tokens},
                'usage':response.usage.model_dump() if response.usage else None,
                'response_id':response.id,'status':response.status,'incomplete_details':response.incomplete_details.model_dump() if response.incomplete_details else None}

    def choose_action(self,observation,allowed,replay=None):
        prompt=('Act as one person in the supplied grid world. Use only the observations and allowed actions provided. '
                'Choose one action that advances your assigned task and respects the world rules. '
                'Return JSON with action, arguments, and a short reason. Do not invent observations or describe a sequence of future actions.\n'
                +json.dumps({'observation':observation,'allowed_actions':allowed},sort_keys=True))
        result=replay if replay is not None else self.request(prompt,'low',300)
        try:
            body=json.loads(result['response'])
            if not isinstance(body,dict) or 'action' not in body: raise ValueError('Missing action')
            args=body.get('arguments',{})
            if not isinstance(args,dict): raise ValueError('Arguments must be an object')
            action={'action':body['action'],'arguments':args}
            if action not in allowed: raise ValueError('Action is not allowed')
            error=None
        except (ValueError,TypeError) as exc:
            action={'action':'wait','arguments':{}}
            error=str(exc)
        return action,dict(result,validation_error=error,applied_action=action)

    def propose_rules(self,case,replay=None):
        target='LIB_MOVE' if case['case']=='library' else 'WORK_MOVE'
        role='reader' if case['case']=='library' else 'worker'
        allowed='role, task, status, needs_help' if case['case']=='library' else 'role, task, status, has_tool, work_left, urgency'
        prompt=(f'Propose exactly one behavior rule to replace {target} in the supplied case. '
                f'The ID must be ALT_{target}. The effect must be exactly {{"action":"move"}}. '
                f'Conditions must include {{"field":"role","op":"eq","value":"{role}"}} and use only these fields: {allowed}. '
                'Use operators eq, ne, gt, ge, lt, le. Each condition must have exactly field, op, value. '
                'Make the rule apply when the manual case actually moves, not when the agent is queued or finished. '
                'Return only JSON with keys rules (one item) and missing_inputs (list). '
                'The rule item must have id, description, conditions, effect. Do not change world constraints.\n'
                +json.dumps(case,sort_keys=True))
        result=replay if replay is not None else self.request(prompt,'high',2500)
        body=json.loads(result['response'])
        if not isinstance(body,dict) or not isinstance(body.get('rules'),list): raise ValueError('Response needs rules list')
        allowed_fields={'role','task','status','needs_help','has_tool','work_left','urgency','desk_open','tools_at_counter'}
        allowed_effects={'move','wait','read','serve','loan','return','work'}
        for rule in body['rules']:
            if not isinstance(rule,dict) or not {'id','description','conditions','effect'}<=rule.keys(): raise ValueError('Malformed rule')
            if not isinstance(rule['id'],str) or not rule['id'].isidentifier(): raise ValueError('Invalid rule ID')
            if not isinstance(rule['conditions'],list): raise ValueError('Conditions must be a list')
            for condition in rule['conditions']:
                if not isinstance(condition,dict) or condition.get('field') not in allowed_fields or condition.get('op') not in {'eq','ne','gt','ge','lt','le'}:
                    raise ValueError('Invalid condition')
            if not isinstance(rule['effect'],dict) or rule['effect'].get('action') not in allowed_effects: raise ValueError('Invalid effect')
            if 'weight' in rule and not (isinstance(rule['weight'],(int,float)) and 0<=rule['weight']<=10): raise ValueError('Invalid weight')
        return body,result

from copy import deepcopy

class AgentPolicy:
    def __init__(self,client=None,replay=None):
        self.client=client
        self.replay=iter(replay) if replay is not None else None
        self.logs=[]
        self.snapshot=None
        if client is None and replay is None: raise ValueError('An Azure client or replay is required')

    def choose(self,world,pid,allowed):
        state=self.snapshot or world.state()
        person=state['people'][pid]
        x,y=person['position']
        visible=[]
        for other in state['people'].values():
            ox,oy=other['position']
            if abs(ox-x)+abs(oy-y)<=1:
                visible.append({'id':other['id'],'role':other['role'],'position':other['position'],'status':other['status']})
        observation={'step':world.step,'case':world.config['case'],'self':{
            'id':pid,'role':person['role'],'position':person['position'],'task':person['task'],'status':person['status'],
            'needs_help':person['needs_help'],'has_tool':person['has_tool'],'work_left':person['work_left'],
            'workstation':person['workstation']},'places':world.places,'nearby_people':visible,
            'desk_open':state['desk_open'],'tools_at_counter':state['tools_at_counter'],
            'queue_ahead':state['queue'].index(pid) if pid in state['queue'] else None}
        if self.replay is None:
            action,log=self.client.choose_action(observation,allowed)
        else:
            saved=next(self.replay)
            if saved['step']!=world.step or saved['person']!=pid: raise ValueError('Replay does not match step and person')
            action,log=self.client.choose_action(observation,allowed,replay=saved['llm']) if self.client else self._validate_replay(saved,allowed)
        self.logs.append({'step':world.step,'person':pid,'observation':observation,'allowed':allowed,'llm':log})
        return action

    @staticmethod
    def _validate_replay(saved,allowed):
        log=deepcopy(saved['llm'])
        action=log['applied_action']
        if action not in allowed and action!={'action':'wait','arguments':{}}: raise ValueError('Replay action is no longer allowed')
        return action,log

