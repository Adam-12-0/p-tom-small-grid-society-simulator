"""Request and validate an initial behavior-rule proposal without executing it."""
from pathlib import Path
import argparse,json
from azure_client import AzureClient
from world import load_case
ROOT=Path(__file__).resolve().parent
p=argparse.ArgumentParser()
p.add_argument('case',choices=['library','workshop'])
p.add_argument('--env-file',type=Path)
p.add_argument('--output',type=Path)
a=p.parse_args()
world=load_case(ROOT/'cases'/f'{a.case}.json')
client=AzureClient(a.env_file)
body,call=client.propose_rules({'case':a.case,'places':world.config['places'],'people':world.config['people'],
                                'current_rules':world.config['rules']})
from generated_rules import validate
check=validate(ROOT/'cases'/f'{a.case}.json',body)
output=a.output or ROOT/'runs'/f'{a.case}-rule-proposal.json'
output.parent.mkdir(exist_ok=True)
output.write_text(json.dumps({'validated_rules':body,'behavior_check':check,'llm_call':call},indent=2)+'\n')
print(f'Validated {len(body["rules"])} proposal(s), saved {output}')
