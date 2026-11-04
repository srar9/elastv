import base64
import os
import unittest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import requests
import agenda_service as agenda
import bot_catalog as catalog
import bot_stream_multicanal as bot


def event(title="Liga: Uno vs Dos", date="2026-10-19", hour="12:00:00", embeds=None):
    return {"id": 1, "attributes": {"diary_description": title, "diary_hour": hour,
            "date_diary": date, "embeds": {"data": embeds or []}}}


NOW = datetime(2026, 10, 19, 9, tzinfo=agenda.LOCAL_TZ)


class AgendaChecks(unittest.TestCase):
    def test_events_without_channels_are_kept(self):
        events = agenda.normalize_schedule({"data": [event()]}, NOW)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["time"], "13:00")
        self.assertEqual(events[0]["channels"], [])
        self.assertIn("Canal pendiente", "".join(catalog.agenda_messages(events)))

    def test_local_day_filters_after_timezone_conversion(self):
        row = event(hour="23:30:00")
        self.assertEqual(agenda.normalize_schedule({"data": [row]}, NOW), [])
        tomorrow = agenda.normalize_schedule({"data": [row]}, NOW + timedelta(days=1))
        self.assertEqual(tomorrow[0]["date"], "2026-10-20")
        self.assertEqual(tomorrow[0]["time"], "00:30")

    def test_utc_legacy_payload_has_correct_date(self):
        row = {"title": "Liga: Uno vs Dos", "date": "2026-10-19", "time": "03:30"}
        self.assertEqual(agenda.normalize_schedule({"events": [row]}, NOW), [])

    def test_wrapper_keeps_unknown_channels_and_stream_id(self):
        url = "https://tvf90.com/2.php?stream=espn1_nl"
        encoded = base64.b64encode(url.encode()).decode()
        embeds = [{"attributes": {"embed_name": "Otra señal", "embed_iframe": "/embed/eventos.html?r=" + encoded}}]
        result = agenda.normalize_schedule({"data": [event(embeds=embeds)]}, NOW)
        self.assertEqual(result[0]["channels"][0]["slug"], "espn1_nl")
        self.assertEqual(result[0]["channels"][0]["iframe"], url)

    def test_malformed_rows_do_not_remove_good_events(self):
        rows = [None, {"attributes": []}, event(date="bad"), event()]
        self.assertEqual(len(agenda.normalize_schedule({"data": rows}, NOW)), 1)

    def test_today_cache_is_used_during_temporary_failure(self):
        service = agenda.ScheduleService()
        response = Mock()
        response.status_code = 200
        response.json.return_value = {"data": [event()]}
        with patch.object(agenda.requests, "get", return_value=response):
            service.get(NOW)
        service.loaded -= 100
        with patch.object(agenda.requests, "get", side_effect=requests.ConnectionError("secret")):
            self.assertEqual(len(service.get(NOW)), 1)
        self.assertTrue(service.stale)

    def test_yesterday_cache_is_never_presented_as_today(self):
        service = agenda.ScheduleService()
        response = Mock()
        response.status_code = 200
        response.json.return_value = {"data": [event()]}
        with patch.object(agenda.requests, "get", return_value=response):
            service.get(NOW)
        with patch.object(agenda.requests, "get", side_effect=requests.ConnectionError):
            with self.assertRaises(agenda.ScheduleUnavailable):
                service.get(NOW + timedelta(days=1))

    def test_successful_empty_schedule_is_cached(self):
        service = agenda.ScheduleService()
        response = Mock()
        response.status_code = 200
        response.json.return_value = {"data": []}
        with patch.object(agenda.requests, "get", return_value=response) as fetch:
            self.assertEqual(service.get(NOW), [])
            self.assertEqual(service.get(NOW), [])
        self.assertEqual(fetch.call_count, 2)  # Two providers, one refresh.

    def test_all_events_are_rendered_in_valid_sized_pages_without_keys(self):
        rows = [event(title=f"Liga: Equipo {i:03d} vs Rival") for i in range(100)]
        events = agenda.normalize_schedule({"data": rows}, NOW)
        pages = catalog.agenda_messages(events)
        self.assertGreater(len(pages), 1)
        for page in pages:
            self.assertLessEqual(len(page.encode("utf-16-le")) // 2, 3500)
        for index in range(100):
            self.assertIn(f"Equipo {index:03d}", "".join(pages))

    def test_missing_feed_is_not_replaced_with_channel_menu(self):
        with patch.object(bot, "fetch_tarjetaroja_schedule", side_effect=agenda.ScheduleUnavailable("No disponible")), \
                patch.object(bot, "get_sports_menu_messages") as menu:
            messages = bot.get_live_matches_agenda("secret-key")
        self.assertIn("no está disponible", messages[0])
        menu.assert_not_called()


class CommandChecks(unittest.TestCase):
    def setUp(self):
        self.admin = patch.object(bot, "ADMIN_USER_IDS", ["6467102546"])
        self.admin.start()
        self.addCleanup(self.admin.stop)

    def message(self, text, admin=True):
        return {"chat": {"id": 1}, "from": {"id": bot.ADMIN_USER_IDS[0] if admin else "unauthorized"}, "text": text}

    def test_repeated_slashes_case_and_bot_mentions(self):
        self.assertEqual(catalog.normalize_command("/ / /PARTIDOS@Elciro_bot"), "/partidos")
        self.assertEqual(catalog.normalize_command("/BUSCAR Café"), "/buscar Café")
        self.assertEqual(catalog.normalize_command("/stop@OtherBot", "Elciro_bot"), "")

    def test_agenda_command_with_mention_routes_correctly(self):
        with patch.object(bot, "BOT_USERNAME", "Elciro_bot"), patch.object(bot, "send_msg") as send, patch.object(bot, "get_live_matches_agenda", return_value=["TODOS"]):
            bot.handle_message(self.message("///PARTIDOS@Elciro_bot"))
        self.assertEqual(send.call_args.args[1], "TODOS")

    def test_partial_command_is_not_executed(self):
        with patch.object(bot, "send_msg"), patch.object(bot, "stop_all_streams") as stop:
            bot.handle_message(self.message("/stopallgarbage", admin=False))
        stop.assert_not_called()

    def test_pause_alias_requires_administrator(self):
        with patch.object(bot, "send_msg") as send, patch.object(bot, "stop_single_stream") as stop:
            bot.handle_message(self.message("/pause", admin=False))
        stop.assert_not_called()
        self.assertIn("denegado", send.call_args.args[1])

    def test_direct_http_source_is_not_mistaken_for_a_stream_key(self):
        url = "https://example.invalid/own.m3u8?access=xyz"
        with patch.object(bot, "send_msg"), patch.object(bot, "start_single_stream", return_value=(True, "OK")) as start:
            bot.handle_message(self.message("/stream " + url))
        self.assertEqual(start.call_args.args[0], url)
        self.assertEqual(start.call_args.args[1], bot.CONFIG["stream_key"])

    def test_channels_do_not_disclose_keys(self):
        with patch.object(bot, "fetch_tarjetaroja_schedule", return_value=[]):
            pages = bot.get_sports_menu_messages("private-stream-key")
        self.assertNotIn("private-stream-key", "".join(pages))
        self.assertIn("/stream espn", "".join(pages))

    def test_search_has_no_six_match_limit(self):
        events = agenda.normalize_schedule({"data": [event(title=f"Liga: Equipo {i} vs Rival") for i in range(15)]}, NOW)
        with patch.object(bot, "fetch_tarjetaroja_schedule", return_value=events):
            result = bot.search_tarjetaroja("LIGA", "secret")
        self.assertIn("Equipo 14", result)
        self.assertNotIn("secret", result)

    def test_oversized_responses_have_complete_plain_text_fallback(self):
        parts = catalog.telegram_parts("<b>" + "Texto &amp; " * 1000 + "</b>")
        self.assertGreater(len(parts), 1)
        self.assertTrue(all(mode is None for _, mode in parts))
        self.assertEqual("".join(text for text, _ in parts), "Texto & " * 1000)

    def test_restart_state_is_consumed_without_sending_messages(self):
        state = '[{"source":"espn","destination":"rtmps://example.invalid/private"}]'
        with patch.dict(os.environ, {"EL_CIRO_RESUME": state}), \
                patch.object(bot, "start_single_stream", return_value=(True, "OK")) as start, \
                patch.object(bot, "send_msg") as send:
            self.assertEqual(bot.restore_streams_from_environment(), 1)
            self.assertNotIn("EL_CIRO_RESUME", os.environ)
        self.assertEqual(start.call_args.args[2], None)
        send.assert_not_called()


class SharedSurfaceChecks(unittest.TestCase):
    def test_web_api_and_miniapp_keep_all_events(self):
        import web_app
        import public_bot
        rows = [event(title=f"Liga: Equipo {i:03d} vs Rival") for i in range(35)]
        events = agenda.normalize_schedule({"data": rows}, NOW)
        with patch.object(web_app, "fetch_tarjetarojatv_schedule", return_value=events):
            response = web_app.app.test_client().get("/api/partidos")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json["events"]), 35)
        msg = {"chat": {"id": 1, "type": "private"}, "from": {"id": 123}, "text": "/partidos@MiniBot"}
        with patch.object(public_bot.schedule, "get", return_value=events), \
                patch.object(public_bot, "send") as send, patch.object(public_bot.time, "sleep"):
            public_bot.handle_message(msg)
        send.assert_called_once()
        self.assertIn("35 resultados",send.call_args.args[1])
        view = next(reversed(public_bot.VIEWS.values()))
        self.assertEqual(len(view['items']),35)
        self.assertEqual(view['items'][-1]['data']['match'],'Equipo 034 vs Rival')


if __name__ == "__main__":
    unittest.main()
