import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import paper_bot as b
import notion_table as t
import migrate_table as m

class MigrationTests(unittest.TestCase):
 def old(self):
  inverse={v:k for k,v in m.RENAMES.items()}
  props={inverse.get(k,k):{'id':'id'+str(i),'type':v} for i,(k,v) in enumerate(t.FIELDS.items()) if k!='Corresponding author'}
  props['PDF']={'id':'pdfid','type':'url'}
  props['읽음']['id']='checkbox-id';props['논문']['id']='title'
  props['수집일시']['id']='collected-id'
  return props
 def test_rename_preserves_ids_and_collection(self):
  changes=m.plan(self.old())
  self.assertEqual(changes['checkbox-id'],{'name':'Read'})
  self.assertEqual(changes['title'],{'name':'Paper'})
  self.assertNotIn('collected-id',changes)
  self.assertIsNone(changes['pdfid'])
  self.assertIn('Corresponding author',changes)
 def test_idempotent_and_custom_columns_preserved(self):
  props={k:{'id':k,'type':v} for k,v in t.FIELDS.items()}
  props['My Notes']={'id':'custom','type':'rich_text'}
  self.assertEqual(m.plan(props),{})
 def test_collision_stops(self):
  props=self.old();props['Read']={'id':'other','type':'checkbox'}
  with self.assertRaises(ValueError):m.plan(props)
 def test_summary_inside_page_not_table(self):
  p=b.normalize({'DOI':'10.1/test','title':['Paper'],'author':[{'given':'Last','family':'Author'}]},'AI')
  p.update(basis='초록 기반 AI 분석 / 전문 미확인',analysis='요약 내용')
  row=t.row_payload(p,'source')
  self.assertEqual(set(row['properties']),set(t.FIELDS))
  self.assertEqual(row['properties']['Corresponding author']['rich_text'][0]['text']['content'],'확인 필요')
  self.assertEqual(row['children'][-1]['type'],'toggle')
  self.assertNotIn('분석 상태',row['properties'])
 def test_backup_precedes_remote_mutation(self):
  with tempfile.TemporaryDirectory() as d,patch.object(b,'ROOT',Path(d)),patch.object(m,'preserve_row'),patch.object(m,'ordered_view'):
   config={'data_source_id':'s','database_id':'db'}
   old=self.old();final={k:{'id':k,'type':v} for k,v in t.FIELDS.items()}
   def api(path,data=None,method=None):
    if path.endswith('/query'):return {'results':[{'id':'p','properties':{'Read':{'checkbox':True}}}]}
    if method=='PATCH':
     files=list((Path(d)/'output'/'schema-backups').glob('*.json'))
     self.assertEqual(len(files),1)
     self.assertTrue(json.loads(files[0].read_text())['rows'][0]['properties']['Read']['checkbox'])
     return {}
    if api.first:api.first=False;return {'properties':old}
    return {'properties':final}
   api.first=True
   with patch.object(t,'api',side_effect=api):m.migrate(config)

if __name__=='__main__':unittest.main()
