import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import notion_runner as r

class RunnerTests(unittest.TestCase):
    def test_link_parsing(self):
        self.assertEqual(r.page_id('https://www.notion.so/Papers-'+'a'*32+'?pvs=4'),'a'*32)
        self.assertEqual(r.page_id('12345678-1234-1234-1234-123456789abc'),'12345678123412341234123456789abc')
        with self.assertRaises(ValueError): r.page_id('https://notion.so/not-a-page')

    def test_duration_and_interval(self):
        now=[0.0];starts=[]
        def wait(t):now[0]+=t
        r.run_for(3,1,lambda deadline:starts.append(now[0]),clock=lambda:now[0],sleeper=wait)
        self.assertEqual(starts,[0,60,120])
        self.assertEqual(now[0],180)
        with self.assertRaises(ValueError):r.run_for(float('nan'),1,lambda _:None)

    def test_long_task_stops_without_second_cycle(self):
        now=[0.0];calls=[]
        def task(deadline):calls.append(deadline);now[0]=100
        r.run_for(1,1,task,clock=lambda:now[0],sleeper=lambda _:None)
        self.assertEqual(len(calls),1)

    def test_existing_env_preserved(self):
        with tempfile.TemporaryDirectory() as d,patch.object(r.bot,'ROOT',Path(d)),patch.dict(os.environ,{},clear=True):
            (Path(d)/'.env').write_text('OPENAI_MODEL=test\nNOTION_TOKEN=old\n',encoding='utf-8')
            r.save_credentials('new','a'*32)
            saved=(Path(d)/'.env').read_text()
            self.assertIn('OPENAI_MODEL=test',saved)
            self.assertEqual(saved.count('NOTION_TOKEN='),1)

    def test_skip_posted_before_limit(self):
        root=r.bot.ROOT
        p=json.loads((root/'sample.json').read_text(encoding='utf-8'))[0]
        q=copy.deepcopy(p);q['doi']='10.1234/new'
        config={'max_papers':1,'exclude_keywords':[]}
        with tempfile.TemporaryDirectory() as d,patch.object(r.bot,'ROOT',Path(d)),patch.object(r,'credentials',return_value=('t','a'*32)),patch.object(r,'known_dois',return_value={r.bot.doi_key(p['doi'])}),patch.object(r.bot,'search',return_value=[p,q]),patch.object(r.bot,'publish',return_value=[{'status':'posted'}]) as pub,patch.object(r.bot,'analyze',side_effect=AssertionError('AI must not run')):
            r.cycle(config,float('inf'),True)
            self.assertEqual(pub.call_args.args[0][0]['doi'],'10.1234/new')
            self.assertIn('미실행',pub.call_args.args[0][0]['basis'])

if __name__=='__main__':unittest.main()
