# Relief donations + Municipal Commissioner portal

A build spec, in the style of `analyst.md` and `liveincident.md`.

> **Naming note.** This is deliberately not `README.md`. That file already
> exists in this repo at 145 KB and documents the whole system; overwriting it
> to describe two features would destroy it. This document covers only the new
> work, and the existing README stays as it is.

---

## 0. Scope

**Build:**
1. A **relief donation flow** attached to individual hazard reports, visible
   only once an official has verified the report.
2. A **demo payment path** — a simulated checkout that records a donation
   without moving any money, labelled as such everywhere it appears.
3. A **Municipal Commissioner portal** — a city-wide overview for a decision
   maker, distinct from the analyst's per-report triage view.

**Do NOT build:**
- ❌ **Any real payment processing.** No gateway credentials, no card capture,
  no fund movement. See §2.
- ❌ **A donate button on unverified reports.** See §1.2 — this is the whole
  point of the feature.
- ❌ **A second copy of the analyst dashboard.** The commissioner portal
  answers different questions; if it ends up looking the same, it is wrong.

---

## 1. Donations

### 1.1 Why it hangs off a report

The app already has a verification pipeline: a citizen submits a `Report`, an
AI scores it, and an official sets `verification_status` to `approved` or
`rejected`. That gate exists to stop unverified claims reaching an operator.

The same gate is exactly what a donation needs. Money attracts fraud, and an
open "donate to any incident" button is an invitation to file a fake flood and
collect for it. Reusing the official's verification decision means a human with
authority has already looked at the incident before a rupee can be offered
against it.

### 1.2 The gate — the one rule that governs this feature

> **A donate button appears only when `report.verification_status == 'approved'`.**

Not "pending". Not "high AI confidence". Not "auto-approved by the model". An
official's decision, and nothing else.

The server must enforce this, not just the template. A template-only check is a
URL away from being bypassed: `POST /donate/<report_id>` has to re-check the
report's status and refuse anything not approved.

### 1.3 Data model

```
donation
  id
  report_id        -> report.id, nullable (null = general relief fund)
  user_id          -> user.id, nullable (nullable so a guest can give)
  amount_paise     INTEGER    -- integers only; see §1.4
  currency         'INR'
  status           'pending' | 'completed' | 'failed' | 'refunded'
  method           'demo'     -- the only value this build produces
  is_demo          BOOLEAN NOT NULL DEFAULT 1
  reference        VARCHAR    -- unique, shown on the receipt
  donor_name, donor_email, donor_phone
  is_anonymous     BOOLEAN
  message          TEXT       -- optional note to responders
  created_at, completed_at
```

### 1.4 Money is stored in paise, as an integer

Never a float. `0.1 + 0.2 != 0.3` in binary floating point, and a currency
column that drifts by fractions of a paisa across a few thousand rows is the
kind of bug that is found by an auditor, not by a test. Store `amount_paise`
as an integer and format for display at the edge.

### 1.5 The demo payment path

A real gateway is out of scope, so the checkout is simulated. The requirements
on a simulation are different from, and in one way stricter than, a real one:

- Every surface that shows the checkout must carry an unmissable **DEMO** mark.
  A payment screen that looks real and is not is worse than no payment screen.
- No card number, CVV, UPI PIN or bank credential field may exist at all —
  not even a disabled one. If the field is not there, it cannot capture
  anything, and no user can be trained into typing a real card number into a
  toy.
- The donation is recorded with `is_demo = 1` permanently. A later migration
  to a real gateway must never be able to silently reclassify demo rows as
  real receipts.
- The receipt says, in plain words, that no money moved.

### 1.6 Leaving room for a real gateway

Keep the payment step behind one function — `create_payment_intent(donation)`
— returning a dict the template renders. The demo implementation returns
`{'kind': 'demo'}`. A Razorpay or UPI implementation returns its own order id
or intent URL. Nothing else in the flow needs to change, and `is_demo` keeps
the two populations separable for ever.

---

## 2. What this build must not do

This is a demo payment path. It follows that:

- **No real credentials are entered by anyone building it.** Gateway keys,
  merchant ids, bank details and UPI VPAs stay out of the repo and out of the
  code. If a real gateway is added later, its keys belong in `.env`, which is
  already gitignored.
- **No card data is captured, transmitted or stored.** Not in a demo, not
  "just for the flow". PCI scope is something you acquire by accident.
- **Accepting real public donations is a legal matter, not a technical one.**
  In India that means a registered entity, and for foreign contributions an
  FCRA registration. Shipping a working payment button does not make the
  collection lawful. That decision sits with the operator of this system.

---

## 3. Municipal Commissioner portal

### 3.1 It is not the analyst dashboard

The analyst dashboard answers *"what is happening at this spot, and is this
report real?"* — per-report triage, the digital twin, per-cell risk.

A commissioner asks different questions:

| Question | What answers it |
|---|---|
| Is the city getting better or worse? | Trend over weeks, not a live map |
| Where is it worst? | Ward/zone ranking, not a hexagon |
| Are we responding fast enough? | Time from report to verification, and to resolution |
| Is verification keeping up? | Pending backlog and its age |
| What have we got to deploy? | Agencies, volunteers, resource allocations |
| What has the public given? | Donations raised, per incident |
| What is the state warning us about? | Official alerts currently in force |

If a number on this page cannot change a decision, it should not be on the page.

### 3.2 Access

A new `commissioner` role. `official` and `admin` are admitted too, so the
portal is reachable in an existing deployment without first minting a new
account — but the role exists so that separation is possible later.

Enforced server-side in the route, matching the pattern
`analyst_dashboard` already uses.

### 3.3 Contents

1. **Headline counts** — total incidents, verified, pending, resolved,
   people reached.
2. **Response performance** — median hours from submission to verification;
   pending backlog by age bucket. Median, not mean: one report that sat for
   three weeks should not move the number that describes the other ninety.
3. **Ward / zone breakdown** — incidents per twin zone, worst first.
4. **Hazard mix** — what the city is actually dealing with.
5. **Live risk** — current status counts from the twin, plus official alerts
   in force. Read-only; the twin owns that computation.
6. **Relief** — donations raised, count, and top-funded incidents. Demo
   amounts must be labelled as demo here too, or a commissioner will read a
   simulated total as real budget.
7. **Capacity** — agencies, volunteers, active resource allocations.

### 3.4 Honesty requirements

- A zero must be distinguishable from a not-measured. If no report has ever
  been resolved, "median resolution time" is **not** `0 h`; it is *no data*.
- Demo donation totals carry a demo badge wherever they appear.
- Any figure derived from the twin says so, because the twin's own inputs can
  be degraded and it reports that.

---

## 4. Build sequence

1. `Donation` model + migration-safe `create_all`.
2. Server-side gate, then the donate button on `view_report.html`.
3. Demo checkout + receipt.
4. Commissioner role + `/commissioner` route + template.
5. Wire donation and twin figures into the portal.

## 5. Acceptance criteria

- [ ] Donate button is absent on a `pending` report and present on an `approved` one
- [ ] `POST` to the donate endpoint for a non-approved report is refused server-side
- [ ] No input field anywhere collects a card number, CVV, UPI PIN or bank credential
- [ ] Every donation row created by this build has `is_demo = 1`
- [ ] The checkout and the receipt both state that no money moved
- [ ] `/commissioner` is refused for a `citizen` and served for `official`/`commissioner`/`admin`
- [ ] Every figure on the portal traces to a real query; no placeholder numbers
- [ ] "No data" is shown where nothing has been measured, never `0`
