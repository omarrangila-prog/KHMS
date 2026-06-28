# Hospital Nurse

## Purpose

`hospital_nurse` is the nurse-station addon of the Hospital Management
System suite for Odoo 19. It builds on `hospital_base` and
`hospital_reception` to give nursing staff structured vitals capture with
automatic triage escalation, a tablet-first Nurse Dashboard, and a simple
OPD nurse task checklist.

This module is **module 3 of 12** in the build order defined by the
project's Phase 12 implementation plan.

## Dependencies

- `hospital_base`
- `hospital_reception`

**Why `hospital_reception` and not just `hospital_base`:** Phase 6 §3 and
the Phase 4 module dependency table both list `hospital_nurse`'s
dependencies as `hospital_base, hospital_reception`. The nurse workflow
(Phase 3 §2) only ever begins once a visit has already been checked in
and confirmed into `waiting_nurse` -- a transition `hospital_reception`
owns (walk-in registration and appointment check-in both call
`hospital.visit.action_confirm()`). The Nurse Dashboard's demo data and
real-world usage assume `hospital_reception`'s queue/visit-creation flow
already ran, so depending on it directly (rather than just `hospital_base`)
matches how the module is actually used, per the authoritative module
breakdown rather than a minimal-but-impractical `hospital_base`-only
dependency.

## Key Models

| Model | Purpose |
|---|---|
| `hospital.vitals` | Structured vitals capture: blood pressure, pulse, temperature, SpO2, respiratory rate, height/weight with computed BMI. Auto-escalates the visit's priority and auto-transitions it to `waiting_doctor` on create. |
| `hospital.nurse.task` | Simple OPD nurse task checklist item, linked to a visit. `hospital_ipd` (not yet built) will extend it with `admission_id` via `_inherit` for ward-round/IPD use, once `hospital.ipd.admission` exists. |
| `hospital.visit` (extended) | Adds `vitals_ids`, `nurse_task_ids`, and the `action_vitals_recorded()` transition method (`waiting_nurse` -> `waiting_doctor`), since `hospital_base`'s visit model has no knowledge of vitals. |

## The Key Business Rule (Phase 3 §2)

Recording vitals on a visit that is `waiting_nurse`:

1. **Always** transitions the visit to `waiting_doctor` -- a single
   "Save & Send to Doctor" action, no separate send step.
2. **Conditionally** escalates the visit's `priority` to `urgent` if any
   recorded vital breaches an abnormal threshold (see below) -- and this
   escalation **never de-escalates** an already-`emergency` visit.

Both effects happen inside `hospital.vitals.create()` via
`_check_abnormal_and_escalate()`, called after `super().create()` so the
computed `bmi`/`is_abnormal` fields are already available.

## Abnormal-Vitals Escalation Thresholds

Defined as named constants at the top of `models/hospital_vitals.py` (one
source of truth, reused by both the `@api.constrains` range checks and
the escalation logic):

| Vital | Abnormal if |
|---|---|
| Blood pressure (systolic) | `> 180` or `< 90` mmHg |
| Temperature | `> 39.0°C` or `< 35.0°C` |
| SpO2 | `< 92%` |
| Pulse rate | `> 120` or `< 50` bpm |

Separately, range-sanity constraints (rejecting data-entry errors, not
clinical judgement) reject:

| Field | Valid range |
|---|---|
| `blood_pressure_systolic` | 40-300 mmHg |
| `blood_pressure_diastolic` | 20-200 mmHg |
| `pulse_rate` | 1-300 bpm |
| `temperature` | 30-45°C |
| `spo2` | 0-100% |
| `respiratory_rate` | 1-100 breaths/min |

## Security

- **Hospital Nurse** (`group_hospital_nurse`): implied by
  `hospital_base.group_hospital_user`; full create/read/write (no delete)
  on `hospital.vitals`, full CRUD on `hospital.nurse.task`.
- `hospital_base.group_hospital_admin` retains full CRUD on both models.
- `hospital_base.group_hospital_user` gets read-only access as the base
  fallback, consistent with `hospital_base`'s own ACL pattern.
- Multi-company record rules on both models, consistent with
  `hospital_base`'s `['|', ('company_id', '=', False), ('company_id', 'in', company_ids)]`
  pattern -- `company_id` is a related, stored field derived from
  `visit_id.company_id` on both models (mirroring how
  `hospital_reception`'s `hospital.appointment` carries its own
  `company_id`).

## Views & Menus

`Hospital -> Nurse Station` (visible to `group_hospital_nurse` and
`group_hospital_admin`):

- **Dashboard** -- OWL client action, tablet-first: a big "Next Patient"
  card (priority/check-in ordered), a "Record Vitals" shortcut opening the
  Vitals Quick-Entry dialog, and the pending nurse task list.
- **Vitals History** -- list/form view of `hospital.vitals`, filterable by
  patient/abnormal flag.
- **Nurse Tasks** -- list/kanban/form view of `hospital.nurse.task`.

The visit form (`hospital_base.hospital_visit_view_form`) gains a "Record
Vitals" button (visible only while `state == 'waiting_nurse'`) and two new
notebook pages: Vitals History and Nurse Tasks.

The Vitals Quick-Entry screen (`hospital_nurse.vitals_quick_entry` client
action) is a separate, tablet-optimized OWL component with numeric
steppers and an auto-computed, color-flagged BMI display, opened as a
dialog from the dashboard.

## Install / Configuration

1. Install `hospital_base` and `hospital_reception` first.
2. Install `hospital_nurse` from the Apps menu.
3. Assign the **Hospital Nurse** group to nursing staff.
4. Go to **Hospital -> Nurse Station -> Dashboard** to start recording
   vitals.

Demo data adds `hospital.vitals` records for 4 of `hospital_reception`'s
10 demo visits (`demo_visit_01`, `02`, `03`, `06`), via the model's actual
`create()` method rather than setting `state` by hand -- so the
auto-escalation/auto-transition behavior runs exactly as it would in
production, leaving the remaining 6 demo visits in `waiting_nurse` so the
dashboard's "Next Patient" queue isn't empty.
