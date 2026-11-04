import json
import re
import unittest
from html import unescape
from urllib.parse import urlencode, urlsplit, parse_qs
from unittest.mock import patch

import web_app


class WebsiteChecks(unittest.TestCase):
    def setUp(self):
        self.events=[dict(match='A vs B',match_slug='a-vs-b',competition='Liga A',time='20:00',starts_at='2026-11-03T20:00:00-04:00',
                          channels=[dict(slug=f'source_{i}',name=f'Canal {i}',lang='Español') for i in range(12)])]
        self.schedule=patch.object(web_app,'fetch_tarjetarojatv_schedule',return_value=self.events)
        self.schedule.start();self.addCleanup(self.schedule.stop)
        self.client=web_app.app.test_client()

    def path(self,event=None):
        event=event or self.events[0]
        return '/partido/'+event['match_slug']+'?'+urlencode(dict(c=event['competition'],at=event['starts_at']))

    def test_home_opens_channel_selection_instead_of_first_stream(self):
        markup=self.client.get('/').get_data(as_text=True)
        self.assertIn('/partido/a-vs-b?',markup)
        self.assertNotIn('/ver/source_0',markup)
        self.assertIn('12 canales',markup)

    def test_match_page_exposes_every_published_channel_without_autoplay(self):
        result=self.client.get(self.path())
        self.assertEqual(result.status_code,200)
        markup=result.get_data(as_text=True)
        links=[unescape(url) for url in re.findall(r'href="([^"]+)"',markup) if url.startswith('/ver/')]
        self.assertEqual(len(links),12)
        for i in range(12):
            self.assertTrue(any(urlsplit(url).path==f'/ver/source_{i}' for url in links))
            self.assertIn(f'Canal {i}',markup)
        self.assertNotIn('<iframe',markup)
        self.assertNotIn('<video',markup)

    def test_selected_channel_keeps_every_alternative_and_match_identity(self):
        event=self.events[0]
        url='/ver/source_8?'+urlencode(dict(m=event['match_slug'],c=event['competition'],at=event['starts_at']))
        result=self.client.get(url)
        self.assertEqual(result.status_code,200)
        markup=result.get_data(as_text=True)
        self.assertIn('/embed/source_8',markup)
        self.assertEqual(len(re.findall(r'<option\b',markup)),12)
        config=json.loads(re.search(r'id="playerConfig">(.*?)</script>',markup,re.S)[1])
        self.assertEqual(config['channel'],'source_8')
        self.assertEqual(config['starts_at'],event['starts_at'])
        self.assertEqual(config['competition'],'Liga A')
        self.assertIn('Canales del partido',markup)
        self.assertNotIn('t.me/Elcirotv_bot',markup)

    def test_unannounced_and_removed_matches_have_clear_site_pages(self):
        self.events[0]['channels']=[]
        result=self.client.get(self.path())
        self.assertEqual(result.status_code,200)
        self.assertIn('todavía no tiene señales',result.get_data(as_text=True))
        self.assertNotIn('/ver/espn',result.get_data(as_text=True))
        result=self.client.get('/partido/unknown')
        self.assertEqual(result.status_code,404)
        self.assertIn('Ver los partidos de hoy',result.get_data(as_text=True))

    def test_same_named_matches_do_not_mix_channels(self):
        duplicate=dict(self.events[0],competition='Liga B',starts_at='2026-11-03T22:00:00-04:00',channels=[dict(slug='other-channel',name='Otro canal')])
        self.events.append(duplicate)
        result=self.client.get(self.path(duplicate))
        self.assertIn('/ver/other-channel',result.get_data(as_text=True))
        self.assertNotIn('/ver/source_0',result.get_data(as_text=True))
        self.assertEqual(self.client.get('/partido/a-vs-b').status_code,404)

    def test_channel_not_in_selected_fixture_returns_to_chooser(self):
        event=self.events[0]
        result=self.client.get('/ver/unrelated?'+urlencode(dict(m=event['match_slug'],c=event['competition'],at=event['starts_at'])))
        self.assertEqual(result.status_code,302)
        self.assertEqual(urlsplit(result.headers['Location']).path,'/partido/a-vs-b')


if __name__=='__main__':unittest.main()
