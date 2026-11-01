"""Run or resume a case, saving every committed step."""
import argparse
from datetime import datetime,timezone
from pathlib import Path
import json
from world import load_case,restore_case
from simulation import run
from rules import RULE_SPECS,priority_scores,validate_generated_rule

ROOT=Path(__file__).resolve().parent

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('case',nargs='?',help='JSON case path or bundled case name')
    parser.add_argument('--display',choices=['print','interactive','delay','quiet'],default='print')
    parser.add_argument('--delay',type=float,default=0.5)
    parser.add_argument('--policy',choices=['manual','psl','azure'])
    parser.add_argument('--propose-rules',action='store_true',help='Request and check one Azure behavior rule')
    parser.add_argument('--env-file',type=Path,help='Existing Azure env file, kept outside this project')
    parser.add_argument('--replay',type=Path,help='Replay saved Azure decisions without API calls')
    parser.add_argument('--resume',type=Path,help='Resume from the last committed step in a saved trace')
    parser.add_argument('--step-limit',type=int,help='Override case step limit for a bounded smoke run')
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    if not args.case and not args.resume: parser.error('case or --resume is required')
    previous=json.loads(args.resume.read_text()) if args.resume else None
    if previous:
        path=Path(previous['case_file'])
        if not path.is_absolute(): path=ROOT/path
        world=restore_case(path,previous['configuration'],previous['trace'][-1]['after'])
        if args.case: parser.error('Do not pass a case when resuming')
        if args.step_limit is not None:
            if args.step_limit<world.step: parser.error('New limit cannot precede the checkpoint')
            world.config['step_limit']=args.step_limit
    else:
        path=Path(args.case)
        if not path.exists(): path=ROOT/'cases'/f'{args.case}.json'
        world=load_case(path)
        if args.policy: world.config['policy']=args.policy
        if args.step_limit is not None:
            if args.step_limit<0: parser.error('step limit must be nonnegative')
            world.config['step_limit']=args.step_limit
    if args.propose_rules:
        if previous: parser.error('Cannot propose rules while resuming a run')
        if world.config['case'] not in ('library','workshop'): parser.error('Unknown case')
        from azure_client import AzureClient
        client=AzureClient(args.env_file)
        case={'case':world.config['case'],'places':world.config['places'],
              'people':world.config['people'],'current_rules':world.config['rules']}
        body,call=client.propose_rules(case)
        check=validate_generated_rule(path,body)
        output=args.output or ROOT/'runs'/f"{path.stem}-rule-proposal.json"
        output.parent.mkdir(parents=True,exist_ok=True)
        output.write_text(json.dumps({'validated_rules':body,'behavior_check':check,'llm_call':call},indent=2)+'\n')
        print(f'Validated {len(body["rules"])} proposal(s), saved {output}')
        return
    output=args.output or args.resume or ROOT/'runs'/f"{path.stem}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    output.parent.mkdir(parents=True,exist_ok=True)
    priority=None
    agent=None
    if world.config['policy']=='psl':
        if world.config['case']!='workshop': parser.error('PSL priority policy requires workshop')
        priority=priority_scores
    if world.config['policy']=='azure':
        from azure_client import AgentPolicy
        if args.replay:
            saved=json.loads(args.replay.read_text())
            calls=[call for record in saved['trace'] for call in record.get('llm_calls',[])]
            agent=AgentPolicy(replay=calls)
        else:
            from azure_client import AzureClient
            agent=AgentPolicy(client=AzureClient(args.env_file))
    def save(trace):
        try: case_file=str(path.resolve().relative_to(ROOT))
        except ValueError: case_file=str(path.resolve())
        result={'case_file':case_file,'configuration':world.config,'rules':RULE_SPECS,
                'trace':trace,'result':{'goal':trace[-1]['goal'],'steps':trace[-1]['step'],
                'people':trace[-1]['after']['people']}}
        temporary=output.with_suffix(output.suffix+'.tmp')
        temporary.write_text(json.dumps(result,indent=2)+'\n')
        temporary.replace(output)
    try:
        trace=run(world,mode=args.display,delay=args.delay,priority_fn=priority,agent=agent,
                  initial_trace=previous['trace'] if previous else None,on_commit=save)
    except Exception as exc:
        parser.exit(1,f'Run stopped: {exc}\nLast committed step is saved in {output}. Resume with --resume {output}.\n')
    save(trace)
    print(f"Saved {output}\nGoal: {'reached' if trace[-1]['goal'] else 'not reached'} at step {trace[-1]['step']}")
if __name__=='__main__': main()
