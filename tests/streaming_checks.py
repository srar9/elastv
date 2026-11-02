"""Offline regression checks: python -m unittest discover -s tests -p '*_checks.py'."""
import io
import array
import json
import os
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import stream_runtime as runtime
import bot_stream_multicanal as bot
import requests
import channel_source


class RuntimeChecks(unittest.TestCase):
    def test_network_live_source_keeps_realtime_speed(self):
        with patch.dict(os.environ, {"STREAM_PLAYBACK_PERCENT": "103"}):
            with self.assertRaisesRegex(ValueError, "100"):
                runtime.build_command("https://source.invalid/live.m3u8", "", "out.flv")

    def test_frame_color_cannot_inject_filters(self):
        with patch.dict(os.environ, {"STREAM_FRAME_COLOR": "cyan,negate"}):
            with self.assertRaisesRegex(ValueError, "RRGGBB"):
                runtime.build_command("input.mp4", "", "out.flv")

    def process(self, code=None):
        proc = Mock()
        proc.poll.return_value = code
        proc.stream_progress = runtime.OutputProgress()
        return proc

    def test_repeated_progress_is_not_healthy_activity(self):
        proc = self.process()
        proc.stream_progress.update({"frame": "30", "out_time_us": "1000000", "speed": "1x"})
        last = proc.stream_progress.last_advance
        proc.stream_progress.update({"frame": "30", "out_time_us": "1000000"})
        self.assertEqual(last, proc.stream_progress.last_advance)
        self.assertEqual(runtime.health(proc, last + runtime.STALL_SECONDS + 1)[0], "stalled")

    def test_frames_and_time_must_both_advance(self):
        proc = self.process()
        proc.stream_progress.update({"frame": "0", "out_time_us": "1000000"})
        self.assertFalse(proc.stream_progress.received)

    def test_startup_grace_then_timeout(self):
        proc = self.process()
        start = proc.stream_progress.started
        self.assertEqual(runtime.health(proc, start + 1)[0], "starting")
        self.assertEqual(runtime.health(proc, start + runtime.STARTUP_SECONDS + 1)[0], "stalled")

    def test_exit_is_failure_even_after_previous_progress(self):
        self.assertEqual(runtime.health(self.process(1))[0], "failed")

    def test_progress_reader_ignores_invalid_values(self):
        progress = runtime.OutputProgress()
        runtime.consume_progress(io.StringIO("frame=bad\nout_time_us=N/A\nprogress=continue\n"
                                            "frame=60\nout_time_us=2000000\nspeed=1.0x\nprogress=end\n"), progress)
        self.assertEqual(progress.snapshot()["frames"], 60)
        self.assertTrue(progress.snapshot()["received"])

    def test_http_options_are_scoped_to_http_input(self):
        cmd = runtime.build_command("https://source.invalid/live.m3u8", "Referer: test\r\n", "out.flv")
        self.assertIn("-reconnect_on_network_error", cmd[:cmd.index("-i")])
        self.assertIn("-re", cmd[:cmd.index("-i")])
        local = runtime.build_command("input.mp4", "", "out.flv")
        self.assertNotIn("-reconnect", local)
        self.assertIn("0:a:0?", local)

    def test_retry_backoff_is_bounded(self):
        self.assertEqual([runtime.retry_delay(n) for n in (1, 2, 3, 1000)], [3, 6, 12, 60])

    def test_logo_requires_an_existing_image(self):
        with patch.dict(os.environ, {"STREAM_LOGO_PATH": "missing-logo.png"}):
            with self.assertRaisesRegex(ValueError, "STREAM_LOGO_PATH"):
                runtime.build_command("input.mp4", "", "out.flv")

    def test_logo_options_preserve_original_audio_mapping(self):
        with tempfile.TemporaryDirectory() as folder:
            logo = Path(folder) / "logo with spaces.png"
            logo.touch()
            with patch.dict(os.environ, {"STREAM_LOGO_PATH": str(logo), "STREAM_LOGO_POSITION": "bottom-left",
                                         "STREAM_LOGO_WIDTH": "9999", "STREAM_LOGO_OPACITY": "75"}):
                cmd = runtime.build_command("input.mp4", "", "out.flv")
            self.assertIn(str(logo), cmd)
            graph = cmd[cmd.index("-filter_complex") + 1]
            self.assertIn("scale=w=400:", graph)
            self.assertIn("colorchannelmixer=aa=0.75", graph)
            self.assertIn("overlay=x=24:y=main_h-overlay_h-24", graph)
            self.assertIn("0:a:0?", cmd)
            self.assertNotIn("-vf", cmd)

    def test_diagnostic_hides_urls_and_keys(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "sample.log"
            path.write_text("rtmps://example.test/s/private-key https://input.test/live?secret=abc key=private-key")
            text = runtime.safe_tail(path, ("private-key",))
            for value in ("private-key", "secret=abc", "input.test", "example.test"):
                self.assertNotIn(value, text)


class SupervisorChecks(unittest.TestCase):
    def setUp(self):
        bot.active_streams.clear()
        self.info = dict(auto_restart=True, process=None, channel_input="test", key="private",
                         destination="out.flv", restarts=0)
        bot.active_streams["1"] = self.info

    def tearDown(self):
        bot.active_streams.clear()

    def test_launching_slot_is_not_started_twice(self):
        self.info["launching"] = True
        with patch.object(bot.threading, "Thread") as worker:
            bot.supervise_once()
            worker.assert_not_called()

    def test_recovery_is_scheduled_only_once(self):
        with patch.object(bot.threading, "Thread") as worker:
            bot.supervise_once()
            bot.supervise_once()
            self.assertEqual(worker.call_count, 1)
            self.assertEqual(self.info["total_restarts"], 1)

    def test_resolver_failure_leaves_retryable_slot(self):
        with patch.object(bot, "resolve_stream_source", side_effect=RuntimeError("secret-url")):
            bot.recover_stream("1", self.info)
        self.assertFalse(self.info["recovering"])
        self.assertTrue(self.info["auto_restart"])
        self.assertGreater(self.info["next_retry"], time.monotonic())
        self.assertNotIn("secret-url", self.info["last_error"])

    def test_stop_during_resolve_does_not_launch(self):
        def resolve(_):
            # Recovery must never hold stream_lock while resolving over the network.
            self.assertTrue(bot.stream_lock.acquire(blocking=False))
            bot.active_streams.clear()
            bot.stream_lock.release()
            return "input.mp4", "", "test", "test", True
        with patch.object(bot, "resolve_stream_source", side_effect=resolve), patch.object(bot, "launch_ffmpeg_process") as launch:
            bot.recover_stream("1", self.info)
            launch.assert_not_called()

    def test_cancel_after_launch_reaps_unclaimed_process(self):
        proc = Mock()
        log = Mock()
        def launch(*_):
            bot.active_streams.clear()
            return proc, log, "out.log"
        with patch.object(bot, "resolve_stream_source", return_value=("in.mp4", "", "test", "test", True)), \
                patch.object(bot, "launch_ffmpeg_process", side_effect=launch), patch.object(bot, "stop_process") as stop:
            bot.recover_stream("1", self.info)
            stop.assert_any_call(proc)
            log.close.assert_called_once()

    def test_explicit_rejection_pauses_retries(self):
        self.info["process"] = Mock()
        self.info["process"].poll.return_value = 1
        with patch.object(bot, "safe_tail", return_value="Server error: NetStream.Publish.Denied"), \
                patch.object(bot.threading, "Thread") as worker:
            bot.supervise_once()
            self.assertFalse(self.info["auto_restart"])
            self.assertEqual(self.info["status"], "rejected")
            worker.assert_not_called()

    def test_missing_ffmpeg_removes_start_reservation(self):
        bot.active_streams.clear()
        with patch.object(bot, "resolve_stream_source", return_value=("in.mp4", "", "test", "test", True)), \
                patch.object(bot, "launch_ffmpeg_process", side_effect=FileNotFoundError):
            success, _ = bot.start_single_stream("test", "private", 1)
        self.assertFalse(success)
        self.assertEqual(bot.active_streams, {})

    def test_source_rejection_reports_origin_without_starting_encoder(self):
        bot.active_streams.clear()
        response = Mock(status_code=403)
        with patch.object(bot, "resolve_roja_source", return_value=(None, None, "Sin fuente nueva")), \
                patch.object(bot.requests, "get", side_effect=[response, requests.ConnectionError("secret-url")]), \
                patch.object(bot, "launch_ffmpeg_process") as launch:
            success, message = bot.start_single_stream("espn", "private-key", 1)
        self.assertFalse(success)
        self.assertIn("HTTP 403", message)
        self.assertIn("ConnectionError", message)
        self.assertNotIn("secret-url", message)
        self.assertNotIn("private-key", message)
        launch.assert_not_called()
        self.assertEqual(bot.active_streams, {})


    def test_direct_source_does_not_depend_on_channel_directory(self):
        with patch.object(bot.requests, "get") as fetch:
            source, _, _, _, ok = bot.resolve_stream_source("https://example.invalid/own-stream.m3u8")
            fetch.assert_not_called()
            self.assertTrue(ok)
            self.assertEqual(source, "https://example.invalid/own-stream.m3u8")

    def test_same_destination_cannot_publish_on_two_slots(self):
        self.info["destination"] = "rtmps://dc4-1.rtmp.t.me/s/private"
        proc = Mock()
        proc.poll.return_value = None
        proc.stream_progress = runtime.OutputProgress()
        with patch.object(bot, "resolve_stream_source", return_value=("in.mp4", "", "test", "test", True)), \
                patch.object(bot, "launch_ffmpeg_process", return_value=(proc, Mock(), "out.log")), \
                patch.object(bot.time, "sleep"):
            success, _ = bot.start_single_stream("test", "private", 1, requested_slot="2")
        self.assertTrue(success)
        self.assertEqual(list(bot.active_streams), ["2"])
        self.assertFalse(self.info["auto_restart"])

    def test_retry_wait_does_not_launch_early(self):
        self.info["next_retry"] = time.monotonic() + 60
        with patch.object(bot.threading, "Thread") as worker:
            bot.supervise_once()
            worker.assert_not_called()


class ChannelSourceChecks(unittest.TestCase):
    def test_nested_player_preserves_immediate_referer(self):
        responses = [Mock(status_code=200, text='<iframe src="https://tvf90.com/online/canal.php?stream=espn"></iframe>'),
                     Mock(status_code=200, text='<iframe src="/5.php?stream=espn"></iframe>'),
                     Mock(status_code=200, text='const playbackURL = "https://media.invalid/own.m3u8?token=private";')]
        with patch.object(channel_source.requests, "get", side_effect=responses) as fetch:
            url, referer, status = channel_source.resolve_roja_source("espn")
        self.assertEqual(fetch.call_count, 3)
        self.assertEqual(referer, "https://tvf90.com/5.php?stream=espn")
        self.assertEqual(url, "https://media.invalid/own.m3u8?token=private")
        self.assertTrue(status.startswith("OK"))
        self.assertEqual(fetch.call_args.kwargs["headers"]["Referer"],
                         "https://tvf90.com/online/canal.php?stream=espn")

    def test_unknown_iframe_hosts_are_not_followed(self):
        page = Mock(status_code=200, text='<iframe src="https://unknown.invalid/ad"></iframe>')
        with patch.object(channel_source.requests, "get", return_value=page) as fetch:
            url, _, _ = channel_source.resolve_roja_source("espn")
        self.assertIsNone(url)
        self.assertEqual(fetch.call_count, 1)

    def test_rejected_origin_does_not_trigger_challenge_bypass(self):
        with patch.object(channel_source.requests, "get", return_value=Mock(status_code=403)) as fetch:
            url, _, status = channel_source.resolve_roja_source("espn")
        self.assertIsNone(url)
        self.assertIn("HTTP 403", status)
        self.assertEqual(fetch.call_count, 1)

    def test_unmapped_channel_makes_no_requests(self):
        with patch.object(channel_source.requests, "get") as fetch:
            self.assertIsNone(channel_source.resolve_roja_source("unknown")[0])
        fetch.assert_not_called()



@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg/ffprobe required")
class EncoderChecks(unittest.TestCase):
    def test_presentation_effects_render_and_keep_audio_video_aligned(self):
        with tempfile.TemporaryDirectory() as folder:
            source = str(Path(folder) / "source.mkv")
            dest = str(Path(folder) / "styled.flv")
            subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi",
                            "-i", "color=white:size=640x360:rate=30", "-f", "lavfi", "-i",
                            "sine=frequency=440:sample_rate=48000", "-t", "3", "-c:v", "mpeg4",
                            "-c:a", "aac", source], check=True, capture_output=True, timeout=45)
            style = dict(line.split("=", 1) for line in Path("estilo_el_ciro.env").read_text().splitlines()
                         if line and not line.startswith("#"))
            style["STREAM_PLAYBACK_PERCENT"] = "103"  # Files can run faster than real time.
            with patch.dict(os.environ, style):
                proc, log, path = runtime.launch(source, "", dest, str(Path(folder) / "style.log"))
            try:
                proc.wait(timeout=45)
                self.assertEqual(proc.returncode, 0, runtime.safe_tail(path))
            finally:
                runtime.stop_process(proc)
                log.close()
            pixel = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", dest,
                                    "-vf", "crop=2:2:10:10,scale=1:1,format=rgb24", "-frames:v", "1",
                                    "-f", "rawvideo", "pipe:1"], check=True, capture_output=True, timeout=20).stdout
            self.assertEqual(len(pixel), 3)
            for actual, expected in zip(pixel, (16, 42, 67)):
                self.assertLess(abs(actual - expected), 15)
            probe = subprocess.run(["ffprobe", "-v", "error", "-show_packets", "-show_entries",
                                    "packet=stream_index,pts_time,duration_time", "-of", "json", dest],
                                   check=True, capture_output=True, text=True, timeout=15)
            ends = {}
            for packet in json.loads(probe.stdout)["packets"]:
                end = float(packet["pts_time"]) + float(packet.get("duration_time", 0))
                index = packet["stream_index"]
                ends[index] = max(ends.get(index, 0), end)
            self.assertEqual(set(ends), {0, 1})
            self.assertLess(abs(ends[0] - ends[1]), .2)
            self.assertLess(abs(ends[0] - 3 / 1.03), .12)
            pcm = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", "0.5",
                                  "-i", dest, "-t", "1", "-vn", "-ac", "1", "-ar", "48000",
                                  "-f", "s16le", "pipe:1"], check=True, capture_output=True, timeout=20).stdout
            samples = array.array("h", pcm)
            self.assertGreater(len(samples), 47000)
            crossings = sum(a <= 0 < b for a, b in zip(samples, samples[1:]))
            frequency = crossings * 48000 / len(samples)
            self.assertLess(abs(frequency - 440 * 1.02), 12)

    def test_real_logo_is_visible_and_source_audio_remains(self):
        with tempfile.TemporaryDirectory() as folder:
            source = str(Path(folder) / "source.mkv")
            logo = str(Path(folder) / "red logo.png")
            dest = str(Path(folder) / "branded.flv")
            subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi",
                            "-i", "color=black:size=640x360:rate=25", "-f", "lavfi", "-i",
                            "sine=frequency=440:sample_rate=48000", "-t", "2", "-c:v", "mpeg4",
                            "-c:a", "aac", source], check=True, capture_output=True, timeout=45)
            subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi",
                            "-i", "color=red:size=160x80", "-frames:v", "1", logo],
                           check=True, capture_output=True, timeout=30)
            with patch.dict(os.environ, {"STREAM_LOGO_PATH": logo, "STREAM_LOGO_OPACITY": "100",
                                         "STREAM_LOGO_WIDTH": "160", "STREAM_LOGO_MARGIN": "24",
                                         "STREAM_LOGO_POSITION": "top-right"}):
                proc, log, path = runtime.launch(source, "", dest, str(Path(folder) / "branded.log"))
            try:
                proc.wait(timeout=45)
                self.assertEqual(proc.returncode, 0, runtime.safe_tail(path))
            finally:
                runtime.stop_process(proc)
                log.close()
            pixel = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", dest,
                                    "-vf", "crop=2:2:1200:60,scale=1:1,format=rgb24", "-frames:v", "1",
                                    "-f", "rawvideo", "pipe:1"], check=True, capture_output=True, timeout=20).stdout
            self.assertEqual(len(pixel), 3)
            self.assertGreater(pixel[0], 180)
            self.assertLess(pixel[1], 50)
            self.assertLess(pixel[2], 50)
            probe = subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-of", "json", dest],
                                   check=True, capture_output=True, text=True, timeout=15)
            self.assertTrue(any(s["codec_type"] == "audio" and s["codec_name"] == "aac"
                                for s in json.loads(probe.stdout)["streams"]))

    def test_real_encoder_with_and_without_audio(self):
        with tempfile.TemporaryDirectory() as folder:
            for with_audio in (False, True):
                source = str(Path(folder) / f"input_{with_audio}.mkv")
                dest = str(Path(folder) / f"output_{with_audio}.flv")
                generate = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi",
                            "-i", "testsrc2=size=640x360:rate=25"]
                if with_audio:
                    generate += ["-f", "lavfi", "-i", "sine=frequency=440:sample_rate=44100"]
                generate += ["-t", "3", "-c:v", "mpeg4", "-q:v", "8"]
                if with_audio:
                    generate += ["-c:a", "aac"]
                subprocess.run(generate + [source], check=True, capture_output=True, timeout=45)
                proc, log, path = runtime.launch(source, "", dest, str(Path(folder) / "encode.log"))
                try:
                    proc.wait(timeout=45)
                    self.assertEqual(proc.returncode, 0, runtime.safe_tail(path))
                    probe = subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-of", "json", dest],
                                           check=True, capture_output=True, text=True, timeout=15)
                    streams = json.loads(probe.stdout)["streams"]
                    video = next(s for s in streams if s["codec_type"] == "video")
                    self.assertEqual((video["codec_name"], video["width"], video["height"]), ("h264", 1280, 720))
                    self.assertEqual(video["r_frame_rate"], "30/1")
                    self.assertEqual(any(s["codec_name"] == "aac" for s in streams), with_audio)
                    # The pipe reader receives the final block asynchronously.
                    deadline = time.monotonic() + 2
                    while not proc.stream_progress.snapshot()["received"] and time.monotonic() < deadline:
                        time.sleep(.01)
                    self.assertTrue(proc.stream_progress.snapshot()["received"])
                finally:
                    runtime.stop_process(proc)
                    log.close()


if __name__ == "__main__":
    unittest.main()
