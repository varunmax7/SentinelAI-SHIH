#!/usr/bin/env python
"""Build the digital twin's H3 grid and load its static inputs.

    python scripts/seed_twin.py              # grid + elevation + OSM (slow)
    python scripts/seed_twin.py --fast       # grid + elevation only
    python scripts/seed_twin.py --rebuild    # drop cells no longer in the grid
    python scripts/seed_twin.py --compute    # also run one scoring pass

Safe to re-run. Cells are matched by h3_index and updated in place, so a re-seed
keeps accumulated terrain data and existing state rows.
"""

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fast', action='store_true',
                        help='skip the Overpass passes (water, assets, cameras)')
    parser.add_argument('--rebuild', action='store_true',
                        help='delete cells that are no longer part of the grid')
    parser.add_argument('--compute', action='store_true',
                        help='run one scoring pass after seeding')
    args = parser.parse_args()

    import app as host
    from models import Report, db
    from twin import twin_models
    from twin import engine, seed

    models = twin_models()
    if models is None:
        print('Digital Twin is not registered (TWIN_ENABLED=0?)')
        return 1

    started = time.time()
    with host.app.app_context():
        report = seed.seed_all(db, models, rebuild=args.rebuild, skip_slow=args.fast)
        print(json.dumps(report, indent=2, default=str))

        if args.compute:
            print('\ncomputing...')
            print(json.dumps(engine.compute_all(db, models, Report), indent=2, default=str))

    print('\ndone in %.1fs' % (time.time() - started))
    return 0


if __name__ == '__main__':
    sys.exit(main())
