import unittest
from unittest.mock import patch
from urllib.parse import urlsplit
import web_app

class PlaybackSessionChecks(unittest.TestCase):
    def setUp(self):
        self.client=web_app.app.test_client()

    def test_session_keeps_its_original_cdn_when_another_worker_resolves_a_new_one(self):
        original={'stream_url':'https://one.example.com/live.m3u8?token=first','iframe_url':'https://tvf90.com/5.php?stream=espn'}
        replacement={'stream_url':'https://two.example.com/live.m3u8?token=second','iframe_url':original['iframe_url']}
        with patch.object(web_app,'resolve_tarjetarojatv_stream',side_effect=[original,replacement]) as resolver:
            first=self.client.get('/api/playback/espn')
            second=self.client.get('/api/playback/espn')
            self.assertEqual(first.status_code,200)
            pinned=first.json['url']
            self.assertEqual(urlsplit(pinned).path,'/stream/live/espn/sub.m3u8')
            with web_app.app.test_request_context(pinned):
                target,ref=web_app.verified_target('espn')
            self.assertEqual(target,original['stream_url']);self.assertEqual(ref,original['iframe_url'])
            self.assertNotEqual(pinned,second.json['url'])
            self.assertEqual(resolver.call_count,2)
            self.assertEqual(first.headers['Cache-Control'],'no-store')

    def test_refresh_clears_only_the_selected_channel_cache(self):
        with patch.dict(web_app.STREAM_RESOLVER_CACHE,{'espn':{'old':True},'espn2':{'other':True}},clear=True):
            with patch.object(web_app,'resolve_tarjetarojatv_stream',return_value={'stream_url':'https://one.example.com/live.m3u8'}):
                self.assertEqual(self.client.get('/api/playback/espn?refresh=1').status_code,200)
            self.assertNotIn('espn',web_app.STREAM_RESOLVER_CACHE)
            self.assertIn('espn2',web_app.STREAM_RESOLVER_CACHE)

    def test_invalid_channel_and_unavailable_source_do_not_issue_a_session(self):
        with patch.object(web_app,'resolve_tarjetarojatv_stream',return_value=None) as resolver:
            self.assertEqual(self.client.get('/api/playback/espn.bad').status_code,400)
            resolver.assert_not_called()
            self.assertEqual(self.client.get('/api/playback/espn').status_code,503)

if __name__=='__main__':unittest.main()
