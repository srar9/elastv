import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch, Mock, MagicMock
from live_delivery import Media, MediaCache, Reports, complete_media, UpstreamHTTPError
import web_app


class DeliveryChecks(unittest.TestCase):
    def cache(self, **options):
        cache=MediaCache(**options);self.addCleanup(cache.close);return cache

    def test_simultaneous_viewers_download_each_fragment_only_once(self):
        cache=self.cache();entered=threading.Event();release=threading.Event();calls=[]
        def load():
            calls.append(1);entered.set();release.wait(2);return Media(b'complete','video/mp2t')
        with ThreadPoolExecutor(max_workers=6) as workers:
            first=workers.submit(cache.get,'segment',load);self.assertTrue(entered.wait(1))
            followers=[workers.submit(cache.get,'segment',load) for _ in range(5)]
            release.set();results=[first.result()]+[future.result() for future in followers]
        self.assertEqual(calls,[1]);self.assertTrue(all(value.body==b'complete' for value in results))

    def test_prepared_fragment_is_reused_by_the_foreground_request(self):
        cache=self.cache();ready=threading.Event();calls=[]
        def load():calls.append(1);ready.set();return Media(b'video','video/mp2t')
        cache.prepare('segment',load);self.assertTrue(ready.wait(1))
        self.assertEqual(cache.get('segment',load).body,b'video');self.assertEqual(calls,[1])

    def test_partial_or_failed_download_is_not_cached(self):
        cache=self.cache()
        with self.assertRaises(OSError):cache.get('bad',lambda:(_ for _ in ()).throw(OSError('truncated')))
        self.assertEqual(cache.get('bad',lambda:Media(b'retry','video/mp2t')).body,b'retry')

    def test_cache_expires_and_evicts_to_stay_within_memory_limit(self):
        clock=[1];cache=self.cache(max_bytes=6,ttl=10,now=lambda:clock[0])
        cache.get('a',lambda:Media(b'1234','video/mp2t'));cache.get('b',lambda:Media(b'5678','video/mp2t'))
        self.assertEqual(cache.size,4);self.assertNotIn('a',cache.items)
        clock[0]=12;self.assertEqual(cache.get('b',lambda:Media(b'new','video/mp2t')).body,b'new')

    def test_truncated_empty_and_error_pages_are_rejected_before_any_bytes_are_served(self):
        class Response:
            status_code=200
            headers={'Content-Type':'video/mp2t','Content-Length':'6'}
            def iter_content(self,**_):return iter([b'123'])
        with self.assertRaisesRegex(OSError,'INCOMPLETE'):complete_media(Response())
        Response.headers={'Content-Type':'text/html'}
        with self.assertRaisesRegex(OSError,'INVALID_MEDIA'):complete_media(Response())
        Response.headers={'Content-Type':'video/mp2t'}
        with self.assertRaisesRegex(OSError,'DOWNLOAD_LIMIT'):complete_media(Response(),limit=2)

    def test_slow_diagnostic_storage_does_not_hold_up_video_delivery(self):
        entered=threading.Event();release=threading.Event()
        def record(*args):entered.set();release.wait(2)
        reports=Reports(record,capacity=1)
        try:
            reports.submit('espn','ok');self.assertTrue(entered.wait(1))
            reports.submit('espn','ok');reports.submit('espn','ok')
            self.assertFalse(release.is_set())
        finally:release.set();reports.queue.join()

    def test_only_recent_same_origin_media_is_prepared(self):
        text='#EXTM3U\na.ts\nb.ts\nc.ts\nhttps://other.example/foreign.ts\n'
        with patch.object(web_app.MEDIA_CACHE,'prepare') as prepare:
            web_app.prepare_recent_media(text,'https://cdn.example/live/playlist.m3u8','https://tvf90.com/')
            self.assertEqual([call.args[0][0] for call in prepare.call_args_list],['https://cdn.example/live/c.ts'])

    def test_signed_segment_uses_complete_cached_response_and_rejects_tampering(self):
        client=web_app.app.test_client();cache=self.cache()
        cache.put(('https://cdn.example/segment.ts','https://tvf90.com/'),Media(b'full-file','video/mp2t'))
        path=web_app.signed_target('espn','https://cdn.example/segment.ts','https://tvf90.com/')
        with patch.object(web_app,'MEDIA_CACHE',cache),patch.object(web_app,'SOURCE_REPORTS'),patch.object(web_app.HLS_SESSION,'get') as load:
            for _ in range(2):
                response=client.get(path);self.assertEqual(response.status_code,200);self.assertEqual(response.data,b'full-file')
                self.assertEqual(response.headers['Content-Length'],'9');self.assertEqual(response.headers['X-Video-Delivery'],'progressive-cache-v1')
            self.assertEqual(load.call_count,0)
            self.assertEqual(client.get(path.replace('espn/','espn2/')).status_code,403)
            self.assertEqual(load.call_count,0)

    def test_expired_source_authorization_is_not_hidden_as_a_retryable_gateway_error(self):
        path=web_app.signed_target('espn','https://cdn.example/expired.ts','https://tvf90.com/')
        with patch.object(web_app,'MEDIA_CACHE',self.cache()),patch.object(web_app,'SOURCE_REPORTS'),patch.object(web_app.HLS_SESSION,'get',return_value=Mock(status_code=403,headers={})):
            response=web_app.app.test_client().get(path)
            self.assertEqual(response.status_code,403)

    def test_first_bytes_are_sent_before_the_remaining_fragment_is_downloaded(self):
        second_read=threading.Event();upstream=Mock(status_code=200,headers={'Content-Type':'video/mp2t','Content-Length':'6'})
        def chunks(**_):
            yield b'abc'
            second_read.set()
            yield b'def'
        upstream.iter_content.side_effect=chunks
        path=web_app.signed_target('espn','https://cdn.example/first.ts','https://tvf90.com/')
        with patch.object(web_app,'MEDIA_CACHE',self.cache()),patch.object(web_app,'SOURCE_REPORTS'),patch.object(web_app.HLS_SESSION,'get',return_value=upstream):
            response=web_app.app.test_client().get(path,buffered=False)
            self.assertFalse(second_read.is_set());self.assertEqual(next(iter(response.response)),b'abc');response.close()

    def test_broken_download_retries_once_on_a_fresh_connection(self):
        old=Mock();old.get.side_effect=web_app.requests.ConnectionError('broken')
        replacement=MagicMock();response=Mock(status_code=200,headers={'Content-Type':'video/mp2t','Content-Length':'3'})
        response.iter_content.return_value=[b'abc'];replacement.get.return_value.__enter__.return_value=response
        with patch.object(web_app.MEDIA_DOWNLOADS,'session',old,create=True),patch.object(web_app.requests,'Session',return_value=replacement):
            self.assertEqual(web_app.download_complete_media('https://cdn.example/a.ts','').body,b'abc')
        old.close.assert_called_once();replacement.get.assert_called_once()

    def test_authorization_denial_is_returned_immediately_without_socket_retries(self):
        session=MagicMock();response=Mock(status_code=403,headers={});session.get.return_value.__enter__.return_value=response
        with patch.object(web_app.MEDIA_DOWNLOADS,'session',session,create=True),patch.object(web_app.requests,'Session') as create:
            with self.assertRaises(UpstreamHTTPError) as error:web_app.download_complete_media('https://cdn.example/a.ts','')
            self.assertEqual(error.exception.status,403);create.assert_not_called()
        session.get.assert_called_once();response.iter_content.assert_not_called()

    def test_expired_playlist_also_requests_a_new_session_without_gateway_retries(self):
        upstream=Mock(status_code=403)
        upstream.raise_for_status.side_effect=web_app.requests.HTTPError(response=upstream)
        path=web_app.signed_target('espn','https://cdn.example/live.m3u8','https://tvf90.com/',True)
        with patch.object(web_app.HLS_SESSION,'get') as get,patch.object(web_app,'SOURCE_REPORTS'):
            get.return_value.__enter__.return_value=upstream
            response=web_app.app.test_client().get(path)
        self.assertEqual(response.status_code,403);self.assertEqual(response.headers['X-Video-Error'],'source-auth')

if __name__=='__main__':unittest.main()
