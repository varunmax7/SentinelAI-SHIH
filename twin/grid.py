"""H3 grid construction and cell/zone geometry.

The grid is a `grid_disk` of hexagons around the city centre rather than a
rectangle clipped to a boundary polygon. Two reasons: it needs no admin
boundary download to produce a usable grid, and a disk has no corner cells
sitting 20 km outside the built-up area contributing nothing but payload.
"""

import json

import h3

from . import config as twin_config
from .geo import haversine_m


def city_center_cell(city_cfg, resolution=None):
    resolution = resolution or twin_config.H3_RESOLUTION
    return h3.latlng_to_cell(city_cfg['center_latitude'],
                             city_cfg['center_longitude'],
                             resolution)


def generate_cells(city_cfg, resolution=None, rings=None):
    """Every H3 index covering the city, as dicts ready for TwinCell rows.

    Returns a list of {h3, lat, lon, ring (GeoJSON linear ring), area_km2}.
    """
    resolution = resolution or twin_config.H3_RESOLUTION
    rings = twin_config.GRID_RINGS if rings is None else rings

    center = city_center_cell(city_cfg, resolution)
    out = []
    for index in h3.grid_disk(center, rings):
        lat, lon = h3.cell_to_latlng(index)
        out.append({
            'h3': index,
            'lat': lat,
            'lon': lon,
            'ring': cell_ring(index),
            'area_km2': h3.cell_area(index, unit='km^2'),
        })
    return out


def cell_ring(h3_index):
    """Closed GeoJSON linear ring for a cell, lon-first and wound closed.

    h3 returns (lat, lng) tuples and does *not* repeat the first vertex;
    GeoJSON needs the opposite of both.
    """
    boundary = h3.cell_to_boundary(h3_index)
    ring = [[lon, lat] for lat, lon in boundary]
    ring.append(ring[0])
    return ring


def cell_polygon(h3_index):
    return {'type': 'Polygon', 'coordinates': [cell_ring(h3_index)]}


def grid_bbox(cells):
    """(min_lon, min_lat, max_lon, max_lat) over generated cell dicts."""
    lons, lats = [], []
    for cell in cells:
        for lon, lat in cell['ring']:
            lons.append(lon)
            lats.append(lat)
    return (min(lons), min(lats), max(lons), max(lats))


def nearest_zone(lat, lon, zones):
    """Nearest zone by centre point - a Voronoi partition of the grid.

    `zones` is an iterable of objects with center_latitude/center_longitude.
    This is why every zone is flagged boundary_source='approximate': it is a
    nearest-centre assignment, not a surveyed ward boundary, and anything that
    displays a zone must say so.
    """
    best, best_d = None, None
    for zone in zones:
        d = haversine_m(lat, lon, zone.center_latitude, zone.center_longitude)
        if best_d is None or d < best_d:
            best, best_d = zone, d
    return best


def zone_hull_geojson(cells):
    """A boundary polygon for a zone, unioned from its member hexagons.

    Rather than a convex hull (which bridges over cells belonging to other
    zones), this collects the member hexes as a MultiPolygon. MapLibre renders
    it identically to a single polygon and the outline follows the real cell
    assignment, so the operator never sees a zone claiming ground it does not
    own.
    """
    polys = [[cell_ring(c.h3_index)] for c in cells]
    if not polys:
        return None
    return {'type': 'MultiPolygon', 'coordinates': polys}


def k_ring_neighbours(h3_index, k=1):
    """Neighbouring cells, excluding the cell itself."""
    return [c for c in h3.grid_disk(h3_index, k) if c != h3_index]


def cell_for_point(lat, lon, resolution=None):
    resolution = resolution or twin_config.H3_RESOLUTION
    return h3.latlng_to_cell(lat, lon, resolution)


def dumps_ring(ring):
    return json.dumps(ring, separators=(',', ':'))
