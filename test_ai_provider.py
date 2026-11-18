import os
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
import ai_provider as p
import ai_tools as a
import paper_bot as b

class ProviderTests(unittest.TestCase):
 def test_gemini_routing_and_response(self):
  with patch.dict(os.environ,{'AI_PROVIDER':'gemini','GEMINI_API_KEY':'test','GEMINI_MODEL':'gemini-2.5-flash'},clear=True),patch.object(b,'request_json',return_value={'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':'숨김','thought':True},{'text':'요약'}]}}]}) as call:
   self.assertTrue(p.ready());self.assertEqual(p.generate('rules','abstract'),'요약')
   self.assertIn('generativelanguage.googleapis.com',call.call_args.args[0])
   self.assertNotIn('test',call.call_args.args[0])
   self.assertEqual(call.call_args.args[2],{'x-goog-api-key':'test'})
 def test_no_paid_fallback(self):
  with patch.dict(os.environ,{'AI_PROVIDER':'gemini','GEMINI_API_KEY':'test','GEMINI_MODEL':'test-model','OPENAI_API_KEY':'other'},clear=True),patch.object(b,'request_json',side_effect=RuntimeError('HTTP 429')) as call:
   with self.assertRaises(RuntimeError):p.generate('rules','abstract')
   self.assertEqual(call.call_count,1)
 def test_incomplete_rejected(self):
  with patch.dict(os.environ,{'AI_PROVIDER':'gemini','GEMINI_API_KEY':'test','GEMINI_MODEL':'test-model'},clear=True),patch.object(b,'request_json',return_value={'candidates':[{'finishReason':'MAX_TOKENS','content':{'parts':[{'text':'partial'}]}}]}):
   with self.assertRaises(RuntimeError):p.generate('rules','abstract')
 def test_setup_preserves_other_keys(self):
  with tempfile.TemporaryDirectory() as d,patch.object(b,'ROOT',Path(d)),patch.dict(os.environ,{},clear=True):
   path=Path(d)/'.env';path.write_text('OPENAI_API_KEY=keep\nNOTION_TOKEN=keep\nAI_PROVIDER=openai\nGEMINI_API_KEY=old\n')
   a.write_ai_env('new','gemini-2.5-flash','gemini')
   content=path.read_text()
   self.assertIn('OPENAI_API_KEY=keep',content);self.assertIn('NOTION_TOKEN=keep',content)
   self.assertEqual(content.count('AI_PROVIDER='),1);self.assertEqual(content.count('GEMINI_API_KEY='),1)
 def test_legacy_openai_works(self):
  with patch.dict(os.environ,{'OPENAI_API_KEY':'test','OPENAI_MODEL':'model'},clear=True),patch.object(b,'request_json',return_value={'status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':'OK'}]}]}):
   self.assertEqual(p.provider(),'openai');self.assertEqual(p.generate('rules','test'),'OK')

if __name__=='__main__':unittest.main()
