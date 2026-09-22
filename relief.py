"""Relief donations against verified hazard reports.

The gate is the whole feature: a donate button exists only once an **official**
has set `verification_status == 'approved'` on the report. The app already runs
that human verification step to stop unverified claims reaching an operator, and
money needs it more than a map does - an open "donate to any incident" button is
an invitation to file a fake flood and collect against it.

Payment here is **simulated**. There is no gateway, no credential of any kind is
collected, and no money moves. `create_payment_intent` is the single seam where
a real gateway would be added; everything else in the flow is independent of it.
"""

import secrets
from datetime import datetime

from flask import (Blueprint, abort, flash, redirect, render_template, request,
                   url_for)
from flask_login import current_user, login_required

from models import Donation, Report, db

relief = Blueprint('relief', __name__)

# Presets in rupees. Offered as buttons so most donors never type a number.
PRESET_AMOUNTS = (100, 500, 1000, 2500)
MIN_RUPEES = 10
# A cap, even in a demo. An unbounded integer field reaching the database is how
# you end up with a 'donation' of 10^18 paise skewing every total on the
# commissioner's portal.
MAX_RUPEES = 100000


def create_payment_intent(donation):
    """The seam a real gateway would replace.

    Returns whatever the checkout template needs to render the payment step.
    The demo implementation returns a marker and nothing else - no order id, no
    client token, because there is no payment processor on the other end.

    A Razorpay or UPI implementation would return its own order id or intent
    URL here and change nothing else in this module.
    """
    return {'kind': 'demo', 'reference': donation.reference}


def _new_reference():
    # token_hex, not a counter: a reference appears on a receipt, and a
    # guessable one lets somebody enumerate other people's donations.
    return 'SR-%s' % secrets.token_hex(6).upper()


def _donatable_report_or_404(report_id):
    """Fetch a report, refusing anything an official has not approved.

    Enforced here rather than only in the template. A template-only check is one
    crafted URL away from being bypassed, and this endpoint is the one that
    creates money-shaped rows.
    """
    report = Report.query.get_or_404(report_id)
    if report.verification_status != 'approved':
        abort(403, description='Donations open only after an official verifies this report.')
    return report


def report_totals(report_id):
    """(completed paise, completed count) for one report."""
    row = (db.session.query(db.func.coalesce(db.func.sum(Donation.amount_paise), 0),
                            db.func.count(Donation.id))
           .filter(Donation.report_id == report_id,
                   Donation.status == 'completed')
           .one())
    return int(row[0] or 0), int(row[1] or 0)


@relief.route('/donate/<int:report_id>', methods=['GET'])
@login_required
def donate(report_id):
    report = _donatable_report_or_404(report_id)
    raised_paise, donor_count = report_totals(report.id)
    return render_template(
        'donate.html',
        report=report,
        presets=PRESET_AMOUNTS,
        min_rupees=MIN_RUPEES,
        max_rupees=MAX_RUPEES,
        raised_rupees=raised_paise / 100.0,
        donor_count=donor_count,
        recent=(Donation.query
                .filter_by(report_id=report.id, status='completed')
                .order_by(Donation.completed_at.desc()).limit(8).all()),
    )


@relief.route('/donate/<int:report_id>', methods=['POST'])
@login_required
def submit_donation(report_id):
    # Re-checked on POST, not trusted from the GET that rendered the form.
    report = _donatable_report_or_404(report_id)

    raw = (request.form.get('amount') or '').strip()
    try:
        rupees = int(float(raw))
    except (TypeError, ValueError):
        flash('Enter a donation amount in rupees.', 'warning')
        return redirect(url_for('relief.donate', report_id=report.id))

    if rupees < MIN_RUPEES or rupees > MAX_RUPEES:
        flash('Amount must be between Rs %d and Rs %s.' % (MIN_RUPEES, format(MAX_RUPEES, ',')),
              'warning')
        return redirect(url_for('relief.donate', report_id=report.id))

    donation = Donation(
        report_id=report.id,
        user_id=current_user.id,
        # Integer paise. The only multiplication by 100 in the codebase.
        amount_paise=rupees * 100,
        currency='INR',
        status='pending',
        method='demo',
        is_demo=True,
        reference=_new_reference(),
        donor_name=(request.form.get('donor_name') or '').strip() or current_user.username,
        donor_email=(request.form.get('donor_email') or '').strip() or None,
        donor_phone=(request.form.get('donor_phone') or '').strip() or None,
        is_anonymous=bool(request.form.get('is_anonymous')),
        message=(request.form.get('message') or '').strip() or None,
    )
    db.session.add(donation)
    db.session.commit()

    # The simulated settlement. A real gateway would leave the row `pending`
    # here and flip it to `completed` from a verified webhook - never from the
    # browser, which the donor controls.
    create_payment_intent(donation)
    donation.status = 'completed'
    donation.completed_at = datetime.utcnow()
    db.session.commit()

    return redirect(url_for('relief.receipt', reference=donation.reference))


@relief.route('/donate/receipt/<reference>')
@login_required
def receipt(reference):
    donation = Donation.query.filter_by(reference=reference).first_or_404()
    # A receipt names a donor and an amount; only the donor and officials see it.
    if (donation.user_id != current_user.id
            and (current_user.role or '') not in ('official', 'admin', 'commissioner')):
        abort(403)
    return render_template('donate_receipt.html', donation=donation)
