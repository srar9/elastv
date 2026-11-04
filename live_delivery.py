"""Bounded, process-local media preparation. No re-encoding, ads or P2P."""
import threading
import time
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from queue import Queue, Full


@dataclass(frozen=True)
class Media:
    body: bytes
    content_type: str


class MediaCache:
    def __init__(self, max_bytes=48 * 1024 * 1024, ttl=45, now=time.monotonic):
        self.max_bytes, self.ttl, self.now = max_bytes, ttl, now
        self.items, self.pending = OrderedDict(), {}
        self.scheduled = set()
        self.size = 0
        self.lock = threading.Lock()
        self.pool = ThreadPoolExecutor(max_workers=3, thread_name_prefix="live-prefetch")
        self.slots = threading.BoundedSemaphore(6)

    def _cached(self, key):
        item = self.items.get(key)
        if item is None:
            return None
        expiry, value = item
        if expiry <= self.now():
            self.size -= len(value.body)
            del self.items[key]
            return None
        self.items.move_to_end(key)
        return value

    def get(self, key, loader):
        with self.lock:
            cached = self._cached(key)
            if cached is not None:
                return cached
            ticket = self.pending.get(key)
            owner = ticket is None
            if owner:
                ticket = {"event": threading.Event()}
                self.pending[key] = ticket
        if not owner:
            if not ticket["event"].wait(12):
                raise TimeoutError("MEDIA_WAIT_TIMEOUT")
            if "error" in ticket:
                raise OSError("MEDIA_DOWNLOAD_FAILED") from None
            return ticket["value"]
        try:
            value = loader()
            with self.lock:
                if len(value.body) <= self.max_bytes:
                    while self.items and self.size + len(value.body) > self.max_bytes:
                        _, (_, old) = self.items.popitem(last=False)
                        self.size -= len(old.body)
                    self.items[key] = (self.now() + self.ttl, value)
                    self.size += len(value.body)
                ticket["value"] = value
            return value
        except Exception:
            ticket["error"] = True
            raise
        finally:
            with self.lock:
                self.pending.pop(key, None)
                ticket["event"].set()

    def prepare(self, key, loader):
        with self.lock:
            if self._cached(key) is not None or key in self.pending or key in self.scheduled:
                return
            if not self.slots.acquire(blocking=False):
                return
            self.scheduled.add(key)
        def run():
            try:
                self.get(key, loader)
            except Exception:
                pass  # Foreground request can retry; never store a partial file.
            finally:
                with self.lock:
                    self.scheduled.discard(key)
                self.slots.release()
        try:
            self.pool.submit(run)
        except RuntimeError:
            with self.lock:
                self.scheduled.discard(key)
            self.slots.release()

    def close(self):
        self.pool.shutdown(wait=True)


def complete_media(response, limit=19000000, deadline=10, now=time.monotonic):
    """Accept only complete files so a truncated download never poisons cache."""
    if response.status_code != 200:
        raise OSError("MEDIA_HTTP")
    content_type = response.headers.get("Content-Type", "application/octet-stream")
    if any(t in content_type.lower() for t in ("html", "json", "javascript", "svg")):
        raise OSError("INVALID_MEDIA_TYPE")
    start, parts, size = now(), [], 0
    for chunk in response.iter_content(chunk_size=65536):
        if not chunk:
            continue
        size += len(chunk)
        if size > limit or now() - start > deadline:
            raise OSError("MEDIA_DOWNLOAD_LIMIT")
        parts.append(chunk)
    expected = response.headers.get("Content-Length")
    if not size or (expected and not response.headers.get("Content-Encoding") and size != int(expected)):
        raise OSError("INCOMPLETE_MEDIA")
    return Media(b"".join(parts), content_type)


class Reports:
    """Slow diagnostic storage must never block delivery of video bytes."""
    def __init__(self, record, capacity=32):
        self.record = record
        self.queue = Queue(maxsize=capacity)
        self.thread = None
        self.lock = threading.Lock()

    def submit(self, *args):
        with self.lock:
            if self.thread is None:
                self.thread = threading.Thread(target=self._run, daemon=True, name="live-reports")
                self.thread.start()
        try:
            self.queue.put_nowait(args)
        except Full:
            pass

    def _run(self):
        while True:
            args = self.queue.get()
            try:
                self.record(*args)
            except Exception:
                pass
            finally:
                self.queue.task_done()
