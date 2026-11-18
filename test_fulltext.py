import base64
import os
import unittest
from unittest.mock import patch
import ai_provider as provider
import paper_bot as bot
import fulltext as f
import cleanup_pages as cleanup

class FulltextTests(unittest.TestCase):
    def setUp(self):
        self.env=patch.dict(os.environ,{'AI_PROVIDER':'gemini','GEMINI_API_KEY':'test','GEMINI_MODEL':'test','UNPAYWALL_EMAIL':''});self.env.start()
        self.paper={'title':'Research','doi':'10.1234/test','abstract':'Abstract','fulltext_evidence':{'url':'https://example.org/p.pdf','license':'cc-by'}}
    def tearDown(self):self.env.stop()
    def test_license_allowlist(self):
        for v in ('cc-by','cc0','https://creativecommons.org/licenses/by/4.0/'):
            self.assertTrue(f.allowed_license(v))
        for v in ('cc-by-nc','cc-by-nd','public','', 'https://evil.org/licenses/by/4.0'):
            self.assertFalse(f.allowed_license(v))
    def test_license_must_match_version_and_date(self):
        p={'fulltext_links':[{'URL':'https://example.org/p.pdf','content-type':'application/pdf','content-version':'vor'}],
           'licenses':[{'URL':'https://creativecommons.org/licenses/by/4.0/','content-version':'vor','start':{'date-parts':[[2020,1,1]]}}]}
        self.assertEqual(len(list(f.candidates(p))),1)
        p['licenses'][0]['content-version']='am';self.assertEqual(list(f.candidates(p)),[])
        p['licenses'][0]['content-version']='vor';p['licenses'][0]['start']['date-parts']=[[2099,1,1]]
        self.assertEqual(list(f.candidates(p)),[])
    def test_unpaywall_requires_license(self):
        with patch.dict(os.environ,{'UNPAYWALL_EMAIL':'user@example.org'}),patch.object(bot,'request_json',return_value={'oa_locations':[{'license':'cc-by','url_for_pdf':'https://example.org/a.pdf'},{'url_for_pdf':'https://example.org/b.pdf'}]}):
            self.assertEqual(len(list(f.candidates(self.paper))),1)
    def test_private_addresses_rejected(self):
        with patch.object(f.socket,'getaddrinfo',return_value=[(2,1,6,'',('127.0.0.1',443))]):
            with self.assertRaises(ValueError):f.validate_url('https://example.org/p.pdf')
        with self.assertRaises(ValueError):f.validate_url('http://example.org/p.pdf')
    def test_html_is_not_pdf(self):
        class Response:
            headers={}
            def __enter__(self):return self
            def __exit__(self,*a):pass
            def read(self,*a):return b'<html>login</html>'
        with patch.object(f,'validate_url'),patch.object(f.urllib.request,'build_opener') as opener:
            opener.return_value.open.return_value=Response()
            with self.assertRaises(ValueError):f.download('https://example.org/p.pdf')
    def test_full_pdf_without_abstract(self):
        self.paper['abstract']=''
        with patch.object(f,'acquire',return_value=(b'%PDF-test','')),patch.object(provider,'generate',return_value='[원문] 결과') as call:
            text,basis=bot.analyze(self.paper,{})
        self.assertEqual(basis,f.COMPLETE);self.assertEqual(call.call_args.kwargs['pdf_bytes'],b'%PDF-test')
        self.assertIn('cc-by',text)
    def test_download_failure_falls_back(self):
        with patch.object(f,'acquire',return_value=(None,'접근 실패')),patch.object(provider,'generate',return_value='초록 요약') as call:
            text,basis=bot.analyze(self.paper,{})
        self.assertIn('전문 미확인',basis);self.assertIn('접근 실패',text);self.assertNotIn('pdf_bytes',call.call_args.kwargs)
    def test_no_material_no_model_call(self):
        self.paper['abstract']=''
        with patch.object(f,'acquire',return_value=(None,'없음')),patch.object(provider,'generate') as call:
            _,basis=bot.analyze(self.paper,{})
        self.assertEqual(basis,'메타데이터만 확보');call.assert_not_called()
    def test_upgrade_preserves_existing_abstract_without_charge(self):
        with patch.object(f,'acquire',return_value=(None,'없음')),patch.object(provider,'generate') as call:
            _,basis=bot.analyze(self.paper,{'keep_existing_abstract':True})
        self.assertEqual(basis,'기존 초록 유지');call.assert_not_called()
    def test_unusable_pdf_budget_and_fallback(self):
        for available,expected in ((0,1),(1,2)):
            with patch.object(f,'acquire',return_value=(b'%PDF-test','')),patch.object(provider,'generate',side_effect=['PDF_UNUSABLE','초록 요약']) as call:
                budget={'remaining':available};_,basis=bot.analyze(self.paper,{'_fallback_budget':budget})
            self.assertEqual(call.call_count,expected);self.assertEqual(budget['remaining'],0)
            self.assertEqual(basis,'PDF 분석 보류' if available==0 else '초록 기반 AI 분석 / 전문 미확인')
    def test_native_pdf_request(self):
        with patch.object(bot,'request_json',return_value={'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':'summary'}]}}]}) as call:
            provider.generate('system','paper',pdf_bytes=b'%PDF-test')
        inline=call.call_args.args[1]['contents'][0]['parts'][1]['inlineData']
        self.assertEqual(inline['mimeType'],'application/pdf');self.assertEqual(base64.b64decode(inline['data']),b'%PDF-test')
    def test_cleanup_across_spans_and_preserves_notes(self):
        phrase=cleanup.PHRASES[0]
        spans=[{'type':'text','text':{'content':'내 메모 '+phrase[:15]},'annotations':{'bold':True}}, {'type':'text','text':{'content':phrase[15:]+' 보존'}}]
        result=cleanup.cleaned_rich_text(spans)
        self.assertEqual(''.join(x['text']['content'] for x in result),'내 메모  보존')
        self.assertTrue(result[0]['annotations']['bold']);self.assertIsNone(cleanup.cleaned_rich_text(result))

if __name__=='__main__':unittest.main()
