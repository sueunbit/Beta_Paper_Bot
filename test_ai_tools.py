import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
import ai_tools as a
import paper_bot as b
import notion_runner as r
from runtime_lock import single_writer

class AITests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory()
  self.root=Path(self.temp.name)
  self.patcher=patch.object(b,'ROOT',self.root);self.patcher.start()
  self.env=patch.dict(os.environ,{'OPENAI_API_KEY':'test','OPENAI_MODEL':'test-model'});self.env.start()
  self.db=sqlite3.connect(':memory:');self.db.execute('CREATE TABLE ai_jobs (page TEXT PRIMARY KEY,state TEXT)')
  self.row={'id':'page1','properties':{'DOI':{'rich_text':[{'plain_text':'10.1234/test'}]},'읽음':{'checkbox':True},'수집일시':{'date':{'start':'2020-01-01'}}}}
  self.work={'DOI':'10.1234/test','title':['Title'],'publisher':'Publisher','type':'journal-article','abstract':'A study with a result.'}
 def tearDown(self):
  self.db.close();self.env.stop();self.patcher.stop();self.temp.cleanup()
 def test_save_preserves_notion_config(self):
  (self.root/'.env').write_text('NOTION_TOKEN=local\nOPENAI_MODEL=old\n')
  a.write_ai_env('new','model')
  text=(self.root/'.env').read_text()
  self.assertIn('NOTION_TOKEN=local',text);self.assertNotIn('OPENAI_MODEL=old',text)
 def test_status_is_local_and_never_overwrites_properties(self):
  with patch.object(a.table,'api') as api:
   a.status('page1','ok')
   api.assert_not_called()
  with sqlite3.connect(self.root/'state.sqlite3') as db:
   self.assertEqual(db.execute('SELECT value FROM analysis_states WHERE page=?',('page1',)).fetchone()[0],'ok')
 def test_success_and_rerun_no_generation(self):
  with patch.object(a,'summary_exists',side_effect=[False,True]),patch.object(b,'request_json',return_value={'message':self.work}),patch.object(b,'analyze',return_value=('한국어 요약',a.COMPLETE)) as model,patch.object(a.table,'api',return_value={'results':[]}) as api:
   self.assertEqual(a.summarize_one(self.row,{},self.db),'요약 추가 완료')
   self.assertEqual(a.summarize_one(self.row,{},self.db),'기존 요약 유지')
  self.assertEqual(model.call_count,1)
  self.assertEqual(sum('blocks/' in c.args[0] for c in api.call_args_list),1)
  for c in api.call_args_list:
   if c.args[0].startswith('pages/'):
    self.assertEqual(set(c.args[1]['properties']),{'분석 상태'})
 def test_missing_abstract_no_charge(self):
  work={**self.work,'abstract':''}
  with patch.object(a,'summary_exists',return_value=False),patch.object(b,'request_json',return_value={'message':work}),patch.object(b,'analyze',return_value=('전문과 초록 없음','메타데이터만 확보')) as model,patch.object(a.table,'api',return_value={}):
   self.assertEqual(a.summarize_one(self.row,{},self.db),a.NO_ABSTRACT)
   model.assert_called_once()
 def test_model_failure_retryable(self):
  with patch.object(a,'summary_exists',return_value=False),patch.object(b,'request_json',return_value={'message':self.work}),patch.object(b,'analyze',side_effect=RuntimeError('HTTP 429')),patch.object(a.table,'api',return_value={}):
   self.assertIn('요약 실패',a.summarize_one(self.row,{},self.db))
  self.assertEqual(self.db.execute('SELECT state FROM ai_jobs').fetchone()[0],'failed')
 def test_ambiguous_append_is_not_repeated(self):
  def api(path,*args,**kwargs):
   if path.startswith('blocks/'):raise RuntimeError('timeout')
   return {}
  with patch.object(a,'summary_exists',return_value=False),patch.object(b,'request_json',return_value={'message':self.work}),patch.object(b,'analyze',return_value=('summary',a.COMPLETE)) as model,patch.object(a.table,'api',side_effect=api):
   with self.assertRaises(RuntimeError):a.summarize_one(self.row,{},self.db)
   self.assertIn('자동 재전송 보류',a.summarize_one(self.row,{},self.db))
   self.assertEqual(model.call_count,1)
 def test_budget_caps_model_calls(self):
  p=b.normalize(self.work,'AI');q={**p,'doi':'10.1234/second'}
  with patch.object(r,'credentials',return_value=('t','p')),patch.object(r,'known_dois',return_value=set()),patch.object(b,'search',return_value=[p,q]),patch.object(b,'analyze',return_value=('summary',a.COMPLETE)) as model,patch.object(b,'publish',return_value=[{'status':'posted'}]):
   budget={'remaining':1};r.cycle({'max_papers':2},float('inf'),False,budget)
   self.assertEqual(model.call_count,1);self.assertEqual(budget['remaining'],0)
 def test_lock_releases(self):
  with single_writer():
   with self.assertRaises(RuntimeError):
    with single_writer():pass
  with single_writer():pass
 def test_patch_http_method(self):
  class Response:
   def __enter__(self):return self
   def __exit__(self,*args):pass
   def read(self):return b'{}'
  with patch.object(b.urllib.request,'urlopen',return_value=Response()) as call:
   b.request_json('https://example.org',{'x':1},method='PATCH')
   self.assertEqual(call.call_args.args[0].method,'PATCH')

if __name__=='__main__':unittest.main()
