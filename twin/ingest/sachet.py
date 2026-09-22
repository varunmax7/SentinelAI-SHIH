"""NDMA SACHET - India's official CAP alert feed.

Keyless, public domain, government-authoritative. This is the primary external
incident source: every other feed in this module is global and coarse, while
SACHET publishes state-scoped alerts written by the IMD and state disaster
management centres for exactly the two cities the twin models.

Three documents per alert, and they do not have the same shape:

  1. the state RSS feed              - plain RSS, an <item> per alert
  2. the CAP 1.2 document            - **namespaced** `cap:` throughout
  3. the polygon document            - **not namespaced**, a bare <alert>

Matching a bare <alert> against the CAP document finds nothing and fails
silently; so does matching `cap:polygon` against the polygon document. They are
genuinely different documents from the same server.
"""

import re
from datetime import datetime, timezone

from lxml import etree

from .base import IngestAdapter

FEED_URL = 'https://sachet.ndma.gov.in/cap_public_website/rss/rss_%s.xml'
CAP_URL = 'https://sachet.ndma.gov.in/cap_public_website/FetchXMLFile?identifier=%s'
POLYGON_URL = 'https://sachet.ndma.gov.in/cap_public_website/FetchPolygonXMLFile?identifier=%s'

CAP_NS = {'cap': 'urn:oasis:names:tc:emergency:cap:1.2'}

# CAP severity/certainty vocabularies mapped onto the twin's own priority and
# confidence scales, so an official alert and a citizen report land on the same
# axis. Deliberately a table, not a formula: these are the CAP spec's fixed
# enumerations and the mapping is a judgement that should be arguable.
SEVERITY_TO_PRIORITY = {
    'Extreme': 'critical',
    'Severe': 'high',
    'Moderate': 'medium',
    'Minor': 'low',
    'Unknown': 'low',
}

CERTAINTY_TO_CONFIDENCE = {
    'Observed': 1.0,
    'Likely': 0.75,
    'Possible': 0.5,
    'Unlikely': 0.25,
    'Unknown': 0.4,
}


def _text(node, path, namespaces=CAP_NS):
    found = node.find(path, namespaces)
    if found is None or found.text is None:
        return None
    value = found.text.strip()
    return value or None


def parse_cap_datetime(value):
    """Parse a CAP timestamp, keeping its offset.

    SACHET stamps everything `+05:30`. Treating these as UTC shifts every alert
    window by five and a half hours, which silently expires live alerts and
    revives dead ones.
    """
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.strip())
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).replace(tzinfo=None)


class SachetFeedAdapter(IngestAdapter):
    """One state's RSS index of current alerts."""

    source_key = 'sachet_feed'
    # Alerts are time-critical and the feed is small; five minutes is the
    # shortest useful poll without hammering a government server.
    ttl_seconds = 300

    def cache_key(self, state=None, **kwargs):
        # Keyed on the state name alone. The base implementation hashes every
        # kwarg, so passing anything whose repr embeds a memory address would
        # change the key on every restart and defeat the cache entirely.
        return super(SachetFeedAdapter, self).cache_key(state=state)

    def fetch(self, state=None, **kwargs):
        import requests

        response = requests.get(FEED_URL % state, timeout=self.timeout,
                                headers={'User-Agent': 'SentinelAI-DigitalTwin/1.0'})
        response.raise_for_status()
        root = etree.fromstring(response.content)

        items = []
        for item in root.findall('.//item'):
            guid = _text(item, 'guid', None)
            link = _text(item, 'link', None)
            if not guid and link:
                match = re.search(r'identifier=([\w-]+)', link)
                guid = match.group(1) if match else None
            if not guid:
                continue
            items.append({
                'source_uid': guid,
                'title': _text(item, 'title', None),
                'category': _text(item, 'category', None),
                'link': link,
                'author': _text(item, 'author', None),
                'pub_date': _text(item, 'pubDate', None),
                'state': state,
            })
        return items


class SachetCapAdapter(IngestAdapter):
    """One CAP 1.2 alert document.

    Cached for a day: a given identifier's document is immutable. Revisions
    arrive as a *new* identifier carrying `msgType=Update` and a
    `cap:references` pointer at the one it supersedes.
    """

    source_key = 'sachet_cap'
    ttl_seconds = 24 * 3600
    stale_grace_seconds = 7 * 24 * 3600

    def cache_key(self, identifier=None, **kwargs):
        return super(SachetCapAdapter, self).cache_key(identifier=identifier)

    def fetch(self, identifier=None, **kwargs):
        import requests

        response = requests.get(CAP_URL % identifier, timeout=self.timeout,
                                headers={'User-Agent': 'SentinelAI-DigitalTwin/1.0'})
        response.raise_for_status()
        return parse_cap_document(response.content, identifier)


