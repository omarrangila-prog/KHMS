# Hospital In-Patient Department (`hospital_ipd`)

Module 9 of 12 in the Hospital Management System suite.

## Purpose

Full inpatient lifecycle: ward/bed master data, admission requests, bed assignment,
mid-stay transfers, and discharge with length-of-stay billing — the most complex
state machine in the suite (Phase 10 Sprint 8).

## Dependencies

- `hospital_doctor` and `hospital_nurse` (which transitively depend on `hospital_reception`, `hospital_base`)
- Deliberately **not** `hospital_lab`/`hospital_radiology`/`hospital_pharmacy`/`hospital_inventory` — see "Visit Branch Integration" below.

## Key Models

| Model | Purpose |
|---|---|
| `hospital.ward` | Ward master data (type, daily rate, bed roster) |
| `hospital.bed` | A single bed; `state` is a denormalized convenience field for dashboards |
| `hospital.ipd.admission` | Admission state machine: requested → waiting_for_bed → admitted → discharged/cancelled |
| `hospital.bed.transfer` | Mid-stay bed change, always a child row of the same admission (never a new admission) |
| `hospital.discharge` | Discharge summary + length-of-stay billing, blocked while any branch is pending |
| `hospital.discharge.medication` | Take-home medication lines printed on the discharge summary |
| `hospital.visit` (_inherit_) | Adds `admission_id`/`admission_ids`; extends `_compute_pending_branches()` and `action_route_from_consultation()` |
| `hospital.nurse.task` (_inherit_) | Adds `admission_id` for ward-round/MAR checklist items |

## Admission State Machine

```
requested → waiting_for_bed → admitted → discharged
        \________________________/
                    ↓
                cancelled
```

`waiting_for_bed` is reached when no vacant bed exists at request time. A transfer
mid-stay never creates a new admission — it is a `hospital.bed.transfer` child row.

## Concurrency Design: One Active Admission Per Bed

Phase 5 §5.2 requires this guarantee at the **database** level, not just in Python.
`hospital.ipd.admission.init()` creates an idempotent partial unique index:

```sql
CREATE UNIQUE INDEX IF NOT EXISTS hospital_ipd_admission_one_active_per_bed
ON hospital_ipd_admission (bed_id) WHERE state = 'admitted'
```

Two concurrent `action_assign_bed()` calls targeting the same bed: the database
rejects the second `UPDATE`/`INSERT` with a `psycopg2.errors.UniqueViolation`, which
is allowed to propagate rather than being swallowed — the losing caller gets a clean
failure and can retry against a different bed.

## Discharge Blocking Rule

Confirming a discharge is blocked while any branch the visit opened (prescription,
lab, radiology) is still pending. Since this module cannot depend on
`hospital_lab`/`hospital_radiology`/`hospital_pharmacy` (they don't depend on
`hospital_ipd`, so a reverse dependency would cycle), the check is generic: it calls
`visit_id._compute_pending_branches()`, the extension contract `hospital_doctor`
built for exactly this purpose. Whichever of those modules are installed will have
already taught that method about their own branch.

## Visit Branch Integration

Extends `hospital.visit._compute_pending_branches()` to replace the intent-only
"admission" placeholder (set by `hospital_doctor` when `outcome_admit_requested=True`)
with a real check: pending while `requested`/`waiting_for_bed`, resolved once
`admitted` (an admitted patient is handled by the visit's own `admitted` state, not
the pending-branches list) or `discharged`/`cancelled`. Also extends
`action_route_from_consultation()` so an admitted visit is pulled out of OPD queues
entirely, per Phase 3 §3.

## Length-of-Stay Billing

`hospital.ipd.admission.length_of_stay_days` is computed from `admission_datetime`
to the discharge's `discharge_datetime` (or now, if still admitted).
`hospital.discharge.ward_charge_amount` multiplies this by the ward's `daily_rate`.
`hospital.discharge._create_ward_billing_line()` is a documented no-op extension
point — no module in the current build order owns `account.move` integration yet;
a future billing module should override it via `_inherit`, calling `super()` first.

## Installation

```bash
./odoo-bin -d mydb -i hospital_ipd
```

## Security Groups

- `hospital_ipd.group_hospital_ward_manager` — ward/bed staff: assign beds, manage transfers, finalize discharges
- `hospital_base.group_hospital_admin` — full access

An optional ward-scoped record rule (`hospital_bed_ward_scoped_rule`) is included but
inactive by default — small hospitals see all wards; a deployment wanting per-ward
scoping must activate the rule and configure a `ward_ids` field on `res.users`.

## Reports

- Discharge Summary (QWeb PDF): diagnosis, course, follow-up instructions, take-home
  medications — follow-up instructions are skipped on the printed summary for
  deceased discharges (Phase 3 §7 "Death in care" exception).

## Tests

Run with:
```bash
./odoo-bin -d mydb --test-enable -i hospital_ipd
```

Covers: concurrent-admission race condition against the partial unique index,
discharge blocked by pending branches, length-of-stay billing accuracy, and the
bed-transfer audit trail.
