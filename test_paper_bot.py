import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import paper_bot as bot

class DemoTests(unittest.TestCase):
    def setUp(self):
        self.samples = json.loads((bot.ROOT/'sample.json').read_text(encoding='utf-8'))
        self.config = json.loads((bot.ROOT/'config.example.json').read_text(encoding='utf-8'))

    def test_mdpi_signals_independently(self):
        for field, value in [('publisher','Multidisciplinary Digital Publishing Institute'),
                             ('doi','https://doi.org/10.3390/test'), ('url','https://www.mdpi.com/test')]:
            p=copy.deepcopy(self.samples[0]); p[field]=value
            self.assertEqual(bot.exclusion(p,[]),'MDPI 제외')

    def test_filter_duplicates_unknown_and_limit(self):
        kept,audit=bot.select(self.samples,self.config)
        self.assertEqual(len(kept),1)
        self.assertEqual({x['reason'] for x in audit},{'MDPI 제외','DOI 중복','출판사 확인 필요: 보류'})

    def test_abstract_missing_never_calls_ai(self):
        with patch.object(bot,'request_json',side_effect=AssertionError('must not call')):
            text,basis=bot.analyze(self.samples[0],self.config)
        self.assertEqual(basis,'AI 분석 미실행')

    def test_html_escapes_remote_text(self):
        p=copy.deepcopy(self.samples[0]);p.update(title='<script>alert(1)</script>',analysis='<img onerror=x>',basis='test')
        with tempfile.TemporaryDirectory() as d:
            f=bot.save_report([p],[],self.config,Path(d),False)
            text=f.read_text(encoding='utf-8')
            self.assertNotIn('<script>',text)
            self.assertIn('&lt;script&gt;',text)

    def test_notion_dedup_and_uncertain_write(self):
        p=copy.deepcopy(self.samples[0]);p.update(analysis='test',basis='초록')
        with tempfile.TemporaryDirectory() as d, patch.object(bot,'ROOT',Path(d)), patch.dict(bot.os.environ,{'NOTION_TOKEN':'test','NOTION_PARENT_PAGE_ID':'a'*32}):
            with patch.object(bot,'request_json',return_value={'url':'https://notion.so/test'}) as call:
                bot.publish([p],Path(d));bot.publish([p],Path(d))
                self.assertEqual(call.call_count,1)
            p['doi']='10.0000/other'
            with patch.object(bot,'request_json',side_effect=RuntimeError('timeout')) as call:
                with self.assertRaises(RuntimeError):bot.publish([p],Path(d))
                result=bot.publish([p],Path(d))
                self.assertEqual(call.call_count,1)
                self.assertIn('pending',result[0]['status'])

    def test_crossref_query_and_normalization(self):
        response={'message':{'items':[{'DOI':'10.1234/ABC','title':['A'], 'publisher':'P','type':'journal-article','abstract':'<jats:p>Some &amp; text</jats:p>'}]}}
        with patch.object(bot,'request_json',return_value=response) as call:
            papers=bot.search(self.config)
        self.assertEqual(len(papers),len(self.config['keywords']))
        self.assertEqual(papers[0]['doi'],'10.1234/abc')
        self.assertEqual(papers[0]['abstract'],'Some & text')
        self.assertIn('from-pub-date',call.call_args.args[0])

if __name__=='__main__':unittest.main()
