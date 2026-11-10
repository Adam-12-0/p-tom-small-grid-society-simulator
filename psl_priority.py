"""Genuine PSL inference for workshop loan priority."""
from pslpython.model import Model
from pslpython.partition import Partition
from pslpython.predicate import Predicate
from pslpython.rule import Rule

RULE_TEXT={
 'urgency':'3: Waiting(W) & Urgency(W) -> Priority(W) ^2',
 'low_default':'1: !Priority(W) ^2',
}

def priority_scores(world,waiting):
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

if __name__=='__main__':
    from world import load_case
    from pathlib import Path
    w=load_case(Path(__file__).parent/'cases/workshop.json')
    print(priority_scores(w,['W1','W2']))
