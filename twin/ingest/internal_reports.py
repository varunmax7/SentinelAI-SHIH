"""Bridge from the host application's `Report` model into the twin's grid.

This is the one 'ingest' that touches no network: verified citizen reports are
already the most locally-specific hazard signal the system has, and they are
what makes the twin a picture of *this* city rather than a weather visualiser.
"""

from datetime import datetime, timedelta

from ..grid import cell_for_point

# Priority is the operator's own severity call; confidence is the AI's.
SEVERITY_BY_PRIORITY = {
    'critical': 1.0,
    'high': 0.8,
    'medium': 0.55,
    'low': 0.3,
}

# How far back a report can still contribute. The exponential decay in
# scoring.incident_load does the real work; this only bounds the query.
LOOKBACK_HOURS = 72


def collect_incidents(Report, bbox, resolution=None, lookback_hours=LOOKBACK_HOURS,
                      now=None):
    """Verified reports inside `bbox`, keyed by the H3 cell they fall in.

    Only `approved` reports feed the risk score. Pending reports are shown as
    incident pins so an operator can see them, but an unreviewed report must
    never be able to move a published risk number on its own.
    """
    now = now or datetime.utcnow()
    min_lon, min_lat, max_lon, max_lat = bbox
    since = now - timedelta(hours=lookback_hours)

    rows = (Report.query
            .filter(Report.timestamp >= since,
                    Report.latitude.between(min_lat, max_lat),
                    Report.longitude.between(min_lon, max_lon))
            .all())

    scoring = {}
    pins = []
    for report in rows:
        if report.latitude is None or report.longitude is None:
            continue
        index = cell_for_point(report.latitude, report.longitude, resolution)
        entry = {
            'id': report.id,
            'h3': index,
            'title': report.title,
            'hazard_type': report.hazard_type,
            'status': report.verification_status,
            'priority': report.priority,
            'severity': SEVERITY_BY_PRIORITY.get(report.priority, 0.5),
            'confidence': float(report.confidence_score or 0.0),
            'timestamp': report.timestamp,
            'lat': float(report.latitude),
            'lon': float(report.longitude),
            'location': report.location,
        }
        pins.append(entry)
        if report.verification_status == 'approved':
            scoring.setdefault(index, []).append(entry)

    return scoring, pins
