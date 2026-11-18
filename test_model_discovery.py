import io
import unittest
from unittest.mock import patch
import urllib.error
import ai_provider as a
import paper_bot as b

class DiscoveryTests(unittest.TestCase):
 def test_pagination_and_filter(self):
  def model(name,methods=['generateContent']):return {'name':'models/'+name,'supportedGenerationMethods':methods}
  with patch.object(b,'request_json',side_effect=[{'models':[model('gemini-text'),model('gemini-image'),model('gemini-embed',['embedContent'])],'nextPageToken':'next/page'},{'models':[model('gemini-other')]}]) as call:
   self.assertEqual(a.list_gemini_models('secret'),['gemini-other','gemini-text'])
   self.assertIn('pageToken=next%2Fpage',call.call_args.args[0])
 def test_api_error_detail_redacted(self):
  error=urllib.error.HTTPError('https://example.org',404,'Not Found',{},io.BytesIO(b'{"error":{"message":"Model absent, key SECRET"}}'))
  with patch.object(b.urllib.request,'urlopen',side_effect=error):
   with self.assertRaises(RuntimeError) as ctx:b.request_json('https://example.org',headers={'x-goog-api-key':'SECRET'})
  self.assertIn('Model absent',str(ctx.exception));self.assertNotIn('SECRET',str(ctx.exception))

if __name__=='__main__':unittest.main()
