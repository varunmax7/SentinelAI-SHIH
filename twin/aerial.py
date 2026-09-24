"""A satellite crop of one exact point - the guaranteed floor for "show me
this place".

Street-level coverage in both modelled cities is patchy: measured across
random Hyderabad cells, a large share have no KartaView or Mapillary
photograph within range even after the widened ring, and those cells fall
through to the city webcam - which is the same two frames everywhere in
Hyderabad and one frame everywhere in Bengaluru. That is how an operator ends
up clicking eight different locations and seeing the same picture eight times.

Esri World Imagery is already this app's default basemap, already attributed,
and its `export` endpoint renders an arbitrary bounding box as a single JPEG
with no key. Asking it for the box around one cell produces an image that is
unambiguously of that cell and different for every cell - at the cost of being
looked straight down at from orbit rather than from the street, which the UI
says on every frame.

**The server builds a URL and never fetches it.** The browser loads the image
straight from Esri, exactly as it already loads the basemap tiles from the
same service, so this adds no bandwidth, no proxying and no new failure mode.
"""

import math

from . import config as twin_config

EXPORT_URL = ('https://server.arcgisonline.com/arcgis/rest/services/'
              'World_Imagery/MapServer/export')
ATTRIBUTION = '(c) Esri, Maxar, Earthstar Geographics'


def crop_url(lat, lon, span_m=None, size_px=None):
    """A square Esri World Imagery crop centred on (lat, lon).

    `None` for a point that is not finite - a caller must never be handed a
    URL built from nonsense coordinates.
    """
    try:
        lat, lon = float(lat), float(lon)
    except (TypeError, ValueError):
        return None
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
        return None

    span_m = span_m or twin_config.AERIAL_SPAN_M
    size_px = size_px or twin_config.AERIAL_SIZE_PX

    half_lat = (span_m / 2.0) / 111320.0
    # Longitude degrees shrink with latitude; without this the box is a
    # rectangle on the ground and the crop is stretched east-west.
    cos_lat = max(0.2, math.cos(math.radians(lat)))
    half_lon = half_lat / cos_lat

    bbox = '%.6f,%.6f,%.6f,%.6f' % (lon - half_lon, lat - half_lat,
                                    lon + half_lon, lat + half_lat)
    return ('%s?bbox=%s&bboxSR=4326&imageSR=3857&size=%d,%d&format=jpg&f=image'
            % (EXPORT_URL, bbox, size_px, size_px))


def crop_for_point(lat, lon, label=None):
    """The same crop, shaped like every other image in the imagery payload.

    `captured_at` is deliberately absent: Esri publishes World Imagery as a
    mosaic without a per-tile capture date on this endpoint, and inventing one
    - or letting the UI's "date unknown" read as "recent" - would be worse
    than saying nothing. The UI labels this tier as aerial, not live.
    """
    url = crop_url(lat, lon)
    if not url:
        return None
    return {
        'provider': 'Esri World Imagery',
        'licence': ATTRIBUTION,
        'id': 'aerial:%.5f,%.5f' % (lat, lon),
        'lat': lat,
        'lon': lon,
        'heading': None,
        'title': label or 'Satellite view of this point',
        'captured_at': None,
        'thumb_url': url,
        'full_url': crop_url(lat, lon, size_px=min(1024, twin_config.AERIAL_SIZE_PX * 2)),
        'page_url': None,
        'distance_m': 0.0,
        'span_m': twin_config.AERIAL_SPAN_M,
        'live': False,
        'aerial': True,
    }
