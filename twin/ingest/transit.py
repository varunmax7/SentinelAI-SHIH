"""GTFS-Realtime vehicle positions, per city.

No stable public GTFS-Realtime feed exists for Hyderabad or Bengaluru as of
writing (checked while building this - TSRTC and BMTC do not publish one).
This adapter is complete and will start returning vehicles the moment
`TWIN_GTFS_RT_URLS` names one; until then it is honestly empty, not broken -
the same "the layer appears only when configured" rule every keyed source in
this package follows.

`gtfs-realtime-bindings` is imported lazily, inside `fetch()`, not at module
level: it is an optional dependency (see requirements.txt's own comment on
this), and importing it eagerly would mean a deployment that never
configures transit at all still has to have the package installed just for
this module to load.
"""

from .. import config as twin_config
from .base import IngestAdapter


class TransitAdapter(IngestAdapter):
    source_key = 'gtfs_rt_vehicles'
    ttl_seconds = 2 * 60  # vehicles move; a stale minute here is a wrong minute

    def fetch(self, city_slug=None, **kwargs):
        url = (twin_config.GTFS_RT_URLS or {}).get(city_slug)
        if not url:
            return None

        try:
            from google.transit import gtfs_realtime_pb2
        except ImportError:
            # Not installed and nothing configured to need it - the common
            # case. Once a deployment sets TWIN_GTFS_RT_URLS it also needs
            # `pip install gtfs-realtime-bindings`; that pairing is the
            # honest failure mode, not a silent empty layer.
            raise RuntimeError(
                'TWIN_GTFS_RT_URLS is set for %r but gtfs-realtime-bindings '
                'is not installed' % city_slug)

        headers = (twin_config.GTFS_RT_HEADERS or {}).get(city_slug) or {}
        response_headers = dict(headers, **{'User-Agent': 'SentinelAI-DigitalTwin/1.0'})
        import requests
        response = requests.get(url, headers=response_headers, timeout=self.timeout)
        response.raise_for_status()

        feed = gtfs_realtime_pb2.FeedMessage()
        feed.ParseFromString(response.content)

        vehicles = []
        for entity in feed.entity:
            if not entity.HasField('vehicle'):
                continue
            v = entity.vehicle
            if not v.HasField('position'):
                continue
            speed_kmh = (v.position.speed * 3.6) if v.position.HasField('speed') else None
            vehicles.append({
                'external_id': entity.id,
                'route_id': v.trip.route_id if v.HasField('trip') else None,
                'lat': v.position.latitude,
                'lon': v.position.longitude,
                'speed_kmh': speed_kmh,
                'stalled': speed_kmh is not None and speed_kmh < twin_config.TRANSIT_STALL_SPEED_KMH,
                'observed_at': v.timestamp if v.HasField('timestamp') else None,
            })
        return vehicles or None
