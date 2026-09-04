"""In-process publish/subscribe behind the SSE route.

Scope, stated plainly: this is per-process. Under a multi-worker gunicorn
deployment a client connected to worker A will not receive an event published by
worker B, so the browser client treats SSE as an optimisation and always keeps a
polling fallback running (`twin-stream.js`). Making this cross-process needs
Redis, which the host app does not currently run.
"""

import json
import queue
import threading
from datetime import datetime

_LOCK = threading.Lock()
_SUBSCRIBERS = []

# Bounded so a browser tab that stops reading cannot grow a queue without limit.
_QUEUE_MAX = 32


class _Subscriber(object):
    __slots__ = ('queue', 'city')

    def __init__(self, city):
        self.queue = queue.Queue(maxsize=_QUEUE_MAX)
        self.city = city


def subscribe(city=None):
    sub = _Subscriber(city)
    with _LOCK:
        _SUBSCRIBERS.append(sub)
    return sub


def unsubscribe(sub):
    with _LOCK:
        try:
            _SUBSCRIBERS.remove(sub)
        except ValueError:
            pass


def publish(city_slug, event, payload):
    """Fan out one event. Never blocks and never raises into the caller."""
    message = {
        'event': event,
        'city': city_slug,
        'payload': payload,
        'at': datetime.utcnow().isoformat() + 'Z',
    }
    with _LOCK:
        targets = [s for s in _SUBSCRIBERS if s.city in (None, city_slug)]
    for sub in targets:
        try:
            sub.queue.put_nowait(message)
        except queue.Full:
            # A stalled reader loses events rather than slowing the compute pass.
            pass


def format_sse(message):
    return "event: %s\ndata: %s\n\n" % (message['event'],
                                        json.dumps(message, separators=(',', ':')))


def subscriber_count():
    with _LOCK:
        return len(_SUBSCRIBERS)
