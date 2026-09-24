#!/usr/bin/env python
"""Backfill the twin's anomaly baselines.

    python scripts/backfill_baselines.py              # both cities, 5 years
    python scripts/backfill_baselines.py --years 3     # shorter history
    python scripts/backfill_baselines.py --city hyderabad

Run once. Safe to re-run: each sample point is upserted by
`(city_id, sample_h3)`, so a re-run just refreshes the numbers rather than
duplicating rows. Until this has run at least once, `twin/anomaly.py` has
nothing to compare against and every cell's anomaly reading is simply absent
- an honestly-empty field, not a wrong one (see engine.py).

One Open-Meteo archive call per sample point, not per cell - the same coarse
H3 resolution-6 sampling `ingest/open_meteo.py` already uses for weather, so
Hyderabad's 805 cells cost a double-digit number of archive calls, not 805.
Each call returns years of daily data, so this is deliberately a slow,
offline, one-shot script rather than something the scheduler ever runs.
"""

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--years', type=int, default=None,
                        help='override TWIN_BASELINE_YEARS for this run')
    parser.add_argument('--city', default=None,
                        help='only this city slug (default: every seeded city)')
    parser.add_argument('--pause', type=float, default=1.0,
                        help='seconds between archive calls (rate-limit courtesy)')
    args = parser.parse_args()

    import app as host
    from models import db
    from twin import twin_models
    from twin import anomaly, config as twin_config
    from twin.ingest.open_meteo import sample_cells

    models = twin_models()
    if models is None:
        print('Digital Twin is not registered (TWIN_ENABLED=0?)')
        return 1

    years = args.years or twin_config.BASELINE_YEARS
    started = time.time()
    report = {}

    with host.app.app_context():
        cities = models.TwinCity.query.all()
        if args.city:
            cities = [c for c in cities if c.slug == args.city]
            if not cities:
                print('Unknown city %r' % args.city)
                return 1

        for city in cities:
            h3_indexes = [c.h3_index for c in city.cells]
            if not h3_indexes:
                report[city.slug] = {'error': 'grid not seeded - run scripts/seed_twin.py first'}
                continue

            _by_cell, points = sample_cells(h3_indexes)
            ok = failed = 0

            for sample_h3, lat, lon in points:
                climatology = anomaly.fetch_climatology(lat, lon, years=years)
                if climatology is None:
                    failed += 1
                    print('  ! %s (%s, %.4f, %.4f): archive call failed or too little history'
                         % (city.slug, sample_h3, lat, lon))
                else:
                    row = models.TwinBaseline.query.filter_by(
                        city_id=city.id, sample_h3=sample_h3).first()
                    if row is None:
                        row = models.TwinBaseline(city_id=city.id, sample_h3=sample_h3)
                        db.session.add(row)
                    row.latitude = lat
                    row.longitude = lon
                    row.years = climatology['years']
                    row.sample_days = climatology['sample_days']
                    row.rain_daily_mean_mm = climatology['rain_daily_mean_mm']
                    row.rain_daily_std_mm = climatology['rain_daily_std_mm']
                    row.temp_max_mean_c = climatology['temp_max_mean_c']
                    row.temp_max_std_c = climatology['temp_max_std_c']
                    ok += 1
                    print('  + %s (%s): rain %.1f +/- %.1f mm/day, temp %.1f +/- %.1f C'
                         % (city.slug, sample_h3, climatology['rain_daily_mean_mm'],
                            climatology['rain_daily_std_mm'], climatology['temp_max_mean_c'],
                            climatology['temp_max_std_c']))

                db.session.commit()
                if args.pause:
                    time.sleep(args.pause)

            report[city.slug] = {'points': len(points), 'ok': ok, 'failed': failed}

    print(json.dumps(report, indent=2))
    print('\ndone in %.1fs' % (time.time() - started))
    return 0


if __name__ == '__main__':
    sys.exit(main())
