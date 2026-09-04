"""`IngestAdapter` - the single contract every external data source obeys.

Principle C1: never take the app down. `run()` catches everything, falls back to
the most recent cached payload when it can, and returns a result object whose
`status` says honestly what happened. Callers branch on `status`; they never
have to write a try/except.

Principle C7: every attempt writes a `TwinDataSnapshot`, and a failure to write
that audit row must never destroy the good data that was just fetched.
"""

import hashlib
import json
import os
import time
from datetime import datetime

import requests

from .. import config as twin_config

OK = 'ok'
CACHED = 'cached'      # upstream failed, a usable cached payload was served
DEGRADED = 'degraded'  # a partial answer
FAILED = 'failed'      # nothing usable


class IngestResult(object):
    __slots__ = ('source_key', 'status', 'data', 'error', 'latency_ms', 'records', 'fetched_at')

    def __init__(self, source_key, status, data=None, error=None,
                 latency_ms=0, records=0, fetched_at=None):
        self.source_key = source_key
        self.status = status
        self.data = data
        self.error = error
        self.latency_ms = latency_ms
        self.records = records
        self.fetched_at = fetched_at or datetime.utcnow()

    @property
    def ok(self):
        return self.status in (OK, CACHED, DEGRADED) and self.data is not None

    @property
    def degraded(self):
        """True when the score built on this data should be flagged to the operator."""
        return self.status in (CACHED, DEGRADED, FAILED)

    def to_dict(self):
        return {
            'source': self.source_key,
            'status': self.status,
            'error': self.error,
            'latency_ms': self.latency_ms,
            'records': self.records,
            'fetched_at': self.fetched_at.isoformat() + 'Z',
        }

    def __repr__(self):
        return "<IngestResult %s %s>" % (self.source_key, self.status)


class IngestAdapter(object):
    """Base class. Subclasses implement `fetch()` and set `source_key`/`ttl_seconds`."""

    source_key = 'base'
    ttl_seconds = 900
    retries = 1
    # Adapters whose payload is large and slow to rebuild keep serving stale
    # data well past the TTL rather than showing the operator nothing.
    stale_grace_seconds = 6 * 3600

    def __init__(self, cache_dir=None, timeout=None):
        self.cache_dir = cache_dir or twin_config.CACHE_DIR
        self.timeout = timeout or twin_config.HTTP_TIMEOUT_S

    # -- to implement -------------------------------------------------------
    def fetch(self, **kwargs):
        """Do the network call. May raise; `run()` is what catches."""
        raise NotImplementedError

    def cache_key(self, **kwargs):
        payload = json.dumps(kwargs, sort_keys=True, default=str)
        digest = hashlib.sha1(payload.encode('utf-8')).hexdigest()[:16]
        return "%s_%s" % (self.source_key, digest)

    # -- the contract -------------------------------------------------------
    def run(self, force=False, **kwargs):
        key = self.cache_key(**kwargs)

        if not force:
            cached = self._read_cache(key, self.ttl_seconds)
            if cached is not None:
                return IngestResult(self.source_key, OK, data=cached,
                                    records=_count(cached))

        started = time.time()
        last_error = None
        for attempt in range(self.retries + 1):
            try:
                data = self.fetch(**kwargs)
                latency = int((time.time() - started) * 1000)
                if data is None:
                    last_error = 'source returned no data'
                    continue
                self._write_cache(key, data)
                return IngestResult(self.source_key, OK, data=data,
                                    latency_ms=latency, records=_count(data))
            except Exception as exc:  # noqa: BLE001 - C1: never propagate
                last_error = "%s: %s" % (type(exc).__name__, exc)

        latency = int((time.time() - started) * 1000)

        # Upstream is down. Stale data, clearly labelled, beats a blank map -
        # but the caller is told it is stale so the cell can be drawn degraded.
        stale = self._read_cache(key, self.ttl_seconds + self.stale_grace_seconds)
        if stale is not None:
            return IngestResult(self.source_key, CACHED, data=stale,
                                error=last_error, latency_ms=latency,
                                records=_count(stale))

        return IngestResult(self.source_key, FAILED, data=None,
                            error=last_error, latency_ms=latency)

    def run_cached_only(self, **kwargs):
        """Serve from disk cache without ever touching the network.

        The lazy layers (`/water`, `/cameras`) are Overpass-backed and a cold
        query can take two minutes. A user request must never wait on that, so
        the routes read cache-only and report `pending` when the scheduler has
        not warmed it yet - an honest "not ingested" beats a hung dashboard.
        """
        key = self.cache_key(**kwargs)
        data = self._read_cache(key, self.ttl_seconds + self.stale_grace_seconds)
        if data is None:
            return IngestResult(self.source_key, FAILED, data=None,
                                error='not yet ingested')
        fresh = self._read_cache(key, self.ttl_seconds) is not None
        return IngestResult(self.source_key, OK if fresh else CACHED,
                            data=data, records=_count(data))

    # -- http ---------------------------------------------------------------
    def get_json(self, url, params=None, headers=None):
        response = requests.get(url, params=params, timeout=self.timeout,
                                headers=headers or {'User-Agent': _USER_AGENT})
        response.raise_for_status()
        return response.json()

    def post_form(self, url, data, headers=None):
        response = requests.post(url, data=data, timeout=self.timeout,
                                 headers=headers or {'User-Agent': _USER_AGENT})
        response.raise_for_status()
        return response.json()

    # -- disk cache ---------------------------------------------------------
    def _cache_path(self, key):
        return os.path.join(self.cache_dir, key + '.json')

    def _read_cache(self, key, max_age_seconds):
        path = self._cache_path(key)
        try:
            age = time.time() - os.path.getmtime(path)
            if age > max_age_seconds:
                return None
            with open(path, 'r') as handle:
                return json.load(handle)
        except (OSError, ValueError):
            return None

    def _write_cache(self, key, data):
        try:
            os.makedirs(self.cache_dir, exist_ok=True)
            path = self._cache_path(key)
            # Write-then-rename: a crash mid-write must not leave a truncated
            # file that then reads back as "no cache" forever.
            tmp = path + '.tmp'
            with open(tmp, 'w') as handle:
                json.dump(data, handle, separators=(',', ':'))
            os.replace(tmp, path)
        except (OSError, TypeError, ValueError):
            pass  # a cache write failing is never worth losing the payload over


def _count(data):
    if isinstance(data, list):
        return len(data)
    if isinstance(data, dict):
        for key in ('features', 'elements', 'items', 'results'):
            value = data.get(key)
            if isinstance(value, list):
                return len(value)
        return 1
    return 0


_USER_AGENT = 'SentinelAI-DigitalTwin/1.0 (+urban resilience; contact via app)'


def record_snapshot(db, models, city_id, result):
    """Write the audit row. Never lets an audit failure destroy good data (C7)."""
    try:
        snapshot = models.TwinDataSnapshot(
            city_id=city_id,
            source_key=result.source_key,
            status=result.status,
            latency_ms=result.latency_ms or 0,
            records_ingested=result.records or 0,
            error_message=(result.error or None),
        )
        db.session.add(snapshot)
    except Exception:  # noqa: BLE001
        db.session.rollback()
