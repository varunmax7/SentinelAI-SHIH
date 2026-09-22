"""Municipal Commissioner portal - a city-wide view for a decision maker.

Deliberately not a second analyst dashboard. The analyst asks "is this report
real, and what is happening at this spot"; a commissioner asks "is the city
getting better or worse, where is it worst, are we responding fast enough, and
what have we got left to deploy". If this page ends up looking like
`/analyst_dashboard`, it has failed.

One rule runs through every figure here: **a zero and a not-measured are
different things.** If no report has ever been resolved, median resolution time
is not `0 h` - it is no data, and the page says so. A commissioner acting on a
fabricated zero is worse off than one who knows the number is missing.
"""

import statistics
from datetime import datetime, timedelta
from functools import wraps

from flask import Blueprint, flash, redirect, render_template, url_for
from flask_login import current_user, login_required

from models import (Agency, Donation, EmergencyEvent, Report,
                    ResourceAllocation, User, Volunteer, db)

commissioner = Blueprint('commissioner', __name__)

# `commissioner` is the role this portal exists for. `official` and `admin` are
# admitted too so the page is reachable in a deployment that has not minted a
# commissioner account yet - the separate role is what makes separation of
# duties possible later, not something that must be used from day one.
PORTAL_ROLES = ('commissioner', 'official', 'admin')


def commissioner_required(view):
    @wraps(view)
    @login_required
    def wrapper(*args, **kwargs):
        if (current_user.role or '').lower() not in PORTAL_ROLES:
            flash('The Commissioner portal is restricted to city officials.', 'warning')
            return redirect(url_for('home'))
        return view(*args, **kwargs)
    return wrapper


def _median_hours(deltas):
    """Median of a list of timedeltas, in hours, or None when there are none.

    Median rather than mean on purpose: one report that sat unverified for three
    weeks should not drag the number that describes the other ninety.
    """
    if not deltas:
        return None
    return round(statistics.median(d.total_seconds() for d in deltas) / 3600.0, 1)


def _pct(part, whole):
    return round(100.0 * part / whole, 1) if whole else None


@commissioner.route('/commissioner')
@commissioner_required
def portal():
    now = datetime.utcnow()
    reports = Report.query.all()
    total = len(reports)

    # --- headline ----------------------------------------------------------
    approved = [r for r in reports if r.verification_status == 'approved']
    pending = [r for r in reports if r.verification_status == 'pending']
    rejected = [r for r in reports if r.verification_status == 'rejected']
    resolved = [r for r in reports if r.status == 'resolved']

    headline = {
        'total': total,
        'verified': len(approved),
        'pending': len(pending),
        'rejected': len(rejected),
        'resolved': len(resolved),
        'verification_rate': _pct(len(approved), total),
        'resolution_rate': _pct(len(resolved), total),
        'last_7_days': sum(1 for r in reports
                           if r.timestamp and r.timestamp >= now - timedelta(days=7)),
        'prev_7_days': sum(1 for r in reports
                           if r.timestamp
                           and now - timedelta(days=14) <= r.timestamp < now - timedelta(days=7)),
    }
    headline['trend'] = (headline['last_7_days'] - headline['prev_7_days'])

    # --- response performance ---------------------------------------------
    verification_lags = [r.verified_at - r.timestamp
                         for r in reports
                         if r.verified_at and r.timestamp and r.verified_at >= r.timestamp]

    buckets = {'under_6h': 0, 'h6_24': 0, 'd1_3': 0, 'over_3d': 0}
    oldest_pending_h = None
    for report in pending:
        if not report.timestamp:
            continue
        age_h = (now - report.timestamp).total_seconds() / 3600.0
        oldest_pending_h = age_h if oldest_pending_h is None else max(oldest_pending_h, age_h)
        if age_h < 6:
            buckets['under_6h'] += 1
        elif age_h < 24:
            buckets['h6_24'] += 1
        elif age_h < 72:
            buckets['d1_3'] += 1
        else:
            buckets['over_3d'] += 1

    performance = {
        'median_verification_h': _median_hours(verification_lags),
        'verified_sample': len(verification_lags),
        'backlog': buckets,
        'backlog_total': len(pending),
        'oldest_pending_h': round(oldest_pending_h, 1) if oldest_pending_h is not None else None,
    }

    # --- hazard mix --------------------------------------------------------
    hazard_counts = {}
    for report in reports:
        key = (report.hazard_type or 'other').replace('_', ' ').title()
        hazard_counts[key] = hazard_counts.get(key, 0) + 1
    hazard_mix = sorted(hazard_counts.items(), key=lambda kv: kv[1], reverse=True)

    priority_counts = {}
    for report in reports:
        priority_counts[report.priority or 'medium'] = \
            priority_counts.get(report.priority or 'medium', 0) + 1

    # --- ward / zone breakdown --------------------------------------------
    wards, twin_summary = _twin_breakdown(reports)

    # --- relief ------------------------------------------------------------
    donation_rows = Donation.query.filter_by(status='completed').all()
    top_funded = (db.session.query(Report, db.func.sum(Donation.amount_paise))
                  .join(Donation, Donation.report_id == Report.id)
                  .filter(Donation.status == 'completed')
                  .group_by(Report.id)
                  .order_by(db.func.sum(Donation.amount_paise).desc())
                  .limit(5).all())
    relief = {
        'total_rupees': sum(d.amount_paise for d in donation_rows) / 100.0,
        'count': len(donation_rows),
        'donors': len({d.user_id for d in donation_rows if d.user_id}),
        # If any contribution is a demo, the total is not real money and the
        # page must not let a commissioner read it as budget.
        'all_demo': all(d.is_demo for d in donation_rows) if donation_rows else True,
        'top_funded': [(r, paise / 100.0) for r, paise in top_funded],
    }

    # --- capacity ----------------------------------------------------------
    capacity = {
        'agencies': Agency.query.count(),
        'volunteers': Volunteer.query.count(),
        'volunteers_available': Volunteer.query.filter_by(is_available=True).count()
        if hasattr(Volunteer, 'is_available') else None,
        'allocations_active': ResourceAllocation.query.filter(
            ResourceAllocation.status != 'completed').count(),
        'emergencies_active': EmergencyEvent.query.filter(
            EmergencyEvent.status == 'active').count(),
        'citizens': User.query.filter_by(role='citizen').count(),
    }

    # --- 14-day trend ------------------------------------------------------
    trend_labels, trend_values = [], []
    for offset in range(13, -1, -1):
        day = (now - timedelta(days=offset)).date()
        trend_labels.append(day.strftime('%d %b'))
        trend_values.append(sum(1 for r in reports
                                if r.timestamp and r.timestamp.date() == day))

    return render_template(
        'commissioner.html',
        headline=headline,
        performance=performance,
        hazard_mix=hazard_mix,
        priority_counts=priority_counts,
        wards=wards,
        twin=twin_summary,
        relief=relief,
        capacity=capacity,
        trend_labels=trend_labels,
        trend_values=trend_values,
        generated_at=now,
        recent=sorted([r for r in reports if r.timestamp],
                      key=lambda r: r.timestamp, reverse=True)[:8],
    )


