"""RainViewer precipitation radar.

Keyless and manifest-driven: the manifest names the current frame paths, and the
tile URL has to be rebuilt from it every few minutes because old frames expire.
Attribution `RainViewer.com`.
"""

from .base import IngestAdapter

MANIFEST_URL = 'https://api.rainviewer.com/public/weather-maps.json'


class RainViewerAdapter(IngestAdapter):
    source_key = 'rainviewer'
    ttl_seconds = 8 * 60

    def fetch(self, **kwargs):
        payload = self.get_json(MANIFEST_URL)
        host = payload.get('host') or 'https://tilecache.rainviewer.com'
        radar = payload.get('radar') or {}
        past = radar.get('past') or []
        nowcast = radar.get('nowcast') or []
        if not past and not nowcast:
            return None

        frames = [{'time': f.get('time'), 'path': f.get('path'), 'kind': 'past'} for f in past]
        frames += [{'time': f.get('time'), 'path': f.get('path'), 'kind': 'nowcast'} for f in nowcast]

        latest = past[-1] if past else nowcast[0]
        return {
            'host': host,
            'frames': frames,
            'latest_path': latest.get('path'),
            'latest_time': latest.get('time'),
            # colour scheme 2, smoothed, with snow colours - the combination
            # that reads best over dark satellite imagery.
            'tile_template': '%s%s/256/{z}/{x}/{y}/2/1_1.png' % (host, latest.get('path')),
            'attribution': 'RainViewer.com',
        }
