import json
import sys
import unittest
from types import SimpleNamespace
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from azure_client import AzureClient
from azure_client import AgentPolicy
from world import load_case
from simulation import run
from rules import validate_generated_rule
ROOT=Path(__file__).resolve().parents[1]

class FakeClient:
    def choose_action(self,observation,allowed):
        desired=next((a for a in allowed if a['action']=='move' and a['arguments']=={'direction':'up'}),allowed[0])
        return desired,{'response':json.dumps(desired),'applied_action':desired,'validation_error':None,
                        'settings':{'reasoning':'low','temperature':None}}

class AgentTests(unittest.TestCase):
    def test_live_policy_interface_and_snapshot(self):
        world=load_case(ROOT/'cases/library.json');world.config['step_limit']=1
        policy=AgentPolicy(client=FakeClient())
        trace=run(world,mode='quiet',agent=policy)
        self.assertEqual(len(trace[1]['llm_calls']),3)
        self.assertEqual(world.people['R1'].position,(0,3))
        self.assertEqual(world.people['R2'].position,(4,3))
        self.assertEqual(trace[1]['llm_calls'][0]['observation']['step'],1)
    def test_azure_request_omits_unsupported_temperature(self):
        class Responses:
            def create(self,**kwargs):
                self.sent=kwargs
                return SimpleNamespace(output_text='OK',usage=None,id='test',status='completed',incomplete_details=None)
        responses=Responses()
        client=AzureClient.__new__(AzureClient)
        client.deployment='gpt-6-luna'
        client.client=SimpleNamespace(responses=responses)
        result=client.request('Check settings',reasoning='high',max_output_tokens=120)
        self.assertNotIn('temperature',responses.sent)
        self.assertEqual(responses.sent['reasoning'],{'effort':'high'})
        self.assertIsNone(result['settings']['temperature'])
    def test_invalid_model_choice_becomes_wait(self):
        client=AzureClient.__new__(AzureClient)
        allowed=[{'action':'move','arguments':{'direction':'up'}},{'action':'wait','arguments':{}}]
        action,log=client.choose_action({},allowed,replay={'response':'{"action":"teleport","arguments":{}}'})
        self.assertEqual(action,{'action':'wait','arguments':{}})
        self.assertIn('not allowed',log['validation_error'])
    def test_generated_rule_matches_reference(self):
        body={'rules':[{'id':'ALT_WORK_MOVE','description':'Move workers toward counter',
            'conditions':[{'field':'role','op':'eq','value':'worker'},
                          {'field':'status','op':'eq','value':'moving'}],
            'effect':{'action':'move'}}]}
        report=validate_generated_rule(ROOT/'cases/workshop.json',body)
        self.assertEqual(report['matched_actions'],12)
        body['rules'][0]['conditions'].append({'field':'desk_open','op':'eq','value':True})
        with self.assertRaisesRegex(ValueError,'not allowed'): validate_generated_rule(ROOT/'cases/workshop.json',body)

if __name__=='__main__': unittest.main()
