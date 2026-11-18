import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import paper_bot as b
import notion_table as t

class TableTests(unittest.TestCase):
 def paper(self):
  return b.normalize({'DOI':'10.1234/ABC','title':['Test'],'publisher':'Publisher','type':'journal-article','author':[{'given':'A','family':'One','affiliation':[{'name':'Imaging Laboratory, University X'}]},{'given':'B','family':'Two','affiliation':[{'name':'University Y'}]}],'link':[{'content-type':'application/pdf','URL':'https://example.org/paper.pdf'}]},'AI')
 def test_authors_and_explicit_group(self):
  p=self.paper()
  self.assertEqual(p['authors'],['A One','B Two'])
  self.assertEqual(p['groups'],['Imaging Laboratory, University X'])
  self.assertIn('B Two: University Y',p['author_affiliations'])
  self.assertTrue(p['collected_at'].endswith('+09:00'))
 def test_missing_does_not_invent(self):
  p=b.normalize({'DOI':'10.1/x'},'')
  row=t.row_payload(p,'s')['properties']
  self.assertNotIn('PDF',row)
  self.assertEqual(row['Corresponding author']['rich_text'][0]['text']['content'],'확인 필요')
 def test_schema_matches_payload_and_checkbox(self):
  row=t.row_payload(self.paper(),'source')
  self.assertEqual(set(row['properties']),set(t.FIELDS))
  self.assertFalse(row['properties']['Read']['checkbox'])
  self.assertEqual(row['parent']['data_source_id'],'source')
 def test_existing_read_row_untouched(self):
  with tempfile.TemporaryDirectory() as d,patch.object(b,'ROOT',Path(d)),patch.object(t,'settings',return_value={'data_source_id':'s'}),patch.object(t,'api',return_value={'results':[{'url':'https://notion.so/existing','properties':{'읽음':{'checkbox':True}}}]}) as api:
   t.publish([self.paper()],Path(d))
   self.assertEqual(api.call_count,1)
   self.assertTrue(api.call_args.args[0].endswith('/query'))
 def test_new_row_and_duplicate_recovery(self):
  with tempfile.TemporaryDirectory() as d,patch.object(b,'ROOT',Path(d)),patch.object(t,'settings',return_value={'data_source_id':'s'}),patch.object(t,'api',side_effect=[{'results':[]},{'url':'https://notion.so/new'},{'results':[{'url':'https://notion.so/new'}]}]) as api:
   t.publish([self.paper()],Path(d));t.publish([self.paper()],Path(d))
   self.assertEqual(sum(c.args[0]=='pages' for c in api.call_args_list),1)

if __name__=='__main__':unittest.main()
