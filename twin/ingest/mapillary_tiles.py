"""Mapillary image discovery via vector tiles, not the Graph API's bbox search.

`streetview.py::_mapillary()` calls the documented `/images?bbox=` endpoint,
and it reliably returns zero rows for both Hyderabad and Bengaluru -
**verified directly** with a real token: HTTP 200, `{"data": []}`, at every
radius from 500 m up to the API's own maximum allowed bbox area. That is a
known unreliability of that specific search endpoint, not a coverage gap or
a request bug. Mapillary's own web app does not use that endpoint to decide
what to draw - it reads the same vector tiles this module reads.

**Hand-rolled Mapbox Vector Tile (MVT) decoder, not a dependency.** MVT is
protobuf with a small, stable, public schema
(github.com/mapbox/vector-tile-spec) - decoding one point layer's geometry
and a couple of tag values is a few dozen lines of varint parsing, not worth
a new package for. Only what this module needs is implemented: point
geometry (`MoveTo` only), scalar tag values. A line/polygon layer, or one
using GeomType other than POINT, is out of scope and skipped, not
mis-parsed.
"""

import math
import struct

import requests

from .. import config as twin_config

TILE_URL = 'https://tiles.mapillary.com/maps/vtp/mly1_public/2/%d/%d/%d'
GRAPH_IMAGES_URL = 'https://graph.mapillary.com/images'
ZOOM = 14
LAYER_NAME = 'image'
MAX_IMAGES = 40


# --- slippy-map tile math ------------------------------------------------------
def lonlat_to_tile(lon, lat, zoom):
    lat_rad = math.radians(lat)
    n = 2.0 ** zoom
    x = int((lon + 180.0) / 360.0 * n)
    y = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
    return x, y


def tile_bounds(x, y, zoom):
    n = 2.0 ** zoom
    lon_min = x / n * 360.0 - 180.0
    lon_max = (x + 1) / n * 360.0 - 180.0
    lat_max = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / n))))
    lat_min = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * (y + 1) / n))))
    return lon_min, lat_min, lon_max, lat_max


# --- minimal protobuf reader ----------------------------------------------------
def _read_varint(buf, pos):
    result = 0
    shift = 0
    while True:
        byte = buf[pos]
        pos += 1
        result |= (byte & 0x7F) << shift
        if not (byte & 0x80):
            return result, pos
        shift += 7


def _zigzag_decode(n):
    return (n >> 1) ^ (-(n & 1))


def _read_fields(buf):
    """Yield (field_number, wire_type, value) for one protobuf message.

    `value` is an int for a varint field, raw bytes for a length-delimited
    one - the two wire types every part of the MVT schema this module reads
    actually uses.
    """
    pos, length = 0, len(buf)
    while pos < length:
        tag, pos = _read_varint(buf, pos)
        field_no, wire_type = tag >> 3, tag & 0x7
        if wire_type == 0:
            value, pos = _read_varint(buf, pos)
        elif wire_type == 2:
            size, pos = _read_varint(buf, pos)
            value = buf[pos:pos + size]
            pos += size
        elif wire_type == 5:
            value, pos = buf[pos:pos + 4], pos + 4
        elif wire_type == 1:
            value, pos = buf[pos:pos + 8], pos + 8
        else:
            return  # an unknown wire type means the buffer is not trustworthy
        yield field_no, wire_type, value


def _read_packed_varints(buf):
    out, pos = [], 0
    while pos < len(buf):
        value, pos = _read_varint(buf, pos)
        out.append(value)
    return out


def _decode_value(buf):
    """One `Layer.Value` message -> its Python scalar."""
    for field_no, _wt, value in _read_fields(buf):
        if field_no == 1:
            return value.decode('utf-8', errors='replace')
        if field_no == 2:
            return struct.unpack('<f', value)[0]
        if field_no == 3:
            return struct.unpack('<d', value)[0]
        if field_no == 4:
            return value
        if field_no == 5:
            return value
        if field_no == 6:
            return _zigzag_decode(value)
        if field_no == 7:
            return bool(value)
    return None


def _decode_point_geometry(buf):
    """A `MoveTo` command's first (and only, for a point) coordinate pair,

    delta + zigzag encoded, in tile-local units. `None` for anything that
    is not a simple single-point MoveTo - see the module docstring.
    """
    pos, x, y = 0, 0, 0
    if not buf:
        return None
    cmd_int, pos = _read_varint(buf, pos)
    cmd_id, count = cmd_int & 0x7, cmd_int >> 3
    if cmd_id != 1 or count < 1:
        return None
    dx, pos = _read_varint(buf, pos)
    dy, pos = _read_varint(buf, pos)
    x += _zigzag_decode(dx)
    y += _zigzag_decode(dy)
    return x, y


def _find_layer(tile_buf, want_name):
    """The named `Layer` message's own bytes, unwrapped from the top-level

    `Tile` message (`layers` is field 3, repeated, length-delimited) - a
    tile the size Mapillary serves here typically carries several layers
    ("sequence", "image", ...), and `_decode_layer` needs to be handed one
    layer's bytes, never the whole tile's.
    """
    for field_no, wire_type, value in _read_fields(tile_buf):
        if field_no != 3 or wire_type != 2:
            continue
        layer = _decode_layer(value, want_name)
        if layer is not None:
            return layer
    return None