def parse_cap_document(payload, source_uid=None):
    """CAP XML bytes -> a flat dict. Returns None if it is not a CAP alert."""
    root = etree.fromstring(payload)
    info = root.find('cap:info', CAP_NS)
    if info is None:
        return None

    polygon_url = None
    for parameter in info.findall('cap:parameter', CAP_NS):
        name = _text(parameter, 'cap:valueName')
        if name and 'polygon' in name.lower():
            polygon_url = _text(parameter, 'cap:value')

    area = info.find('cap:area', CAP_NS)
    district_codes = []
    area_desc = None
    if area is not None:
        area_desc = _text(area, 'cap:areaDesc')
        for geocode in area.findall('cap:geocode', CAP_NS):
            name = _text(geocode, 'cap:valueName') or ''
            value = _text(geocode, 'cap:value')
            if value and 'district' in name.lower():
                district_codes.append(value)

    severity = _text(info, 'cap:severity')
    certainty = _text(info, 'cap:certainty')

    # `cap:references` is "sender,identifier,sent" - possibly several,
    # whitespace separated. Only the identifiers matter to us.
    references = []
    raw_refs = _text(root, 'cap:references')
    if raw_refs:
        for ref in raw_refs.split():
            parts = ref.split(',')
            if len(parts) >= 2:
                references.append(parts[1])

    return {
        'source_uid': source_uid,
        'cap_identifier': _text(root, 'cap:identifier'),
        'sender': _text(root, 'cap:sender'),
        'sent_at': parse_cap_datetime(_text(root, 'cap:sent')),
        'status': _text(root, 'cap:status'),
        'msg_type': _text(root, 'cap:msgType'),
        'scope': _text(root, 'cap:scope'),
        'references': references,
        'category': _text(info, 'cap:category'),
        'event': _text(info, 'cap:event'),
        'urgency': _text(info, 'cap:urgency'),
        'severity': severity,
        'certainty': certainty,
        'effective_at': parse_cap_datetime(_text(info, 'cap:effective')),
        'onset_at': parse_cap_datetime(_text(info, 'cap:onset')),
        'expires_at': parse_cap_datetime(_text(info, 'cap:expires')),
        'headline': _text(info, 'cap:headline'),
        'description': _text(info, 'cap:description'),
        'instruction': _text(info, 'cap:instruction'),
        'area_desc': area_desc,
        'district_codes': district_codes,
        'polygon_url': polygon_url,
        'priority': SEVERITY_TO_PRIORITY.get(severity, 'low'),
        'confidence': CERTAINTY_TO_CONFIDENCE.get(certainty, 0.4),
    }


class SachetPolygonAdapter(IngestAdapter):
    """The alert's affected-area polygon.

    A separate document at a separate URL, referenced from `cap:parameter`
    rather than carried inline in `cap:area` - so one extra fetch per alert,
    which is why it is cached hard.

    The vertices are `lat,lon`. GeoJSON is `lon,lat`. Swapping them puts a
    Bengaluru alert in the Indian Ocean, so the two orderings are kept
    explicitly separate here: `pairs` is always (lat, lon), `ring` is always
    [lon, lat].
    """

    source_key = 'sachet_polygon'
    ttl_seconds = 24 * 3600
    stale_grace_seconds = 30 * 24 * 3600

    def cache_key(self, identifier=None, url=None, **kwargs):
        return super(SachetPolygonAdapter, self).cache_key(identifier=identifier)

    def fetch(self, identifier=None, url=None, **kwargs):
        import requests

        response = requests.get(url or (POLYGON_URL % identifier), timeout=self.timeout,
                                headers={'User-Agent': 'SentinelAI-DigitalTwin/1.0'})
        response.raise_for_status()
        pairs = parse_polygon_document(response.content)
        if not pairs:
            return None
        return {
            'pairs': pairs,                                   # (lat, lon)
            'ring': [[lon, lat] for lat, lon in pairs],       # [lon, lat]
        }


def parse_polygon_document(payload):
    """Polygon XML bytes -> [(lat, lon), ...].

    This document is NOT namespaced - it is a bare <alert><polygon>. Reusing
    the cap: prefix here matches nothing and returns an empty polygon, which
    then silently degrades every alert to district-level resolution.
    """
    root = etree.fromstring(payload)
    node = root.find('polygon')
    if node is None or not node.text:
        return []

    pairs = []
    for token in node.text.split():
        parts = token.split(',')
        if len(parts) != 2:
            continue
        try:
            lat, lon = float(parts[0]), float(parts[1])
        except ValueError:
            continue
        # India spans roughly 6-38N, 68-98E. A pair outside that is almost
        # certainly lon,lat the wrong way round; drop it rather than plot it.
        if 6.0 <= lat <= 38.0 and 68.0 <= lon <= 98.0:
            pairs.append((lat, lon))
    return pairs
