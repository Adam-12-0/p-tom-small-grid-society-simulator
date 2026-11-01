import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from world import load_case,restore_case
from simulation import run
from rules import next_move
from display import export_runs

ROOT=Path(__file__).resolve().parents[1]

class SimulatorTests(unittest.TestCase):
    def case(self,name): return load_case(ROOT/'cases'/f'{name}.json')
    def test_library_timing_and_closure(self):
        open_world=self.case('library');closed_world=self.case('library_closed')
        open_trace=run(open_world,mode='quiet');closed_trace=run(closed_world,mode='quiet')
        self.assertEqual([open_world.people[p].served_step for p in ('R1','R2')],[7,8])
        self.assertEqual([closed_world.people[p].served_step for p in ('R1','R2')],[9,10])
        self.assertEqual([open_world.people[p].arrival_step for p in ('R1','R2')],[6,6])
        self.assertTrue(open_trace[-1]['goal'] and closed_trace[-1]['goal'])
        self.assertEqual(next_move(self.case('library'),(0,4),(2,0)),('up',(0,3)))
    def test_workshop_inventory_and_comparison(self):
        one=self.case('workshop');two=self.case('workshop_two_drills')
        t1=run(one,mode='quiet');t2=run(two,mode='quiet')
        self.assertEqual((t1[-1]['step'],t2[-1]['step']),(38,23))
        for world,trace in [(one,t1),(two,t2)]:
            self.assertTrue(trace[-1]['goal'])
            for record in trace:
                state=record['after']
                self.assertEqual(state['tools_at_counter']+sum(p['has_tool'] for p in state['people'].values()),world.tool_count)
                self.assertLessEqual(sum(a['action'] in ('loan drill','accept return') for a in record['actions']),1)
                ids=[a['person'] for a in record['chosen_actions']]
                self.assertEqual(len(ids),len(set(ids)))
                for action in record['actions']:
                    if action['action']=='loan drill':
                        self.assertLess(record['before']['people'][action['partner']]['arrival_step'],record['step'])
    def test_readable_observation_export(self):
        world=self.case('library')
        trace=run(world,mode='quiet')
        with tempfile.TemporaryDirectory() as temp:
            source=Path(temp)/'library.json'
            source.write_text(json.dumps({'configuration':world.config,'trace':trace}))
            text_path,tsv_path=export_runs([source])
            rendered=text_path.read_text()
            self.assertIn('step 0 / 12',rendered)
            self.assertIn('step 8 / 12',rendered)
            self.assertIn('R1 served_step: None -> 7',rendered)
            self.assertEqual(len(tsv_path.read_text().splitlines()),1+9*4)
    def test_resume_from_committed_step(self):
        first=self.case('library')
        first.config['step_limit']=3
        partial=run(first,mode='quiet')
        resumed=restore_case(ROOT/'cases/library.json',first.config,partial[-1]['after'])
        resumed.config['step_limit']=12
        complete=run(resumed,mode='quiet',initial_trace=partial)
        self.assertTrue(complete[-1]['goal'])
        self.assertEqual(complete[-1]['step'],8)
        self.assertEqual([r['step'] for r in complete],list(range(9)))
    def test_scheduled_tool_addition(self):
        world=self.case('workshop')
        world.config['scheduled_changes']=[{'step':10,'field':'add_tools','value':1}]
        trace=run(world,mode='quiet')
        self.assertEqual(trace[9]['after']['tool_count'],1)
        self.assertEqual(trace[10]['after']['tool_count'],2)
        self.assertTrue(trace[-1]['goal'])
        self.assertEqual(trace[-1]['after']['tools_at_counter'],2)
    def test_invalid_cases(self):
        data=json.loads((ROOT/'cases/library.json').read_text())
        for mutation,expected in [
            (lambda d:d.pop('people'),'Missing case fields'),
            (lambda d:d['people'][1].update(position=[6,4]),'Invalid position'),
            (lambda d:d['people'][1].pop('id'),'Person missing fields')]:
            item=json.loads(json.dumps(data));mutation(item)
            with tempfile.TemporaryDirectory() as temp:
                path=Path(temp)/'bad.json';path.write_text(json.dumps(item))
                with self.assertRaisesRegex(ValueError,expected): load_case(path)

if __name__=='__main__': unittest.main()
