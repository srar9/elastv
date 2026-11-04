import hashlib
import hmac
import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlencode, urlsplit, parse_qs

import audience
import public_bot
import web_app


class PublicChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = patch.object(audience, 'DB_PATH', str(Path(self.temp.name) / 'audience.db'))
        self.db.start()
        audience.initialize()
        self.client = web_app.app.test_client()

    def tearDown(self):
        self.db.stop()
        self.temp.cleanup()

    def signed(self, user_id, age=0):
        data = dict(auth_date=str(int(time.time()) - age), user=json.dumps(dict(id=user_id)))
        check = '\n'.join(f'{k}={v}' for k, v in sorted(data.items()))
        key = hmac.new(b'WebAppData', b'test-token', hashlib.sha256).digest()
        data['hash'] = hmac.new(key, check.encode(), hashlib.sha256).hexdigest()
        return urlencode(data)

    def test_statistics_only_accept_signed_owner(self):
        with patch.object(public_bot, 'TOKEN', 'test-token'):
            self.assertEqual(self.client.get('/api/admin/statistics?user_id=6467102546').status_code, 403)
            for raw in (self.signed(123), self.signed(audience.OWNER_ID, 90000), self.signed(audience.OWNER_ID) + '&user=bad'):
                self.assertEqual(self.client.get('/api/admin/statistics', headers={'X-Telegram-Init-Data':raw}).status_code, 403)
            result = self.client.get('/api/admin/statistics', headers={'X-Telegram-Init-Data':self.signed(audience.OWNER_ID)})
            self.assertEqual(result.status_code, 200)
            self.assertEqual(result.headers['Cache-Control'], 'no-store')

    def test_visits_pause_expire_and_deduplicate(self):
        data = dict(session_id='session_123', match_id='team-a-team-b', title='A vs B', playing=False)
        self.assertEqual(self.client.post('/api/audience', json=data).status_code, 200)
        self.assertEqual(audience.summary()['watching'], 0)
        data['playing'] = True
        self.client.post('/api/audience', json=data)
        self.client.post('/api/audience', json=data)
        stats = audience.summary()
        self.assertEqual((stats['player_entries'], stats['watching']), (1, 1))
        data['session_id'] = 'session_456'
        self.client.post('/api/audience', json=data)
        self.assertEqual(audience.summary()['watching'], 1)
        with patch('audience.time.time', return_value=time.time() + 50):
            self.assertEqual(audience.summary()['watching'], 0)
        data['playing'] = False
        self.client.post('/api/audience', json=data)
        self.assertEqual(audience.summary()['matches'][0]['entries'], 2)

    def test_private_menu_and_no_control_commands(self):
        for user_id in (123, audience.OWNER_ID):
            with patch.object(public_bot, 'send', return_value={'message_id':17}) as send, patch.object(public_bot, 'api') as api, patch.object(public_bot.schedule, 'get',return_value=[]) as schedule:
                public_bot.handle_message(dict(chat=dict(id=user_id,type='private'), **{'from':dict(id=user_id)}, text='/start'))
                send.assert_called_once()
                schedule.assert_not_called()
                api.assert_not_called()
                rows = send.call_args.args[2]
                self.assertTrue(any('web_app' in item and item['web_app']['url'] == public_bot.BASE_URL+'/' for row in rows for item in row))
                self.assertEqual(any('Estadísticas' in item['text'] for row in rows for item in row), user_id == audience.OWNER_ID)
        with patch.object(public_bot, 'send') as send:
            public_bot.handle_message(dict(chat=dict(id=-12,type='group'), **{'from':dict(id=audience.OWNER_ID)}, text='/stats'))
            send.assert_not_called()

    def test_all_results_have_miniapp_buttons(self):
        events = [dict(match=f'Team {i}', match_slug=f'team-{i}', competition='Basketball', time='20:00',
                       channels=[dict(slug='dsports_eventos',name='DSports')]) for i in range(19)]
        with patch.object(public_bot.schedule, 'get', return_value=events), patch.object(public_bot, 'send') as send, patch.object(public_bot, 'api') as api:
            public_bot.handle_message(dict(chat=dict(id=123,type='private'), **{'from':dict(id=123)}, text='/partidos'))
            send.assert_called_once()
            rows=send.call_args.args[2]
            buttons=[]
            pages=0
            while True:
                buttons.extend(item for row in rows for item in row if 'web_app' in item)
                next_button=next((item for row in rows for item in row if item['text']=='Siguiente ›'),None)
                if not next_button:break
                public_bot.handle_callback(dict(id='click',data=next_button['callback_data'],message=dict(message_id=17,chat=dict(id=123,type='private')),**{'from':dict(id=123)}))
                self.assertEqual(api.call_args.args[0],'editMessageText')
                self.assertEqual(api.call_args.kwargs['message_id'],17)
                rows=api.call_args.kwargs['reply_markup']['inline_keyboard']
                pages+=1
                self.assertLess(pages,10)
            urls = [b['web_app']['url'] for b in buttons if '/ver/' in b['web_app']['url']]
            self.assertEqual(len(urls), 19)
            self.assertEqual(len(set(urls)),19)
            send.assert_called_once()
            self.assertTrue(all('dsports_eventos' in url for url in urls))
            self.assertTrue(all(parse_qs(urlsplit(url).query)['mode'] == ['watch'] for url in urls))

    def test_start_sends_one_ordered_menu_without_loading_games(self):
        events = [dict(match=f'Team {i}', match_slug=f'team-{i}', competition='Basketball', time='20:00',
                       channels=[dict(slug='espn',name='ESPN'),dict(slug='espn2',name='ESPN 2')]) for i in range(19)]
        with patch.object(public_bot.schedule, 'get', return_value=events) as schedule, patch.object(public_bot, 'send',return_value={'message_id':17}) as send, patch.object(public_bot,'api') as api:
            public_bot.handle_message(dict(chat=dict(id=123,type='private'), **{'from':dict(id=123)}, text='/start'))
            send.assert_called_once()
            schedule.assert_not_called()
            self.assertNotIn('remove_keyboard',send.call_args.kwargs)
            self.assertNotIn('Team',send.call_args.args[1])
            api.assert_not_called()
            rows=send.call_args.args[2]
            video_buttons=[item for row in rows for item in row if '/ver/' in item.get('web_app',{}).get('url','')]
            self.assertEqual(len(video_buttons),0)
            self.assertTrue(any(item.get('web_app',{}).get('url')==public_bot.BASE_URL+'/' for row in rows for item in row))
            self.assertEqual([item['text'] for row in rows for item in row],
                             ['⚽ Partidos del día','📺 Canales','🔎 Buscar','📣 Unirse al canal principal','📱 Abrir mini app'])
            self.assertTrue(any(item.get('url')=='https://t.me/elasdelfutbol' for row in rows for item in row))
            self.assertNotIn('Venezuela',send.call_args.args[1])

    def test_search_button_prompts_inside_chat(self):
        with patch.object(public_bot.schedule,'get') as schedule, patch.object(public_bot,'send') as send:
            public_bot.handle_message(dict(chat=dict(id=123,type='private'), **{'from':dict(id=123)},text='🔎 Buscar'))
            schedule.assert_not_called()
            self.assertIn('Escribe aquí',send.call_args.args[1])
            send.assert_called_once()

    def test_start_attaches_buttons_to_the_actual_send_message_payload(self):
        for user_id in (123,audience.OWNER_ID):
            with self.subTest(user_id=user_id),patch.object(public_bot.requests,'post') as post,patch.object(public_bot.schedule,'get') as schedule:
                post.return_value.json.return_value={'ok':True,'result':{'message_id':17}}
                public_bot.handle_message(dict(chat=dict(id=user_id,type='private'),**{'from':dict(id=user_id)},text='/start'))
                post.assert_called_once()
                self.assertTrue(post.call_args.args[0].endswith('/sendMessage'))
                payload=post.call_args.kwargs['json']
                self.assertEqual(payload['chat_id'],user_id)
                self.assertEqual(payload['text'],public_bot.HOME_TEXT)
                self.assertNotIn('remove_keyboard',payload['reply_markup'])
                rows=payload['reply_markup']['inline_keyboard']
                self.assertTrue(any(item.get('callback_data')=='menu:events' for row in rows for item in row))
                self.assertTrue(any(item.get('url')=='https://t.me/elasdelfutbol' for row in rows for item in row))
                self.assertTrue(any('web_app' in item for row in rows for item in row))
                self.assertEqual(any(item.get('callback_data')=='menu:stats' for row in rows for item in row),user_id==audience.OWNER_ID)
                schedule.assert_not_called()

    def test_menu_buttons_edit_existing_message(self):
        events=[dict(match='A vs B',match_slug='a-vs-b',competition='Basketball',time='20:00',channels=[dict(slug='espn',name='ESPN')])]
        with patch.object(public_bot.schedule,'get',return_value=events),patch.object(public_bot,'api') as api,patch.object(public_bot,'send') as send:
            public_bot.handle_callback(dict(id='click',data='menu:events',message=dict(message_id=17,chat=dict(id=123,type='private')),**{'from':dict(id=123)}))
            send.assert_not_called()
            self.assertEqual(api.call_args.args[0],'editMessageText')
            self.assertEqual(api.call_args.kwargs['message_id'],17)
            self.assertIn('Partidos del día',api.call_args.kwargs['text'])
            self.assertNotIn('Venezuela',api.call_args.kwargs['text'])
            rows=api.call_args.kwargs['reply_markup']['inline_keyboard']
            self.assertTrue(any(item.get('url')==public_bot.PUBLIC_CHANNEL_URL for row in rows for item in row))
            public_bot.schedule.get.reset_mock()
            public_bot.handle_callback(dict(id='back',data='menu:home',message=dict(message_id=17,chat=dict(id=123,type='private')),**{'from':dict(id=123)}))
            public_bot.schedule.get.assert_not_called()
            send.assert_not_called()

    def test_search_combines_events_and_channels_in_one_message(self):
        events=[dict(match='A vs B',match_slug='a-vs-b',competition='Basketball',time='20:00',channels=[dict(slug='espn',name='ESPN')])]
        channels=[dict(slug='espn',name='ESPN')]
        with patch.object(public_bot.schedule,'get',return_value=events),patch.object(public_bot,'catalog_channels',return_value=channels),patch.object(public_bot,'send') as send:
            public_bot.handle_message(dict(chat=dict(id=123,type='private'),**{'from':dict(id=123)},text='ESPN'))
            send.assert_called_once()
            self.assertEqual(sum('/ver/' in item.get('web_app',{}).get('url','') for row in send.call_args.args[2] for item in row),2)

    def test_expired_or_other_users_pages_do_not_send_new_messages(self):
        view=dict(chat_id=123,user_id=123,private=True,kind='events',items=[],heading='Games',refresh='menu:events',created=time.time())
        with patch.dict(public_bot.VIEWS,{'valid':view}),patch.object(public_bot,'api') as api,patch.object(public_bot,'send') as send:
            callback=dict(id='click',data='page:valid:1',message=dict(message_id=17,chat=dict(id=123,type='private')),**{'from':dict(id=456)})
            public_bot.handle_callback(callback)
            self.assertEqual(api.call_args.args[0],'answerCallbackQuery')
            self.assertTrue(api.call_args.kwargs['show_alert'])
            callback['from']['id']=123
            callback['data']='page:missing:1'
            public_bot.handle_callback(callback)
            self.assertEqual(api.call_args.args[0],'editMessageText')
            self.assertIn('caducó',api.call_args.kwargs['text'])
            send.assert_not_called()

    def test_stats_menu_cannot_be_opened_by_other_users(self):
        with patch.object(public_bot,'summary') as summary,patch.object(public_bot,'api') as api:
            public_bot.handle_callback(dict(id='click',data='menu:stats',message=dict(message_id=17,chat=dict(id=123,type='private')),**{'from':dict(id=123)}))
            summary.assert_not_called()
            self.assertEqual(api.call_count,1)

    def test_channels_and_statistics_each_send_only_one_page(self):
        channels=[dict(name=f'Channel {i}',slug=f'channel-{i}') for i in range(20)]
        data=dict(watching=1,bot_users=2,player_entries=20,player_visitors=3,app_entries=4,bot_entries=5,
                  matches=[dict(title=f'Match {i}',watching=1,entries=2,visitors=3) for i in range(20)])
        with patch.object(public_bot,'catalog_channels',return_value=channels),patch.object(public_bot,'summary',return_value=data),patch.object(public_bot,'send') as send:
            public_bot.handle_message(dict(chat=dict(id=123,type='private'),**{'from':dict(id=123)},text='/canales'))
            send.assert_called_once()
            self.assertEqual(sum('/ver/' in item.get('web_app',{}).get('url','') for row in send.call_args.args[2] for item in row),6)
            send.reset_mock()
            public_bot.handle_message(dict(chat=dict(id=audience.OWNER_ID,type='private'),**{'from':dict(id=audience.OWNER_ID)},text='/estadisticas'))
            send.assert_called_once()
            self.assertIn('Match 5',send.call_args.args[1])
            self.assertNotIn('Match 6',send.call_args.args[1])

    def test_telegram_menu_keeps_miniapp_available(self):
        with patch.object(public_bot,'api',return_value={'username':'Elcirotv_bot'}) as api:
            public_bot.configure()
            menus=[call.kwargs['menu_button'] for call in api.call_args_list if call.args[0]=='setChatMenuButton']
            self.assertTrue(menus)
            self.assertTrue(all(menu==dict(type='web_app',text='Mini app',web_app=dict(url=public_bot.BASE_URL)) for menu in menus))

    def test_bot_and_miniapp_use_chronological_order_with_unknown_times_last(self):
        events=[dict(match=name,match_slug=name.lower(),competition='Liga',time=clock,channels=[dict(slug='espn',name='ESPN')]) for name,clock in [('Late','23:00'),('Unknown','--:--'),('Morning','08:00'),('Afternoon','15:30')]]
        with patch.object(public_bot.schedule,'get',return_value=events),patch.object(public_bot,'send') as send:
            public_bot.handle_message(dict(chat=dict(id=123,type='private'),**{'from':dict(id=123)},text='/partidos'))
            buttons=[item for row in send.call_args.args[2] for item in row if '/ver/' in item.get('web_app',{}).get('url','')]
            self.assertEqual([parse_qs(urlsplit(item['web_app']['url']).query)['title'][0] for item in buttons],['Morning','Afternoon','Late','Unknown'])
            response=self.client.get('/api/partidos')
            self.assertEqual([event['match'] for event in response.json['events']],['Morning','Afternoon','Late','Unknown'])

    def test_start_keeps_miniapp_even_when_agenda_is_down(self):
        with patch.object(public_bot.schedule,'get',side_effect=public_bot.ScheduleUnavailable) as schedule,patch.object(public_bot,'send',return_value={'message_id':17}) as send,patch.object(public_bot,'api') as api:
            public_bot.handle_message(dict(chat=dict(id=123,type='private'),**{'from':dict(id=123)},text='/start'))
            send.assert_called_once()
            schedule.assert_not_called()
            api.assert_not_called()
            rows=send.call_args.args[2]
            self.assertTrue(any('web_app' in item for row in rows for item in row))

    def test_app_command_shows_miniapp_without_loading_agenda(self):
        with patch.object(public_bot.schedule,'get') as schedule,patch.object(public_bot,'send') as send:
            public_bot.handle_message(dict(chat=dict(id=123,type='private'),**{'from':dict(id=123)},text='/app'))
            send.assert_called_once()
            schedule.assert_not_called()
            self.assertTrue(any('web_app' in item for row in send.call_args.args[2] for item in row))

    def test_primary_channel_and_miniapp_page_have_correct_link_without_timezone_copy(self):
        with patch.object(public_bot,'send') as send,patch.object(public_bot.schedule,'get',return_value=[]):
            public_bot.handle_message(dict(chat=dict(id=123,type='private'),**{'from':dict(id=123)},text='/canal'))
            send.assert_called_once()
            self.assertEqual(send.call_args.args[2][0][0]['url'],'https://t.me/elasdelfutbol')
            response=self.client.get('/')
            markup=response.get_data(as_text=True)
            self.assertEqual(response.status_code,200)
            self.assertNotIn('Venezuela',markup)
            self.assertIn('https://t.me/elasdelfutbol',markup)

    def test_watch_mode_keeps_video_and_alternatives_without_site_navigation(self):
        events=[dict(match='A vs B',match_slug='a-vs-b',competition='Basketball',time='20:00',channels=[dict(slug='espn',name='ESPN'),dict(slug='espn2',name='ESPN 2')])]
        with patch.object(web_app.schedule,'events',events), patch.object(web_app.schedule,'day',web_app.datetime.now(web_app.LOCAL_TZ).date()), patch.object(web_app,'fetch_tarjetarojatv_schedule') as fetch:
            response=self.client.get('/ver/espn?m=a-vs-b&mode=watch')
            self.assertEqual(response.status_code,200)
            markup=response.get_data(as_text=True)
            self.assertIn('class="watch-mode"',markup)
            self.assertIn('id="liveFrame"',markup)
            self.assertIn('/embed/espn',markup)
            self.assertIn('espn2?',markup)
            self.assertIn('mode=watch',markup)
            self.assertIn('Volver al bot',markup)
            self.assertNotIn('class="site-header"',markup)
            self.assertNotIn('class="site-footer"',markup)
            self.assertNotIn('Todos los partidos',markup)
            fetch.assert_not_called()

    def test_cold_watch_page_does_not_wait_for_agenda_or_catalog(self):
        with patch.object(web_app.schedule,'day',None), patch.object(web_app,'fetch_tarjetarojatv_schedule') as agenda, patch.object(web_app,'get_unique_channels') as channels:
            result=self.client.get('/ver/espn?m=a-vs-b&title=A+vs+B&mode=watch')
            self.assertEqual(result.status_code,200)
            self.assertIn(b'id="liveFrame"',result.data)
            self.assertIn(b'player.js',result.data)
            agenda.assert_not_called()
            channels.assert_not_called()

    def test_hls_rewrites_keys_maps_and_nested_playlists(self):
        playlist = '#EXTM3U\n#EXT-X-MEDIA:TYPE=AUDIO,URI="/audio.m3u8"\n#EXT-X-KEY:METHOD=AES-128,URI="../key?k=1"\n#EXT-X-MAP:URI="init.mp4"\n#EXT-X-STREAM-INF:BANDWIDTH=900\n../variant?id=2\nsegment.ts\n'
        result = web_app.rewrite_playlist(playlist, 'https://cdn.example/live/master.m3u8', 'espn', 'https://player.example/')
        self.assertIn('/sub.m3u8?', result)
        self.assertIn('URI="/stream/', result)
        path = web_app.signed_target('espn', 'https://cdn.example/key', 'https://player.example/')
        with patch.object(web_app.HLS_SESSION, 'get') as get:
            self.assertEqual(self.client.get(path.replace('target=', 'target=changed')).status_code, 403)
            get.assert_not_called()
        self.assertEqual(self.client.get('/stream/live/espn/segment.ts?target=http://127.0.0.1').status_code, 403)

    def test_native_embed_does_not_serve_provider_html(self):
        with patch.object(web_app, 'resolve_tarjetarojatv_stream', return_value=dict(stream_url=None, iframe_url='https://ads.example/')):
            result = self.client.get('/embed/espn')
            self.assertEqual(result.status_code, 200)
            self.assertNotIn(b'ads.example', result.data)
            self.assertNotIn(b'P2PEngine', result.data)
            self.assertIn(b'<video', result.data)

    def test_game_pages_show_six_games_with_time_competition_and_direct_play_buttons(self):
        events=[dict(match=f'Home {i} vs Away',match_slug=f'game-{i}',competition='Liga de prueba',time=f'{10+i:02d}:00',channels=[dict(slug='espn',name='ESPN')]) for i in range(9)]
        with patch.object(public_bot.schedule,'get',return_value=events),patch.object(public_bot,'send') as send:
            public_bot.handle_message(dict(chat=dict(id=123,type='private'),**{'from':dict(id=123)},text='/partidos'))
            send.assert_called_once()
            text,rows=send.call_args.args[1:3]
            self.assertIn('10:00',text)
            self.assertIn('Liga de prueba',text)
            self.assertIn('Home 5 vs Away',text)
            self.assertNotIn('Home 6 vs Away',text)
            videos=[item for row in rows for item in row if '/ver/' in item.get('web_app',{}).get('url','')]
            self.assertEqual(len(videos),6)
            self.assertTrue(all('Ver partido' in item['text'] for item in videos))

    def test_source_failure_diagnostics_are_deduplicated_and_recover(self):
        audience.signal_event('espn','failed','No responde','ESPN')
        audience.signal_event('espn','failed','No responde','ESPN')
        data=audience.summary()
        self.assertEqual(data['failing_signals'],1)
        self.assertEqual(data['signals'][0]['failures'],1)
        audience.signal_event('espn','ok','Entregando datos','ESPN')
        self.assertEqual(audience.summary()['failing_signals'],0)
        audience.signal_event('espn','failed','Se interrumpió','ESPN')
        self.assertEqual(audience.summary()['signals'][0]['failures'],2)

    def test_proxy_reports_missing_source_but_not_invalid_unsigned_requests(self):
        with patch.object(web_app,'resolve_tarjetarojatv_stream',return_value={}):
            self.assertEqual(self.client.get('/stream/live/espn/master.m3u8').status_code,503)
        self.assertEqual(audience.summary()['failing_signals'],1)
        self.assertEqual(self.client.get('/stream/live/espn2/segment.ts?target=http://127.0.0.1').status_code,403)
        self.assertEqual(len(audience.summary()['signals']),1)

    def test_proxy_success_means_bytes_received_not_just_http_headers(self):
        from unittest.mock import Mock
        audience.signal_event('espn','failed','Caída','ESPN')
        upstream=Mock(status_code=200,headers={'Content-Type':'video/mp2t'})
        upstream.iter_content.return_value=[b'video' * 100]
        path=web_app.signed_target('espn','https://cdn.example/video.ts','https://player.example/')
        with patch.object(web_app.HLS_SESSION,'get',return_value=upstream):
            response=self.client.get(path)
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.data,b'video'*100)
        self.assertEqual(audience.summary()['failing_signals'],0)
        upstream.close.assert_called()

    def test_proxy_rejects_provider_html_instead_of_executing_it_on_our_origin(self):
        from unittest.mock import Mock
        upstream=Mock(status_code=200,headers={'Content-Type':'text/html; charset=utf-8'})
        path=web_app.signed_target('espn','https://cdn.example/video.ts','https://player.example/')
        with patch.object(web_app.HLS_SESSION,'get',return_value=upstream):
            result=self.client.get(path)
            self.assertEqual(result.status_code,502)
            upstream.iter_content.assert_not_called()
        self.assertEqual(audience.summary()['failing_signals'],1)

    def test_player_keeps_the_real_channel_id_for_aliases(self):
        import re
        with patch.object(web_app.schedule,'day',None):
            result=self.client.get('/ver/espn1?mode=watch')
            config=json.loads(re.search(r'id="playerConfig">(.*?)</script>',result.get_data(as_text=True),re.S)[1])
            self.assertEqual(config['channel'],'espn1')

    def test_reconnect_invalidates_a_cached_failed_resolution(self):
        web_app.STREAM_RESOLVER_CACHE['espn']={'data':{},'timestamp':time.time()}
        with patch.object(web_app,'resolve_tarjetarojatv_stream',return_value={}):
            self.client.get('/embed/espn?refresh=1')
        self.assertNotIn('espn',web_app.STREAM_RESOLVER_CACHE)


if __name__ == '__main__':
    unittest.main()
