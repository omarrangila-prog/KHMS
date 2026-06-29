# Hospital Executive Dashboard (`hospital_dashboard`)

Module 10 of 12 in the Hospital Management System suite.

## Purpose

Cross-department, admin-level KPI rollup. Per-department dashboards (reception,
nurse, doctor, pharmacy, lab, radiology, ward) each ship in their own module; this
module adds the executive cross-cutting view on top of all of them.

## Dependencies

- `hospital_base`, `hospital_reception`, `hospital_doctor`, `hospital_pharmacy`,
  `hospital_lab`, `hospital_radiology`, `hospital_ipd`

## Key Models

| Model | Purpose |
|---|---|
| `hospital.dashboard.kpi` | SQL-view-backed (`_auto = False`), one row per company: patient volume, bed occupancy %, avg. doctor wait time, ward revenue |

## KPI Definitions

- **Patients Today / This Week**: distinct patients with a visit `checkin_datetime` in the window.
- **Bed Occupancy %**: `occupied beds / total beds * 100` across `hospital.bed`. 0% if a company has no beds configured (not NULL).
- **Avg. Doctor Wait (minutes)**: average minutes between a visit's `checkin_datetime` and its first `hospital.consultation.create_date`.
- **Ward Revenue**: sum of `length_of_stay_days * ward.daily_rate` across confirmed `hospital.discharge` records — computed directly from the stored admission/ward columns, since `hospital.discharge.ward_charge_amount` itself is a non-stored compute field with no backing column a SQL view could join. This is the only real billing-shaped number anywhere in the suite until a future billing module exists.

## Installation

```bash
./odoo-bin -d mydb -i hospital_dashboard
```

## Security

- `hospital_base.group_hospital_admin` — read-only access to the KPI view. No group has write/create/unlink, since `hospital.dashboard.kpi` is a read-only SQL view with nothing to write back to.

## Tests

Run with:
```bash
./odoo-bin -d mydb --test-enable -i hospital_dashboard
```

Covers: KPI numbers match underlying transactional data on a seeded demo set
(patient counts, bed occupancy, ward revenue cross-checked against direct ORM
queries on the source models).