def _twin_breakdown(reports):
    """Ward counts and live risk, read from the digital twin.

    Read-only. The twin owns risk computation; duplicating any of that
    arithmetic here would let the two disagree, and then neither is trustworthy.
    Returns ([], None) when the twin is absent or unseeded, and the template
    says so rather than rendering an empty table as if it meant zero.
    """
    try:
        from twin import twin_models
        models = twin_models()
        if models is None:
            return [], None
    except Exception:  # noqa: BLE001 - the portal must not need the twin
        return [], None

    try:
        from twin.alerts import live_alerts
        from twin.grid import cell_for_point

        wards = []
        summary = {'cities': [], 'alerts_in_force': 0, 'degraded': 0}

        for city in models.TwinCity.query.all():
            zone_by_cell = {c.h3_index: c.zone_id for c in city.cells}
            zone_names = {z.id: z.name for z in city.zones}

            counts = {}
            for report in reports:
                if report.latitude is None or report.longitude is None:
                    continue
                index = cell_for_point(report.latitude, report.longitude, city.h3_resolution)
                zone_id = zone_by_cell.get(index)
                if zone_id is None:
                    continue
                counts[zone_id] = counts.get(zone_id, 0) + 1

            for zone_id, count in counts.items():
                wards.append({'city': city.name,
                              'zone': zone_names.get(zone_id, 'Unknown'),
                              'incidents': count})

            rows = (db.session.query(models.TwinCellState.status,
                                     db.func.count(models.TwinCellState.id))
                    .join(models.TwinCell, models.TwinCell.id == models.TwinCellState.cell_id)
                    .filter(models.TwinCell.city_id == city.id,
                            models.TwinCellState.horizon_hours == 0)
                    .group_by(models.TwinCellState.status).all())
            status_counts = {s: n for s, n in rows}
            alerts = live_alerts(models, city)
            summary['alerts_in_force'] += len(alerts)
            summary['cities'].append({
                'name': city.name,
                'slug': city.slug,
                'status_counts': status_counts,
                'cells': sum(status_counts.values()),
                'alerts': len(alerts),
                'last_computed_at': city.last_computed_at,
            })

        summary['degraded'] = (models.TwinCellState.query
                               .filter_by(horizon_hours=0, degraded_inputs=True).count())
        wards.sort(key=lambda w: w['incidents'], reverse=True)
        return wards, summary
    except Exception:  # noqa: BLE001
        return [], None