def _decode_layer(buf, want_name):
    name, extent, keys, values, feature_bufs = None, 4096, [], [], []
    for field_no, _wt, value in _read_fields(buf):
        if field_no == 1:
            name = value.decode('utf-8', errors='replace')
        elif field_no == 3:
            keys.append(value.decode('utf-8', errors='replace'))
        elif field_no == 4:
            values.append(_decode_value(value))
        elif field_no == 5:
            extent = value
        elif field_no == 2:
            feature_bufs.append(value)
    if name != want_name:
        return None

    features = []
    for feat_buf in feature_bufs:
        tags, geometry = [], None
        for f_no, _wt, val in _read_fields(feat_buf):
            if f_no == 2:
                tags = _read_packed_varints(val)
            elif f_no == 4:
                geometry = _decode_point_geometry(val)
        if geometry is None:
            continue
        props = {}
        for i in range(0, len(tags) - 1, 2):
            key_idx, val_idx = tags[i], tags[i + 1]
            if key_idx < len(keys) and val_idx < len(values):
                props[keys[key_idx]] = values[val_idx]
        features.append({'geometry': geometry, 'properties': props})
    return {'extent': extent, 'features': features}


# --- public entry point ---------------------------------------------------------
def fetch_tile_images(lat, lon, zoom=None, timeout=None):
    """Every image point Mapillary's vector tiles carry for the tile

    covering (lat, lon). `[]` on any failure, a missing token, or an empty
    tile - the same "a missing input hides the layer" contract every
    adapter in this package follows, never an exception upward.
    """
    token = twin_config.MAPILLARY_TOKEN
    if not token:
        return []
    zoom = zoom or ZOOM
    timeout = timeout or twin_config.STREETVIEW_TIMEOUT_S
    x, y = lonlat_to_tile(lon, lat, zoom)

    try:
        response = requests.get(TILE_URL % (zoom, x, y),
                                params={'access_token': token}, timeout=timeout)
        response.raise_for_status()
        layer = _find_layer(response.content, LAYER_NAME)
    except Exception:  # noqa: BLE001 - a malformed/unreachable tile degrades, never raises
        return []
    if not layer or not layer['features']:
        return []

    lon_min, lat_min, lon_max, lat_max = tile_bounds(x, y, zoom)
    extent = layer['extent'] or 4096
    points = []
    for feature in layer['features'][:MAX_IMAGES]:
        tx, ty = feature['geometry']
        flon = lon_min + (tx / extent) * (lon_max - lon_min)
        flat = lat_max - (ty / extent) * (lat_max - lat_min)
        props = feature['properties']
        image_id = props.get('id')
        if image_id is None:
            continue
        points.append({
            'id': str(image_id), 'lat': flat, 'lon': flon,
            'heading': props.get('compass_angle'),
            'captured_at': props.get('captured_at'),
        })

    thumbs = _fetch_thumbnails(token, [p['id'] for p in points], timeout)
    out = []
    for point in points:
        thumb = thumbs.get(point['id'])
        # No image without a real thumbnail URL is returned. The tile gives
        # accurate geometry for every point regardless; a thumbnail needs
        # this one extra Graph-by-ID call, which - as of building this -
        # returned nothing for every id tried, including a direct single-id
        # lookup that came back "does not exist, cannot be loaded due to
        # missing permissions, or does not support this operation". That
        # reads like a token scope issue (max.md's own notes flag Mapillary
        # as needing "Graph read scope"), not a bug in the id or the call
        # shape - but rather than guess and risk a broken <img src> in the
        # drawer, an image with no confirmed thumbnail is simply omitted.
        if not thumb:
            continue
        out.append({
            'provider': 'Mapillary', 'licence': 'CC BY-SA', 'id': point['id'],
            'lat': point['lat'], 'lon': point['lon'], 'heading': point['heading'],
            'captured_at': point['captured_at'],
            'thumb_url': thumb, 'full_url': thumb,
            'page_url': 'https://www.mapillary.com/app/?pKey=%s' % point['id'],
            'live': False,
        })
    return out


def _fetch_thumbnails(token, image_ids, timeout):
    """One batched Graph API call for every id the tile carried, not one

    call per image - the tile gives geometry and tags, but never a signed
    thumbnail URL, so this is the one Graph API call left in the whole
    discovery path (image-by-id lookup, not the unreliable bbox search).
    """
    if not image_ids:
        return {}
    try:
        response = requests.get(GRAPH_IMAGES_URL, params={
            'access_token': token,
            'image_ids': ','.join(image_ids),
            'fields': 'id,thumb_1024_url',
        }, timeout=timeout)
        response.raise_for_status()
        payload = response.json()
    except Exception:  # noqa: BLE001
        return {}
    return {
        str(row.get('id')): row.get('thumb_1024_url')
        for row in payload.get('data') or []
        if row.get('id') is not None
    }
