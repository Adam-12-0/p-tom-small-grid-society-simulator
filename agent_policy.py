"""LLM action selection with explicit allowed choices and replay."""
from copy import deepcopy
from rules import DIRECTIONS

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

def action(name,**arguments): return {'action':name,'arguments':arguments}

def legal_moves(world,position):
    return [action('move',direction=name) for name,(dx,dy) in DIRECTIONS
            if world.valid_cell((position[0]+dx,position[1]+dy))]
